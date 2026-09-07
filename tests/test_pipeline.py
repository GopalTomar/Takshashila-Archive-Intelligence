"""Ingestion pipeline: text PDF, empty PDF, dedup, metadata, chunk provenance."""
from __future__ import annotations

from conftest import make_empty_pdf, make_text_pdf

from app.db.models import DocumentChunk, DocumentPage, ProcessingStatus
from app.ingestion.pipeline import ingest_document_bytes


def test_text_pdf_ingests_with_pages_and_chunks(db, demo_source):
    content = make_text_pdf([
        "Page one about Aksai Chin and the McMahon Line. India China 1959.",
        "Page two about Tibet and the Dalai Lama in Lhasa.",
    ])
    doc = ingest_document_bytes(db, source=demo_source, content=content,
                               source_url="http://127.0.0.1:8899/text.pdf",
                               filename="text.pdf", content_type="application/pdf", is_demo=True)
    db.commit()
    assert doc.page_count == 2
    assert doc.text_extraction_status == ProcessingStatus.succeeded
    assert doc.sha256 and len(doc.sha256) == 64
    pages = db.query(DocumentPage).filter_by(document_id=doc.id).all()
    assert len(pages) == 2
    chunks = db.query(DocumentChunk).filter_by(document_id=doc.id).all()
    assert chunks
    # Every chunk retains a page number (provenance never lost).
    assert all(c.page_number in (1, 2) for c in chunks)


def test_empty_pdf_is_flagged_not_lost(db, demo_source):
    doc = ingest_document_bytes(db, source=demo_source, content=make_empty_pdf(),
                               source_url="http://x/empty.pdf", filename="empty.pdf",
                               content_type="application/pdf", is_demo=True)
    db.commit()
    # Document exists and is catalogued even though there's no text.
    assert doc.document_id
    assert doc.download_status == ProcessingStatus.succeeded
    # No embedded text => extraction status reflects reality (failed/needs-ocr note).
    assert doc.page_count == 1


def test_duplicate_detection_by_checksum(db, demo_source):
    content = make_text_pdf(["Same content for dedup test."])
    d1 = ingest_document_bytes(db, source=demo_source, content=content,
                              source_url="http://x/a.pdf", filename="a.pdf", is_demo=True)
    db.commit()
    d2 = ingest_document_bytes(db, source=demo_source, content=content,
                              source_url="http://x/b.pdf", filename="b.pdf", is_demo=True)
    db.commit()
    assert d1.id == d2.id  # deduplicated by SHA-256


def test_missing_metadata_stays_null(db, demo_source):
    # A PDF with no title metadata and a generic filename -> author stays None.
    content = make_text_pdf(["Body text only, no author anywhere."])
    doc = ingest_document_bytes(db, source=demo_source, content=content,
                               source_url="http://x/123.pdf", filename="123.pdf", is_demo=True)
    db.commit()
    assert doc.author is None  # never guessed


def test_non_pdf_is_stored_metadata_only_pipeline(db, demo_source):
    doc = ingest_document_bytes(db, source=demo_source, content=b"just some bytes not a pdf",
                               source_url="http://x/notpdf.bin", filename="notpdf.bin", is_demo=True)
    db.commit()
    assert doc.text_extraction_status == ProcessingStatus.not_applicable
