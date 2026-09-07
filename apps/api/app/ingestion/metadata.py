"""Deterministic metadata extraction.

Uses PDF metadata, filename, and first-page text heuristics. Everything it
produces is marked ``deterministic``. It NEVER guesses a value it cannot
support — unknown fields stay ``None``. AI-assisted metadata (separate path)
is stored as ``ai`` and enters review, never promoted to verified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.db.models import DatePrecision

_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_PDF_DATE_RE = re.compile(r"D:(\d{4})(\d{2})?(\d{2})?")


@dataclass
class ExtractedMetadata:
    title: str | None = None
    author: str | None = None
    doc_date: str | None = None
    date_precision: DatePrecision = DatePrecision.unknown
    page_count: int | None = None
    language: str | None = None
    document_type: str | None = None
    notes: list[str] = field(default_factory=list)


def _title_from_filename(url_or_path: str) -> str | None:
    name = Path(urlparse(url_or_path).path or url_or_path).name
    name = unquote(name)
    stem = Path(name).stem
    if not stem:
        return None
    cleaned = re.sub(r"[_\-]+", " ", stem).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or None


def _parse_pdf_date(raw: str | None) -> tuple[str | None, DatePrecision]:
    if not raw:
        return None, DatePrecision.unknown
    m = _PDF_DATE_RE.search(raw)
    if not m:
        return None, DatePrecision.unknown
    year, month, day = m.group(1), m.group(2), m.group(3)
    if day and month:
        return f"{year}-{month}-{day}", DatePrecision.exact
    if month:
        return f"{year}-{month}", DatePrecision.month
    return year, DatePrecision.year


def extract_pdf_metadata(path: str, source_url: str | None, first_page_text: str | None) -> ExtractedMetadata:
    out = ExtractedMetadata()
    try:
        import fitz
        doc = fitz.open(path)
        out.page_count = doc.page_count
        meta = doc.metadata or {}
        doc.close()
    except Exception as exc:
        out.notes.append(f"pdf metadata unavailable: {exc}")
        meta = {}

    title = (meta.get("title") or "").strip() or None
    author = (meta.get("author") or "").strip() or None
    date_str, precision = _parse_pdf_date(meta.get("creationDate") or meta.get("modDate"))

    # Fallbacks that are still deterministic (from filename/url), clearly noted.
    if not title:
        title = _title_from_filename(source_url or path)
        if title:
            out.notes.append("title derived from filename (deterministic)")
    if not date_str and first_page_text:
        m = _YEAR_RE.search(first_page_text[:2000])
        if m:
            date_str, precision = m.group(1), DatePrecision.year
            out.notes.append("year derived from first-page text (deterministic, low precision)")

    out.title = title
    out.author = author  # may be None — never guessed
    out.doc_date = date_str
    out.date_precision = precision
    out.document_type = None  # not asserted deterministically
    return out
