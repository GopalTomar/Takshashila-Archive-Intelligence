"""Ingestion pipeline orchestration.

Given downloaded document bytes and provenance, runs the pipeline steps and
records an explicit status for each. Steps degrade independently: a document
whose OCR fails is still stored, catalogued and (partially) searchable — never
lost. Deduplication is by SHA-256 and by source URL. Originals are never
overwritten.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder, get_embedder
from app.db.models import (
    DatePrecision,
    Document,
    DocumentChunk,
    DocumentEntity,
    DocumentFile,
    DocumentPage,
    DocumentTopic,
    Entity,
    MetadataSource,
    ProcessingStatus,
    Source,
    Topic,
)
from app.ingestion import chunking, metadata as metadata_mod, taxonomy
from app.logging_config import get_logger
from app.ocr import pdf as pdf_ocr
from app.security.files import sniff_mime, validate_signature
from app.storage import files as storage

log = get_logger("ingestion")


def allocate_document_id(db: Session, source: Source) -> str:
    seq = source.next_seq
    source.next_seq = seq + 1
    db.flush()
    return f"{source.doc_prefix}-{seq:05d}"


def find_duplicate(db: Session, sha256: str | None, source_url: str | None) -> Document | None:
    if sha256:
        dup = db.execute(select(Document).where(Document.sha256 == sha256)).scalars().first()
        if dup:
            return dup
    if source_url:
        dup = db.execute(select(Document).where(Document.source_url == source_url)).scalars().first()
        if dup:
            return dup
    return None


def ingest_document_bytes(
    db: Session,
    *,
    source: Source,
    content: bytes,
    source_url: str | None,
    filename: str | None = None,
    content_type: str | None = None,
    archived_url: str | None = None,
    archive_provider: str | None = None,
    archive_snapshot_timestamp: str | None = None,
    is_demo: bool = False,
    collection_id: int | None = None,
    force_ocr: bool = False,
    embedder: Embedder | None = None,
    progress: dict | None = None,
) -> Document:
    """Full pipeline for one document. Returns the Document (committed by caller)."""
    embedder = embedder or get_embedder(db)
    progress = progress if progress is not None else {}

    # ── VALIDATE (file signature; do not trust extension) ──
    sha = storage.sha256_bytes(content)
    sniffed = sniff_mime(content)
    mime = sniffed or content_type or "application/octet-stream"

    # ── DEDUPLICATE ──
    dup = find_duplicate(db, sha, source_url)
    if dup is not None:
        log.info("duplicate_detected", sha256=sha, existing=dup.document_id)
        progress["duplicate"] = dup.document_id
        return dup

    is_pdf = validate_signature(content, "application/pdf") or mime == "application/pdf"

    # ── CREATE RECORD + STORE ORIGINAL ──
    document_id = allocate_document_id(db, source)
    doc = Document(
        document_id=document_id,
        source_id=source.id,
        collection_id=collection_id,
        source_url=source_url,
        archived_url=archived_url,
        archive_provider=archive_provider,
        archive_snapshot_timestamp=archive_snapshot_timestamp,
        mime_type=mime,
        file_size=len(content),
        sha256=sha,
        retrieved_at=datetime.now(timezone.utc),
        rights_status=source.rights_status,
        access_status=source.access_status,
        copyright_notes=source.copyright_notes,
        is_demo=is_demo,
        metadata_source=MetadataSource.deterministic,
    )
    db.add(doc)
    db.flush()

    stored = storage.save_bytes(document_id, "original", filename or f"{document_id}.pdf", content)
    doc.local_path = stored["local_path"]
    db.add(DocumentFile(
        document_id=doc.id, role="original", local_path=stored["local_path"],
        mime_type=mime, file_size=stored["file_size"], sha256=stored["sha256"],
        checksum_computed_at=stored["checksum_computed_at"],
    ))
    doc.download_status = ProcessingStatus.succeeded

    if not is_pdf:
        # Non-PDF: stored + catalogued, but no text pipeline here.
        doc.text_extraction_status = ProcessingStatus.not_applicable
        doc.ocr_status = ProcessingStatus.not_applicable
        doc.metadata_status = ProcessingStatus.succeeded
        doc.index_status = ProcessingStatus.not_applicable
        db.flush()
        return doc

    # ── TEXT EXTRACTION / OCR ──
    extraction = pdf_ocr.extract_text(stored["local_path"], force_ocr=force_ocr)
    doc.page_count = extraction.page_count
    if extraction.error and extraction.total_chars == 0:
        doc.text_extraction_status = ProcessingStatus.failed
        doc.ocr_status = ProcessingStatus.failed if extraction.used_ocr else ProcessingStatus.not_applicable
        log.warning("text_extraction_failed", document_id=document_id, error=extraction.error)
    else:
        doc.text_extraction_status = ProcessingStatus.succeeded
        doc.ocr_status = (
            ProcessingStatus.succeeded if extraction.used_ocr else ProcessingStatus.not_applicable
        )

    # Persist pages.
    first_page_text = extraction.pages[0].text if extraction.pages else None
    for p in extraction.pages:
        db.add(DocumentPage(
            document_id=doc.id, page_number=p.page_number, text=p.text,
            char_count=len(p.text or ""), text_source=p.source, ocr_confidence=p.confidence,
        ))

    # OCR run bookkeeping.
    if extraction.used_ocr:
        from app.db.models import OcrRun
        db.add(OcrRun(
            document_id=doc.id, engine=extraction.engine, engine_version=extraction.engine_version,
            status=ProcessingStatus.succeeded, pages_processed=extraction.page_count,
            mean_confidence=extraction.mean_confidence,
            started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
        ))

    # ── METADATA (deterministic) ──
    meta = metadata_mod.extract_pdf_metadata(stored["local_path"], source_url, first_page_text)
    doc.title = meta.title
    doc.author = meta.author
    doc.doc_date = meta.doc_date
    doc.date_precision = meta.date_precision or DatePrecision.unknown
    doc.language = meta.language
    doc.document_type = meta.document_type
    doc.metadata_status = ProcessingStatus.succeeded
    doc.metadata_source = MetadataSource.deterministic
    db.flush()

    # ── CHUNKING (page-preserving) ──
    pages_for_chunking = [(p.page_number, p.text or "") for p in extraction.pages]
    chunks = chunking.chunk_pages(pages_for_chunking)
    full_text = "\n".join(p.text or "" for p in extraction.pages)

    chunk_rows: list[DocumentChunk] = []
    for ch in chunks:
        cid = f"{document_id}-c{ch.chunk_index:04d}"
        row = DocumentChunk(
            chunk_id=cid, document_id=doc.id, page_number=ch.page_number,
            section=ch.section, chunk_index=ch.chunk_index, text=ch.text,
            char_start=ch.char_start, char_end=ch.char_end, token_estimate=ch.token_estimate,
        )
        db.add(row)
        chunk_rows.append(row)
    db.flush()
    progress["chunks"] = len(chunk_rows)

    # ── EMBEDDING (only if configured — never faked) ──
    if embedder.enabled and chunk_rows:
        try:
            texts = [c.text for c in chunk_rows]
            vectors = embedder.embed(texts)
            for row, vec in zip(chunk_rows, vectors):
                row.embedding = vec
                row.embedding_model = f"{embedder.provider}:{embedder.model or 'hash'}"
                row.embedding_dims = len(vec)
            doc.embedding_status = ProcessingStatus.succeeded
        except Exception as exc:
            doc.embedding_status = ProcessingStatus.failed
            log.warning("embedding_failed", document_id=document_id, error=str(exc))
    else:
        doc.embedding_status = ProcessingStatus.skipped

    # ── TOPIC + ENTITY TAGGING (deterministic, evidence-backed) ──
    _tag_topics(db, doc, full_text)
    _tag_entities(db, doc, extraction.pages)

    doc.index_status = ProcessingStatus.succeeded
    db.flush()
    log.info("document_ingested", document_id=document_id, pages=doc.page_count, chunks=len(chunk_rows))
    return doc


def _get_or_create_topic(db: Session, key: str, label: str) -> Topic:
    t = db.execute(select(Topic).where(Topic.key == key)).scalar_one_or_none()
    if not t:
        t = Topic(key=key, label=label)
        db.add(t)
        db.flush()
    return t


def _tag_topics(db: Session, doc: Document, text: str) -> None:
    for match in taxonomy.match_topics(text):
        topic = _get_or_create_topic(db, match["key"], match["label"])
        exists = db.execute(
            select(DocumentTopic).where(
                DocumentTopic.document_id == doc.id, DocumentTopic.topic_id == topic.id
            )
        ).scalar_one_or_none()
        if not exists:
            db.add(DocumentTopic(
                document_id=doc.id, topic_id=topic.id, confidence=1.0,
                evidence=match["evidence"], source=MetadataSource.deterministic,
            ))


def _get_or_create_entity(db: Session, etype: str, name: str) -> Entity:
    e = db.execute(
        select(Entity).where(Entity.entity_type == etype, Entity.name == name)
    ).scalar_one_or_none()
    if not e:
        e = Entity(entity_type=etype, name=name)
        db.add(e)
        db.flush()
    return e


def _tag_entities(db: Session, doc: Document, pages) -> None:
    seen: set[tuple[str, str, int]] = set()
    for p in pages:
        for match in taxonomy.match_entities(p.text or ""):
            key = (match["type"], match["name"], p.page_number)
            if key in seen:
                continue
            seen.add(key)
            entity = _get_or_create_entity(db, match["type"], match["name"])
            db.add(DocumentEntity(
                document_id=doc.id, entity_id=entity.id, page_number=p.page_number,
                mention=match["mention"], confidence=1.0, source=MetadataSource.deterministic,
            ))
