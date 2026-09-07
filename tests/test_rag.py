"""RAG behaviour: no-evidence + no-provider paths never fabricate answers."""
from __future__ import annotations

from conftest import make_text_pdf

from app.ai.rag import answer_question
from app.ingestion.pipeline import ingest_document_bytes
from app.retrieval.search import SearchFilters


def test_no_evidence_returns_insufficient_without_calling_model(db, demo_source):
    # Empty archive -> must return insufficient, not a hallucinated answer.
    resp = answer_question(
        db, "What happened in 1962?", provider_id="groq", model_id="openai/gpt-oss-120b",
        filters=SearchFilters(include_demo=True),
    )
    assert resp.confidence == "insufficient_evidence"
    assert "sufficient" in resp.answer.lower()
    assert resp.chunks_retrieved == 0


def test_evidence_but_no_provider_key_is_honest(db, demo_source):
    ingest_document_bytes(db, source=demo_source,
                          content=make_text_pdf(["The 1962 border situation involved NEFA."]),
                          source_url="http://x/1.pdf", filename="1.pdf", is_demo=True)
    db.commit()
    resp = answer_question(
        db, "border 1962 NEFA", provider_id="groq", model_id="openai/gpt-oss-120b",
        filters=SearchFilters(include_demo=True),
    )
    # Provider not configured in tests -> retrieval shown, but answer not fabricated.
    assert resp.chunks_retrieved >= 1
    assert "not configured" in resp.answer.lower() or "NOT CONFIGURED" in " ".join(resp.warnings)
