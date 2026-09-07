"""Exports: CSV catalogue, JSON metadata, BibTeX, archive manifest.
Never exports API keys or secrets (spec 65)."""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import document_summary
from app.db.base import get_db
from app.db.models import Document

router = APIRouter(prefix="/api/exports", tags=["exports"])

_MANIFEST_FIELDS = [
    "document_id", "title", "author", "date", "document_type", "source_url",
    "archived_url", "local_path", "sha256", "mime_type", "file_size",
    "page_count", "ocr_status", "index_status", "rights_status", "retrieved_at",
]


def _manifest_rows(db: Session, include_demo: bool):
    stmt = select(Document)
    if not include_demo:
        stmt = stmt.where(Document.is_demo.is_(False))
    for d in db.execute(stmt).scalars().all():
        yield {
            "document_id": d.document_id, "title": d.title, "author": d.author,
            "date": d.doc_date, "document_type": d.document_type, "source_url": d.source_url,
            "archived_url": d.archived_url, "local_path": d.local_path, "sha256": d.sha256,
            "mime_type": d.mime_type, "file_size": d.file_size, "page_count": d.page_count,
            "ocr_status": d.ocr_status.value, "index_status": d.index_status.value,
            "rights_status": d.rights_status,
            "retrieved_at": d.retrieved_at.isoformat() if d.retrieved_at else None,
        }


@router.get("/manifest.csv")
def manifest_csv(include_demo: bool = False, db: Session = Depends(get_db)):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_MANIFEST_FIELDS)
    writer.writeheader()
    for row in _manifest_rows(db, include_demo):
        writer.writerow(row)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=archive_manifest.csv"})


@router.get("/manifest.json")
def manifest_json(include_demo: bool = False, db: Session = Depends(get_db)):
    return {"documents": list(_manifest_rows(db, include_demo))}


@router.get("/catalogue.json")
def catalogue_json(include_demo: bool = False, db: Session = Depends(get_db)):
    stmt = select(Document)
    if not include_demo:
        stmt = stmt.where(Document.is_demo.is_(False))
    return {"documents": [document_summary(d) for d in db.execute(stmt).scalars().all()]}


@router.get("/bibtex")
def bibtex(include_demo: bool = False, db: Session = Depends(get_db)):
    stmt = select(Document)
    if not include_demo:
        stmt = stmt.where(Document.is_demo.is_(False))
    entries = []
    for d in db.execute(stmt).scalars().all():
        year = (d.doc_date or "")[:4]
        fields = [f"  title = {{{d.title or 'Untitled'}}}"]
        if d.author:
            fields.append(f"  author = {{{d.author}}}")
        if year:
            fields.append(f"  year = {{{year}}}")
        if d.source_url:
            fields.append(f"  url = {{{d.source_url}}}")
        fields.append(f"  note = {{Document ID {d.document_id}; SHA256 {d.sha256 or 'unknown'}}}")
        entries.append("@misc{" + d.document_id.replace("-", "") + ",\n" + ",\n".join(fields) + "\n}")
    return PlainTextResponse("\n\n".join(entries), media_type="text/plain")
