"""Safe file handling: filename sanitisation, path-traversal prevention,
and content-signature (magic-byte) validation. Filename extensions are never
trusted on their own.
"""
from __future__ import annotations

import re
from pathlib import Path

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

# Magic byte signatures we accept for downloaded documents.
_SIGNATURES = {
    "application/pdf": [b"%PDF-"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/tiff": [b"II*\x00", b"MM\x00*"],
}


def safe_filename(name: str, default: str = "file") -> str:
    name = name.strip().replace("\x00", "")
    name = _SAFE_CHARS.sub("_", name)
    name = name.strip("._") or default
    return name[:200]


def ensure_within(base: Path, target: Path) -> Path:
    """Resolve ``target`` and ensure it stays within ``base``. Raises on
    traversal (``..``) attempts."""
    base_r = base.resolve()
    target_r = (base / target).resolve() if not target.is_absolute() else target.resolve()
    if base_r != target_r and base_r not in target_r.parents:
        raise ValueError(f"path traversal blocked: {target}")
    return target_r


def sniff_mime(data: bytes) -> str | None:
    """Return a MIME type from magic bytes, or None if unrecognised."""
    for mime, sigs in _SIGNATURES.items():
        for sig in sigs:
            if data.startswith(sig):
                return mime
    return None


def validate_signature(data: bytes, expected_mime: str) -> bool:
    sigs = _SIGNATURES.get(expected_mime)
    if not sigs:
        return False
    return any(data.startswith(sig) for sig in sigs)
