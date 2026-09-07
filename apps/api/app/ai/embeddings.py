"""Embedding abstraction — independent from the chat model.

Providers:
  * none   -> embeddings disabled; semantic search is OFF (keyword still works)
  * hash   -> deterministic, offline, LABELLED pseudo-embedding for tests/demo.
              This is NOT a semantic model; it is clearly reported as such and
              must never be presented as real semantic search quality.
  * openai / openai_compatible / local / groq -> real provider embeddings.

The application reports semantic search as enabled ONLY when a usable embedder
is configured. It never fakes semantic availability.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.registry import build_provider
from app.config import get_settings


@dataclass
class EmbedderStatus:
    enabled: bool
    provider: str
    model: str | None
    dimensions: int
    is_real_semantic: bool
    detail: str


class Embedder:
    def __init__(self, provider: str, model: str | None, dimensions: int, db: Session | None = None):
        self.provider = provider
        self.model = model
        self.dimensions = dimensions
        self._db = db

    @property
    def enabled(self) -> bool:
        return self.provider != "none"

    @property
    def is_real_semantic(self) -> bool:
        return self.provider not in ("none", "hash")

    def status(self) -> EmbedderStatus:
        detail = {
            "none": "No embedding provider configured. Semantic search disabled; keyword search available.",
            "hash": "Deterministic offline hash embedder (TEST/DEMO ONLY — not a semantic model).",
        }.get(self.provider, f"Provider embeddings via {self.provider}.")
        return EmbedderStatus(
            enabled=self.enabled, provider=self.provider, model=self.model,
            dimensions=self.dimensions, is_real_semantic=self.is_real_semantic, detail=detail,
        )

    def _hash_embed_one(self, text: str) -> list[float]:
        # Deterministic bag-of-hashed-tokens vector. Offline, reproducible.
        vec = [0.0] * self.dimensions
        for token in (text or "").lower().split():
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimensions
            vec[idx] += 1.0
        # L2 normalise.
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.enabled:
            raise RuntimeError("embeddings are disabled (EMBEDDING_PROVIDER=none)")
        if self.provider == "hash":
            return [self._hash_embed_one(t) for t in texts]
        if self._db is None:
            raise RuntimeError("provider embeddings require a DB session for credentials")
        provider = build_provider(self._db, self.provider)
        if not self.model:
            raise RuntimeError("no embedding model configured")
        return provider.embed(texts, model=self.model)


def get_embedder(db: Session | None = None) -> Embedder:
    s = get_settings()
    return Embedder(
        provider=s.embedding_provider,
        model=s.embedding_model or None,
        dimensions=s.embedding_dimensions,
        db=db,
    )
