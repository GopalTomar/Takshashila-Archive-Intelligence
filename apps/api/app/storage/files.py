"""Provenance-aware document storage.

Layout (originals are never overwritten):

    data/store/<document_id>/original/<safe_name>
    data/store/<document_id>/ocr/<name>
    data/store/<document_id>/text/<name>
    data/store/<document_id>/images/<name>
    data/store/<document_id>/derived/<name>
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.security.files import ensure_within, safe_filename

ROLES = ("original", "ocr", "text", "images", "derived", "archived", "thumbnail")


def store_root() -> Path:
    root = get_settings().data_path / "store"
    root.mkdir(parents=True, exist_ok=True)
    return root


def document_dir(document_id: str) -> Path:
    safe_id = safe_filename(document_id)
    d = store_root() / safe_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def save_bytes(document_id: str, role: str, filename: str, data: bytes) -> dict:
    """Write bytes to the document's role directory (never overwriting an
    existing original). Returns a dict with path, size, sha256, computed_at."""
    if role not in ROLES:
        raise ValueError(f"unknown storage role: {role}")
    base = document_dir(document_id) / role
    base.mkdir(parents=True, exist_ok=True)
    target = ensure_within(base, Path(safe_filename(filename)))

    if role == "original" and target.exists():
        # Preserve the original: refuse to overwrite; version the new arrival.
        stem, suffix = target.stem, target.suffix
        n = 1
        while target.exists():
            target = base / f"{stem}.v{n}{suffix}"
            n += 1

    with open(target, "wb") as fh:
        fh.write(data)

    return {
        "local_path": str(target),
        "file_size": len(data),
        "sha256": sha256_bytes(data),
        "checksum_algo": "sha256",
        "checksum_computed_at": datetime.now(timezone.utc),
    }
