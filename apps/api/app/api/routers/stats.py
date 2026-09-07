"""Dashboard statistics — REAL database counts only (spec 44, 57)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedder
from app.db.base import get_db
from app.db.models import (
    ArchiveCollection,
    Document,
    DocumentPage,
    Entity,
    ProcessingStatus,
    Source,
    Topic,
)

router = APIRouter(prefix="/api", tags=["stats"])


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
    pages_stmt = select(func.count()).select_from(DocumentPage).join(
        Document, Document.id == DocumentPage.document_id
    )
    if not include_demo:
        pages_stmt = pages_stmt.where(Document.is_demo.is_(False))
    pages = db.execute(pages_stmt).scalar() or 0

    authors = db.execute(
        select(func.count(func.distinct(Document.author))).where(Document.author.is_not(None))
    ).scalar() or 0

    emb = get_embedder(db).status()
    return {
        "documents": documents,
        "pages": pages,
        "collections": db.execute(select(func.count()).select_from(ArchiveCollection)).scalar() or 0,
        "sources": db.execute(select(func.count()).select_from(Source)).scalar() or 0,
        "authors": authors,
        "topics": db.execute(select(func.count()).select_from(Topic)).scalar() or 0,
        "entities": db.execute(select(func.count()).select_from(Entity)).scalar() or 0,
        "ocr_processed": dcount(Document.ocr_status == ProcessingStatus.succeeded),
        "failed_processing": dcount(Document.text_extraction_status == ProcessingStatus.failed),
        "indexed_documents": dcount(Document.index_status == ProcessingStatus.succeeded),
        "embedded_documents": dcount(Document.embedding_status == ProcessingStatus.succeeded),
        "semantic_search": {
            "enabled": emb.enabled and emb.is_real_semantic,
            "provider": emb.provider,
            "detail": emb.detail,
        },
        "empty": documents == 0,
    }
