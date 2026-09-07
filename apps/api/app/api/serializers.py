"""Plain-dict serializers for ORM rows. Never emit secrets."""
from __future__ import annotations

import json

from app.db.models import Document


def _enum(v):
    return v.value if hasattr(v, "value") else v


def document_summary(d: Document) -> dict:
    return {
        "id": d.id,
        "document_id": d.document_id,
        "title": d.title,
        "author": d.author,
        "date": d.doc_date,
        "date_precision": _enum(d.date_precision),
        "document_type": d.document_type,
        "page_count": d.page_count,
        "language": d.language,
        "source_url": d.source_url,
        "archived_url": d.archived_url,
        "rights_status": d.rights_status,
        "access_status": d.access_status,
        "sha256": d.sha256,
        "is_demo": d.is_demo,
        "ocr_status": _enum(d.ocr_status),
        "text_extraction_status": _enum(d.text_extraction_status),
        "index_status": _enum(d.index_status),
        "embedding_status": _enum(d.embedding_status),
        "metadata_source": _enum(d.metadata_source),
        "review_status": _enum(d.review_status),
        "retrieved_at": d.retrieved_at.isoformat() if d.retrieved_at else None,
    }


def document_detail(d: Document, topics: list, entities: list) -> dict:
    base = document_summary(d)
    base.update({
        "subtitle": d.subtitle,
        "publisher": d.publisher,
        "description": d.description,
        "mime_type": d.mime_type,
        "file_size": d.file_size,
        "copyright_notes": d.copyright_notes,
        "metadata_only": d.metadata_only,
        "duplicate_of_id": d.duplicate_of_id,
        "topics": topics,
        "entities": entities,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    })
    return base


def loads(maybe_json: str | None):
    if not maybe_json:
        return None
    try:
        return json.loads(maybe_json)
    except json.JSONDecodeError:
        return None
