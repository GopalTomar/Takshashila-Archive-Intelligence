"""Ask the Archive (RAG), document summarization, and document Q&A."""
from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedder
from app.ai.rag import answer_question
from app.db.base import get_db
from app.db.models import Document, ResearchSession
from app.retrieval.search import SearchFilters
from app.schemas import AskRequest

router = APIRouter(prefix="/api", tags=["ask"])


def _run(db, req: AskRequest, filters: SearchFilters):
    embedder = get_embedder(db)
    resp = answer_question(
        db, req.question, provider_id=req.provider_id, model_id=req.model_id,
        archive_only=req.archive_only, reasoning=req.reasoning, temperature=req.temperature,
        max_tokens=req.max_tokens, top_k=req.top_k, mode=req.mode, filters=filters, embedder=embedder,
    )
    return resp


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)) -> dict:
    filters = SearchFilters(**req.filters.model_dump())
    resp = _run(db, req, filters)
    payload = asdict(resp)

    if req.save_session:
        session = ResearchSession(
            title=req.question[:120], question=req.question, answer=resp.answer,
            citations_json=json.dumps(resp.citations), sources_json=json.dumps(resp.sources),
            provider_id=resp.provider_id, model_id=resp.model_id,
            retrieval_mode=resp.retrieval_mode, confidence=resp.confidence,
        )
        db.add(session)
        db.commit()
        payload["saved_session_id"] = session.id

    payload["transparency"] = {
        "provider": resp.provider_id,
        "model": resp.model_id,
        "reasoning": resp.reasoning,
        "retrieval_mode": resp.retrieval_mode,
        "documents_retrieved": resp.documents_retrieved,
        "chunks_retrieved": resp.chunks_retrieved,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "cost_note": resp.cost_note,
    }
    return payload


@router.post("/documents/{document_id}/ask")
def ask_document(document_id: str, req: AskRequest, db: Session = Depends(get_db)) -> dict:
    doc = db.execute(select(Document).where(Document.document_id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    # Scope retrieval to this document (spec 89).
    filters = SearchFilters(**req.filters.model_dump())
    filters.document_id = doc.id
    filters.include_demo = doc.is_demo or filters.include_demo
    resp = _run(db, req, filters)
    return asdict(resp)


@router.post("/documents/{document_id}/summarize")
def summarize_document(document_id: str, req: AskRequest, db: Session = Depends(get_db)) -> dict:
    doc = db.execute(select(Document).where(Document.document_id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    req.question = (
        "Summarize this document. Cite the page for each point. "
        "Do not include anything not present in the evidence."
    )
    req.top_k = max(req.top_k, 12)
    filters = SearchFilters(**req.filters.model_dump())
    filters.document_id = doc.id
    filters.include_demo = doc.is_demo or filters.include_demo
    resp = _run(db, req, filters)
    return asdict(resp)
