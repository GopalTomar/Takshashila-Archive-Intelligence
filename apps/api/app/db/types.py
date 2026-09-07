"""Portable column types.

``Vector`` uses the real pgvector column type on PostgreSQL and a JSON-encoded
list on other backends (e.g. SQLite for unit tests). Similarity search uses
pgvector operators on Postgres and an in-Python cosine fallback elsewhere —
see ``app.retrieval.vectors``.
"""
from __future__ import annotations

import json

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

try:  # pragma: no cover - import guard
    from pgvector.sqlalchemy import Vector as PgVector
    _HAS_PGVECTOR = True
except Exception:  # pragma: no cover
    PgVector = None
    _HAS_PGVECTOR = False


class Vector(TypeDecorator):
    """Embedding column: pgvector on PG, JSON list elsewhere."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int = 1024, *args, **kwargs):
        self.dimensions = dimensions
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and _HAS_PGVECTOR:
            return dialect.type_descriptor(PgVector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and _HAS_PGVECTOR:
            return list(value)
        return list(value)  # JSON stores as list

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return list(value)
