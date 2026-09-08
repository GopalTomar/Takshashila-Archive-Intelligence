"""Dashboard statistics - REAL database counts only (spec 44, 57).

Every value is a live query. Nothing is hard-coded. When a metric has no data
the count is 0 (never invented). Demo/synthetic documents are excluded unless
``include_demo=true``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedder
from app.db.base import get_db
from app.db.models import (
    ArchiveCollection,
    CrawlRun,
    Document,
    DocumentChunk,
    DocumentPage,
    Entity,
    ProcessingJob,
    ProcessingStatus,
    Source,
    Topic,
)

router = APIRouter(prefix="/api", tags=["stats"])


def _demo_filtered_count(db: Session, model, include_demo: bool):
    """Count rows of a model joined to Document, honouring the demo filter."""
    stmt = select(func.count()).select_from(model).join(Document, Document.id == model.document_id)
    if not include_demo:
        stmt = stmt.where(Document.is_demo.is_(False))
    return db.execute(stmt).scalar() or 0


@router.get("/stats")
def stats(include_demo: bool = False, db: Session = Depends(get_db)) -> dict:
    def dcount(*where):
        stmt = select(func.count()).select_from(Document)
        if not include_demo:
            stmt = stmt.where(Document.is_demo.is_(False))
        for w in where:
            stmt = stmt.where(w)
        return db.execute(stmt).scalar() or 0

    documents = dcount()
    pages = _demo_filtered_count(db, DocumentPage, include_demo)
    chunks = _demo_filtered_count(db, DocumentChunk, include_demo)

    # Embedded chunks = chunks with an actual vector stored (never assumed).
    emb_stmt = (
        select(func.count()).select_from(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.embedding.is_not(None))
    )
    if not include_demo:
        emb_stmt = emb_stmt.where(Document.is_demo.is_(False))
    embedded_chunks = db.execute(emb_stmt).scalar() or 0

    authors = db.execute(
        select(func.count(func.distinct(Document.author))).where(Document.author.is_not(None))
    ).scalar() or 0

    # Job counts (not document-scoped; jobs are operational records).
    def jobcount(status=None):
        stmt = select(func.count()).select_from(ProcessingJob)
        if status is not None:
            stmt = stmt.where(ProcessingJob.status == status)
        return db.execute(stmt).scalar() or 0

    emb = get_embedder(db).status()
    return {
        "documents": documents,
        "pages": pages,
        "chunks": chunks,
        "embeddings": embedded_chunks,
        "collections": db.execute(select(func.count()).select_from(ArchiveCollection)).scalar() or 0,
        "sources": db.execute(select(func.count()).select_from(Source)).scalar() or 0,
        "authors": authors,
        "topics": db.execute(select(func.count()).select_from(Topic)).scalar() or 0,
        "entities": db.execute(select(func.count()).select_from(Entity)).scalar() or 0,
        "ocr_processed": dcount(Document.ocr_status == ProcessingStatus.succeeded),
        "failed_processing": dcount(Document.text_extraction_status == ProcessingStatus.failed),
        "indexed_documents": dcount(Document.index_status == ProcessingStatus.succeeded),
        "embedded_documents": dcount(Document.embedding_status == ProcessingStatus.succeeded),
        "ingestion_jobs": jobcount(),
        "crawl_jobs": db.execute(select(func.count()).select_from(CrawlRun)).scalar() or 0,
        "jobs": {
            "queued": jobcount(ProcessingStatus.pending),
            "running": jobcount(ProcessingStatus.running),
            "completed": jobcount(ProcessingStatus.succeeded),
            "failed": jobcount(ProcessingStatus.failed),
        },
        "semantic_search": {
            "enabled": emb.enabled and emb.is_real_semantic,
            "provider": emb.provider,
            "model": emb.model,
            "dimensions": emb.dimensions,
            "detail": emb.detail,
        },
        "empty": documents == 0,
    }


@router.get("/stats/distributions")
def distributions(include_demo: bool = False, db: Session = Depends(get_db)) -> dict:
    """Grouped counts for dashboard charts. Empty lists when there is no data."""

    def doc_group(column, label_transform=None):
        stmt = select(column, func.count()).select_from(Document)
        if not include_demo:
            stmt = stmt.where(Document.is_demo.is_(False))
        stmt = stmt.group_by(column).order_by(column)
        out = []
        for value, count in db.execute(stmt).all():
            if value is None:
                continue
            v = label_transform(value) if label_transform else value
            out.append({"label": str(v), "count": count})
        return out

    def enum_group(column):
        stmt = select(column, func.count()).select_from(Document)
        if not include_demo:
            stmt = stmt.where(Document.is_demo.is_(False))
        stmt = stmt.group_by(column)
        return [
            {"label": (v.value if hasattr(v, "value") else str(v)), "count": c}
            for v, c in db.execute(stmt).all()
        ]

    # Year: first 4 chars of doc_date (portable across sqlite/postgres).
    year_col = func.substr(Document.doc_date, 1, 4)
    documents_by_year = doc_group(year_col)

    # Sources with document counts.
    src_stmt = (
        select(Source.source_key, Source.name, func.count(Document.id))
        .select_from(Source).outerjoin(Document, Document.source_id == Source.id)
        .group_by(Source.id).order_by(func.count(Document.id).desc())
    )
    sources = [
        {"key": k, "name": n, "count": c} for k, n, c in db.execute(src_stmt).all()
    ]

    return {
        "documents_by_year": documents_by_year,
        "documents_by_type": doc_group(Document.document_type),
        "ocr_status": enum_group(Document.ocr_status),
        "index_status": enum_group(Document.index_status),
        "embedding_status": enum_group(Document.embedding_status),
        "sources": sources,
    }
