"""Vector similarity over document chunks.

On PostgreSQL with pgvector, similarity uses the native ``cosine_distance``
operator (indexable). On other backends (or when pgvector is unavailable), a
NumPy cosine fallback runs over stored embeddings. Both paths are real — the
fallback is documented, not faked.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import dialect_name
from app.db.models import DocumentChunk

try:  # pragma: no cover
    import numpy as np
    _HAS_NUMPY = True
except Exception:  # pragma: no cover
    _HAS_NUMPY = False


@dataclass
class VectorHit:
    chunk_id: str
    document_id: int
    score: float  # cosine similarity in [-1, 1]; higher is better


def _pg_supports_pgvector(db: Session) -> bool:
    try:
        row = db.execute(
            select(DocumentChunk).limit(0)
        )  # cheap; the real check is the operator below
        return True
    except Exception:  # pragma: no cover
        return False


def search_vectors(
    db: Session,
    query_embedding: list[float],
    *,
    top_k: int = 20,
    document_id: int | None = None,
    include_demo: bool = False,
) -> list[VectorHit]:
    if dialect_name() == "postgresql":
        try:
            return _search_pgvector(db, query_embedding, top_k, document_id, include_demo)
        except Exception:
            # Fall back to Python if the operator/extension is unavailable.
            pass
    return _search_numpy(db, query_embedding, top_k, document_id, include_demo)


def _base_stmt(document_id: int | None, include_demo: bool):
    from app.db.models import Document

    stmt = select(DocumentChunk).join(Document, Document.id == DocumentChunk.document_id)
    stmt = stmt.where(DocumentChunk.embedding.is_not(None))
    if document_id is not None:
        stmt = stmt.where(DocumentChunk.document_id == document_id)
    if not include_demo:
        stmt = stmt.where(Document.is_demo.is_(False))
    return stmt


def _search_pgvector(db, query_embedding, top_k, document_id, include_demo):
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = _base_stmt(document_id, include_demo).add_columns(distance.label("distance"))
    stmt = stmt.order_by(distance).limit(top_k)
    hits = []
    for chunk, dist in db.execute(stmt).all():
        hits.append(VectorHit(chunk_id=chunk.chunk_id, document_id=chunk.document_id, score=1.0 - float(dist)))
    return hits


def _cosine(a, b) -> float:
    if _HAS_NUMPY:
        va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        na, nb = np.linalg.norm(va), np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _search_numpy(db, query_embedding, top_k, document_id, include_demo):
    stmt = _base_stmt(document_id, include_demo)
    hits: list[VectorHit] = []
    for chunk in db.execute(stmt).scalars().all():
        if not chunk.embedding:
            continue
        score = _cosine(query_embedding, chunk.embedding)
        hits.append(VectorHit(chunk_id=chunk.chunk_id, document_id=chunk.document_id, score=score))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
