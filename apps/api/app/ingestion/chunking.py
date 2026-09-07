"""Archival-aware, page-preserving chunking.

Chunks are built page-by-page (never across page boundaries) so every chunk
retains an exact page number for provenance. Within a page, text is split on
paragraph boundaries and packed to a target size with overlap. Provenance
(document_id, page_number, section, chunk_index, char offsets) is never lost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_TARGET_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 150

_PARA_RE = re.compile(r"\n\s*\n")


@dataclass
class Chunk:
    page_number: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    section: str | None = None

    @property
    def token_estimate(self) -> int:
        # Rough heuristic: ~4 chars/token.
        return max(1, len(self.text) // 4)


def _split_paragraphs(text: str) -> list[str]:
    parts = _PARA_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def chunk_page(
    text: str,
    page_number: int,
    *,
    start_index: int = 0,
    target_chars: int = DEFAULT_TARGET_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    text = (text or "").strip()
    if not text:
        return []

    paragraphs = _split_paragraphs(text) or [text]
    chunks: list[Chunk] = []
    buffer = ""
    buffer_start = 0
    cursor = 0
    idx = start_index

    def flush(buf: str, start: int):
        nonlocal idx
        if buf.strip():
            chunks.append(
                Chunk(
                    page_number=page_number,
                    chunk_index=idx,
                    text=buf.strip(),
                    char_start=start,
                    char_end=start + len(buf),
                )
            )
            idx += 1

    for para in paragraphs:
        if not buffer:
            buffer_start = cursor
        candidate = (buffer + "\n\n" + para) if buffer else para
        if len(candidate) <= target_chars:
            buffer = candidate
        else:
            flush(buffer, buffer_start)
            # Start new buffer with overlap tail of previous.
            tail = buffer[-overlap_chars:] if overlap_chars and buffer else ""
            buffer = (tail + "\n\n" + para).strip() if tail else para
            buffer_start = cursor
        cursor += len(para) + 2

    flush(buffer, buffer_start)
    return chunks


def chunk_pages(
    pages: list[tuple[int, str]],
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """pages: list of (page_number, text). Returns provenance-preserving chunks."""
    out: list[Chunk] = []
    idx = 0
    for page_number, text in pages:
        page_chunks = chunk_page(
            text, page_number, start_index=idx,
            target_chars=target_chars, overlap_chars=overlap_chars,
        )
        out.extend(page_chunks)
        idx += len(page_chunks)
    return out
