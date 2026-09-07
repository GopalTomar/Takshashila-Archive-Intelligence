"""Citation validation (anti-hallucination).

Every citation returned by the model is checked against the database and
against the evidence actually supplied:
  * the chunk_id must exist and have been in the retrieved evidence set;
  * the document_id must match that chunk's document;
  * the cited page must be a real page of that document;
  * any quote must actually appear in the chunk/page text (normalised).

Citations that fail are marked invalid. The overall confidence is downgraded
based on how much of the answer is actually supported — never on the model's
own say-so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk, DocumentPage


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


@dataclass
class ValidatedCitation:
    id: str
    document_id: str | None
    chunk_id: str | None
    page: int | None
    title: str | None
    source_url: str | None
    archived_url: str | None
    quote: str | None
    valid: bool
    note: str


@dataclass
class ValidationOutcome:
    citations: list[ValidatedCitation] = field(default_factory=list)
    invalid_ids: list[str] = field(default_factory=list)
    confidence: str = "insufficient_evidence"

    @property
    def all_valid(self) -> bool:
        return not self.invalid_ids and bool(self.citations)


def validate_citations(
    db: Session,
    raw_citations: list[dict],
    allowed_chunk_ids: set[str],
    model_confidence: str | None = None,
) -> ValidationOutcome:
    outcome = ValidationOutcome()
    valid_count = 0

    for rc in raw_citations or []:
        cid = str(rc.get("id") or f"c{len(outcome.citations)+1}")
        chunk_id = rc.get("chunk_id")
        doc_ref = rc.get("document_id")
        page = rc.get("page")
        quote = rc.get("quote")
        note_parts: list[str] = []
        valid = True

        chunk = None
        if chunk_id:
            chunk = db.execute(
                select(DocumentChunk).where(DocumentChunk.chunk_id == chunk_id)
            ).scalar_one_or_none()

        if chunk is None:
            valid = False
            note_parts.append("chunk_id not found in archive")
        else:
            if chunk_id not in allowed_chunk_ids:
                valid = False
                note_parts.append("chunk was not part of retrieved evidence (possible fabrication)")

        doc = None
        if chunk is not None:
            doc = db.get(Document, chunk.document_id)
            if doc and doc_ref and doc.document_id != doc_ref:
                valid = False
                note_parts.append(f"document_id mismatch (chunk belongs to {doc.document_id})")

        # Page existence.
        resolved_page = page if page is not None else (chunk.page_number if chunk else None)
        if doc is not None and resolved_page is not None:
            page_exists = db.execute(
                select(DocumentPage).where(
                    DocumentPage.document_id == doc.id,
                    DocumentPage.page_number == int(resolved_page),
                )
            ).scalar_one_or_none()
            if page_exists is None:
                # Allow page to equal chunk.page_number even if page row missing,
                # but flag impossible pages.
                if doc.page_count and int(resolved_page) > doc.page_count:
                    valid = False
                    note_parts.append(f"page {resolved_page} exceeds document page_count {doc.page_count}")

        # Quote verification.
        if quote and chunk is not None:
            if _normalize(quote) not in _normalize(chunk.text):
                # Check the page text too.
                page_text = ""
                if doc is not None and resolved_page is not None:
                    pt = db.execute(
                        select(DocumentPage).where(
                            DocumentPage.document_id == doc.id,
                            DocumentPage.page_number == int(resolved_page),
                        )
                    ).scalar_one_or_none()
                    page_text = pt.text if pt else ""
                if _normalize(quote) not in _normalize(page_text):
                    valid = False
                    note_parts.append("quote not found in cited chunk/page")

        if valid:
            valid_count += 1
        else:
            outcome.invalid_ids.append(cid)

        outcome.citations.append(ValidatedCitation(
            id=cid,
            document_id=(doc.document_id if doc else doc_ref),
            chunk_id=chunk_id,
            page=(int(resolved_page) if resolved_page is not None else None),
            title=(doc.title if doc else None),
            source_url=(doc.source_url if doc else None),
            archived_url=(doc.archived_url if doc else None),
            quote=quote,
            valid=valid,
            note="; ".join(note_parts) or "ok",
        ))

    # Confidence is derived from validation, not the model's claim.
    total = len(outcome.citations)
    if total == 0:
        outcome.confidence = "insufficient_evidence"
    elif valid_count == total:
        outcome.confidence = "supported"
    elif valid_count > 0:
        outcome.confidence = "partially_supported"
    else:
        outcome.confidence = "insufficient_evidence"
    return outcome
