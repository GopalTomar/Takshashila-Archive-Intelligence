"""Symmetric encryption for secrets at rest (provider API keys).

Keys entered via the UI are stored encrypted with a Fernet key derived from
``APP_SECRET_KEY``. They are never returned by the API and never logged. The
API only ever exposes a boolean ``has_key`` plus a masked hint.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    secret = get_settings().app_secret_key.encode("utf-8")
    # Derive a stable 32-byte urlsafe key from the app secret.
    digest = hashlib.sha256(secret).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    if plaintext is None:
        raise ValueError("cannot encrypt None")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover
        raise ValueError("could not decrypt secret (wrong APP_SECRET_KEY?)") from exc


def mask_secret(plaintext: str) -> str:
    """Return a non-reversible hint, e.g. '****abcd', for display only."""
    if not plaintext:
        return ""
    tail = plaintext[-4:] if len(plaintext) >= 4 else ""
    return f"****{tail}"
