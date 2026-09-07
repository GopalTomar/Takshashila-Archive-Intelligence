"""Citation validation / anti-hallucination."""
from __future__ import annotations

from conftest import make_text_pdf

from app.ai.citations import validate_citations
from app.ingestion.pipeline import ingest_document_bytes


def _doc(db, source):
    doc = ingest_document_bytes(db, source=source,
                               content=make_text_pdf(["Nehru wrote about Aksai Chin in 1959."]),
                               source_url="http://x/1.pdf", filename="1.pdf", is_demo=True)
    db.commit()
    return doc


def test_valid_citation_passes(db, demo_source):
    doc = _doc(db, demo_source)
    chunk = doc.chunks[0]
    outcome = validate_citations(db, [{
        "id": "c1", "document_id": doc.document_id, "chunk_id": chunk.chunk_id,
        "page": chunk.page_number, "quote": "Aksai Chin",
    }], allowed_chunk_ids={chunk.chunk_id})
    assert outcome.all_valid
    assert outcome.confidence == "supported"


def test_fabricated_chunk_is_invalid(db, demo_source):
    doc = _doc(db, demo_source)
    outcome = validate_citations(db, [{
        "id": "c1", "document_id": doc.document_id, "chunk_id": "NOPE-c9999", "page": 1,
    }], allowed_chunk_ids=set())
    assert not outcome.all_valid
    assert "c1" in outcome.invalid_ids
    assert outcome.confidence == "insufficient_evidence"


def test_impossible_page_is_invalid(db, demo_source):
    doc = _doc(db, demo_source)
    chunk = doc.chunks[0]
    outcome = validate_citations(db, [{
        "id": "c1", "document_id": doc.document_id, "chunk_id": chunk.chunk_id, "page": 9999,
    }], allowed_chunk_ids={chunk.chunk_id})
    assert not outcome.all_valid


def test_quote_not_in_source_is_invalid(db, demo_source):
    doc = _doc(db, demo_source)
    chunk = doc.chunks[0]
    outcome = validate_citations(db, [{
        "id": "c1", "document_id": doc.document_id, "chunk_id": chunk.chunk_id,
        "page": chunk.page_number, "quote": "this exact sentence never appears in the document",
    }], allowed_chunk_ids={chunk.chunk_id})
    assert not outcome.all_valid


def test_chunk_not_in_evidence_flagged(db, demo_source):
    doc = _doc(db, demo_source)
    chunk = doc.chunks[0]
    # chunk exists but was NOT part of retrieved evidence -> possible fabrication.
    outcome = validate_citations(db, [{
        "id": "c1", "document_id": doc.document_id, "chunk_id": chunk.chunk_id,
        "page": chunk.page_number,
    }], allowed_chunk_ids=set())
    assert not outcome.all_valid
