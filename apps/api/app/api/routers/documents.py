"""Document listing, detail, pages, and secure file streaming."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import document_detail, document_summary
from app.db.base import get_db
from app.db.models import (
    Document,
    DocumentEntity,
    DocumentPage,
    DocumentTopic,
    Entity,
    Topic,
)
from app.schemas import ReviewIn
from app.security.files import ensure_within
from app.storage.files import store_root

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(
    q: str | None = None,
    include_demo: bool = False,
    topic_key: str | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Document)
    count_stmt = select(func.count()).select_from(Document)
    if not include_demo:
        stmt = stmt.where(Document.is_demo.is_(False))
        count_stmt = count_stmt.where(Document.is_demo.is_(False))
    if q:
        like = f"%{q}%"
        cond = Document.title.ilike(like) | Document.author.ilike(like) | Document.description.ilike(like)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    if topic_key:
        stmt = stmt.join(DocumentTopic, DocumentTopic.document_id == Document.id).join(
            Topic, Topic.id == DocumentTopic.topic_id
        ).where(Topic.key == topic_key)

    total = db.execute(count_stmt).scalar() or 0
    stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    docs = db.execute(stmt).scalars().all()
    return {"total": total, "items": [document_summary(d) for d in docs], "limit": limit, "offset": offset}


def _get_doc(db: Session, document_id: str) -> Document:
    doc = db.execute(select(Document).where(Document.document_id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.get("/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)) -> dict:
    doc = _get_doc(db, document_id)
    topics = []
    for dt, t in db.execute(
        select(DocumentTopic, Topic).join(Topic, Topic.id == DocumentTopic.topic_id).where(
            DocumentTopic.document_id == doc.id
        )
    ).all():
        topics.append({"key": t.key, "label": t.label, "evidence": dt.evidence,
                       "source": dt.source.value if hasattr(dt.source, "value") else dt.source})
    entities = []
    for de, e in db.execute(
        select(DocumentEntity, Entity).join(Entity, Entity.id == DocumentEntity.entity_id).where(
            DocumentEntity.document_id == doc.id
        )
    ).all():
        entities.append({"type": e.entity_type, "name": e.name, "page": de.page_number, "mention": de.mention})
    return document_detail(doc, topics, entities)


@router.get("/{document_id}/pages")
def get_pages(document_id: str, db: Session = Depends(get_db)) -> dict:
    doc = _get_doc(db, document_id)
    pages = db.execute(
        select(DocumentPage).where(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number)
    ).scalars().all()
    return {
        "document_id": document_id,
        "pages": [
            {"page_number": p.page_number, "char_count": p.char_count,
             "text_source": p.text_source, "ocr_confidence": p.ocr_confidence, "text": p.text}
            for p in pages
        ],
    }


@router.get("/{document_id}/file")
def get_file(document_id: str, db: Session = Depends(get_db)):
    doc = _get_doc(db, document_id)
    if doc.metadata_only:
        raise HTTPException(status_code=403, detail="metadata-only record: file not redistributable")
    if not doc.local_path:
        raise HTTPException(status_code=404, detail="no local file for this document")
    path = Path(doc.local_path)
    try:
        # Prevent path traversal: file must live inside the store root.
        ensure_within(store_root(), path)
    except ValueError:
        raise HTTPException(status_code=403, detail="file path outside storage root")
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing on disk")
    return FileResponse(str(path), media_type=doc.mime_type or "application/pdf", filename=path.name)


@router.post("/{document_id}/review")
def set_review(document_id: str, body: ReviewIn, db: Session = Depends(get_db)) -> dict:
    from app.db.models import ReviewStatus
    doc = _get_doc(db, document_id)
    try:
        doc.review_status = ReviewStatus(body.review_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid review_status: {body.review_status}")
    db.commit()
    return {"document_id": document_id, "review_status": doc.review_status.value}
