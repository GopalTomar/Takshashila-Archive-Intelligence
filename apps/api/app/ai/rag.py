"""RAG orchestration.

Flow: retrieve evidence -> (if none) return insufficient WITHOUT calling the
model -> build grounded prompt -> call provider (structured JSON) -> parse ->
validate citations against the DB -> persist an audit trail -> return a
structured, transparent response.

No-result behaviour (spec 90): if retrieval finds nothing relevant, we do NOT
ask the model to answer from general knowledge. We return an explicit
"insufficient evidence" response and suggestions.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from app.ai.base import ChatMessage
from app.ai.citations import validate_citations
from app.ai.embeddings import Embedder, get_embedder
from app.ai.prompts import (
    SYSTEM_PROMPT_ARCHIVE_ONLY,
    SYSTEM_PROMPT_ARCHIVE_WEB,
    EvidenceBlock,
    build_user_message,
    format_evidence,
)
from app.ai.registry import build_provider, has_credentials
from app.db.models import AiRun, Citation, Document
from app.logging_config import get_logger
from app.retrieval.search import SearchFilters, hybrid_search

log = get_logger("rag")

MIN_RELEVANCE = 0.01  # below this combined score we treat retrieval as empty


@dataclass
class RagResponse:
    answer: str
    confidence: str
    retrieval_mode: str
    documents_retrieved: int
    chunks_retrieved: int
    citations: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    provider_id: str | None = None
    model_id: str | None = None
    reasoning: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_note: str = "Cost unavailable"
    warnings: list[str] = field(default_factory=list)
    ai_run_id: int | None = None


INSUFFICIENT_MESSAGE = (
    "No sufficiently relevant archival evidence was retrieved. "
    "The archive does not contain sufficient evidence to answer this reliably."
)
SUGGESTIONS = [
    "Broaden the date range or remove date filters.",
    "Remove topic/entity/collection filters.",
    "Try related or broader search terms.",
]


def _parse_model_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    # Try direct, then extract first {...} block.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def answer_question(
    db: Session,
    question: str,
    *,
    provider_id: str,
    model_id: str,
    archive_only: bool = True,
    reasoning: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = 1200,
    top_k: int = 8,
    mode: str = "hybrid",
    filters: SearchFilters | None = None,
    embedder: Embedder | None = None,
) -> RagResponse:
    embedder = embedder or get_embedder(db)
    filters = filters or SearchFilters()

    hits, effective_mode = hybrid_search(
        db, question, mode=mode, filters=filters, top_k=top_k, embedder=embedder,
    )
    relevant = [h for h in hits if h.combined_score >= MIN_RELEVANCE] or hits
    doc_ids = {h.document_id for h in relevant}

    # No-result behaviour: do not call the model.
    if not relevant:
        return RagResponse(
            answer=INSUFFICIENT_MESSAGE, confidence="insufficient_evidence",
            retrieval_mode=effective_mode, documents_retrieved=0, chunks_retrieved=0,
            provider_id=provider_id, model_id=model_id, warnings=SUGGESTIONS,
        )

    # Build evidence blocks.
    docs = {d.id: d for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}
    blocks: list[EvidenceBlock] = []
    allowed_chunk_ids: set[str] = set()
    for i, h in enumerate(relevant, start=1):
        d = docs.get(h.document_id)
        cid = f"c{i}"
        allowed_chunk_ids.add(h.chunk_id)
        blocks.append(EvidenceBlock(
            citation_id=cid,
            document_id=(d.document_id if d else str(h.document_id)),
            chunk_id=h.chunk_id, page=h.page_number,
            title=(d.title if d else None), text=h.text,
        ))

    sources = _build_sources(relevant, docs)

    # If no provider credentials, return retrieval-only (honest, not faked).
    if not has_credentials(db, provider_id):
        return RagResponse(
            answer=(
                "AI provider not configured. Retrieved archive evidence is shown "
                "in Sources, but no answer was generated. Configure a provider in "
                "Settings → AI Providers."
            ),
            confidence="insufficient_evidence", retrieval_mode=effective_mode,
            documents_retrieved=len(doc_ids), chunks_retrieved=len(relevant),
            sources=sources, provider_id=provider_id, model_id=model_id,
            warnings=["NOT CONFIGURED: no API key for this provider."],
        )

    system = SYSTEM_PROMPT_ARCHIVE_ONLY if archive_only else SYSTEM_PROMPT_ARCHIVE_WEB
    user = build_user_message(question, format_evidence(blocks))
    messages = [ChatMessage("system", system), ChatMessage("user", user)]

    provider = build_provider(db, provider_id)
    warnings: list[str] = []
    try:
        result = provider.chat(
            messages, model=model_id, temperature=temperature,
            max_tokens=max_tokens, reasoning=reasoning,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        # Do NOT silently fall back to another model (spec 68).
        return RagResponse(
            answer=f"AI provider error: {exc}. No answer generated; evidence is shown in Sources.",
            confidence="insufficient_evidence", retrieval_mode=effective_mode,
            documents_retrieved=len(doc_ids), chunks_retrieved=len(relevant),
            sources=sources, provider_id=provider_id, model_id=model_id,
            warnings=[f"Provider call failed: {exc}"],
        )

    parsed = _parse_model_json(result.text)
    if parsed is None:
        # Model didn't return JSON; treat text as answer but with no validated citations.
        answer_text = result.text or ""
        outcome = validate_citations(db, [], allowed_chunk_ids)
        warnings.append("Model did not return structured JSON; citations could not be validated.")
        return _finalize(
            db, question, answer_text, [], outcome, effective_mode, relevant, doc_ids,
            sources, provider_id, model_id, reasoning, archive_only, result, warnings,
        )

    answer_text = parsed.get("answer") or ""
    claims = parsed.get("claims") or []
    raw_citations = parsed.get("citations") or []
    model_conf = parsed.get("confidence")
    outcome = validate_citations(db, raw_citations, allowed_chunk_ids, model_conf)

    if outcome.invalid_ids:
        warnings.append(
            f"{len(outcome.invalid_ids)} citation(s) failed validation and are "
            f"flagged: {', '.join(outcome.invalid_ids)}."
        )

    return _finalize(
        db, question, answer_text, claims, outcome, effective_mode, relevant, doc_ids,
        sources, provider_id, model_id, reasoning, archive_only, result, warnings,
    )


def _build_sources(relevant, docs) -> list[dict]:
    sources = []
    for i, h in enumerate(relevant, start=1):
        d = docs.get(h.document_id)
        sources.append({
            "ref": f"c{i}",
            "document_id": (d.document_id if d else None),
            "internal_id": h.document_id,
            "title": (d.title if d else None),
            "author": (d.author if d else None),
            "date": (d.doc_date if d else None),
            "page": h.page_number,
            "chunk_id": h.chunk_id,
            "source_url": (d.source_url if d else None),
            "archived_url": (d.archived_url if d else None),
            "passage": h.text[:600],
            "keyword_score": round(h.keyword_score, 4),
            "semantic_score": round(h.semantic_score, 4),
            "combined_score": round(h.combined_score, 4),
            "match_reasons": h.match_reasons,
        })
    return sources


def _finalize(
    db, question, answer_text, claims, outcome, effective_mode, relevant, doc_ids,
    sources, provider_id, model_id, reasoning, archive_only, result, warnings,
) -> RagResponse:
    run = AiRun(
        kind="ask", question=question, provider_id=provider_id, model_id=model_id,
        reasoning=reasoning, retrieval_mode=effective_mode, archive_only=archive_only,
        answer=answer_text, confidence=outcome.confidence,
        documents_retrieved=len(doc_ids), chunks_retrieved=len(relevant),
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
    )
    db.add(run)
    db.flush()
    for vc in outcome.citations:
        db.add(Citation(
            ai_run_id=run.id, citation_ref=vc.id,
            chunk_id=vc.chunk_id, page_number=vc.page, quote=vc.quote,
            validated=vc.valid, validation_note=vc.note,
        ))
    db.commit()

    cost_note = "Cost unavailable"
    return RagResponse(
        answer=answer_text, confidence=outcome.confidence, retrieval_mode=effective_mode,
        documents_retrieved=len(doc_ids), chunks_retrieved=len(relevant),
        citations=[asdict(c) for c in outcome.citations],
        sources=sources, claims=claims,
        provider_id=provider_id, model_id=model_id, reasoning=reasoning,
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        cost_note=cost_note, warnings=warnings, ai_run_id=run.id,
    )
