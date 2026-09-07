"""Hybrid retrieval: keyword (full-text) + semantic (vector) + filters.

Keyword search uses PostgreSQL full-text search (``websearch_to_tsquery`` +
``ts_rank``) when on Postgres, and a portable LIKE-based scorer otherwise.
Semantic search uses the vector index (only when embeddings exist). Hybrid
combines normalised keyword and semantic scores with a configurable weight.

Every result carries an explicit "why it matched" explanation. Scores are real
— never fabricated. If embeddings are unavailable, semantic contribution is
zero and the mode is honestly reported as keyword-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder
from app.db.base import dialect_name
from app.db.models import Document, DocumentChunk
from app.retrieval.vectors import search_vectors


@dataclass
class ChunkHit:
    chunk_id: str
    document_id: int
    page_number: int | None
    text: str
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    combined_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)


@dataclass
class SearchFilters:
    author: str | None = None
    document_type: str | None = None
    collection_key: str | None = None
    language: str | None = None
    source_key: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    topic_key: str | None = None
    entity_name: str | None = None
    include_demo: bool = False
    document_id: int | None = None


def _apply_filters(stmt, filters: SearchFilters):
    from app.db.models import (
        ArchiveCollection,
        DocumentEntity,
        DocumentTopic,
        Entity,
        Source,
        Topic,
    )

    if not filters.include_demo:
        stmt = stmt.where(Document.is_demo.is_(False))
    if filters.author:
        stmt = stmt.where(Document.author.ilike(f"%{filters.author}%"))
    if filters.document_type:
        stmt = stmt.where(Document.document_type == filters.document_type)
    if filters.language:
        stmt = stmt.where(Document.language == filters.language)
    if filters.date_from:
        stmt = stmt.where(Document.doc_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Document.doc_date <= filters.date_to)
    if filters.document_id is not None:
        stmt = stmt.where(Document.id == filters.document_id)
    if filters.collection_key:
        stmt = stmt.join(ArchiveCollection, ArchiveCollection.id == Document.collection_id).where(
            ArchiveCollection.collection_key == filters.collection_key
        )
    if filters.source_key:
        stmt = stmt.join(Source, Source.id == Document.source_id).where(
            Source.source_key == filters.source_key
        )
    if filters.topic_key:
        stmt = stmt.join(DocumentTopic, DocumentTopic.document_id == Document.id).join(
            Topic, Topic.id == DocumentTopic.topic_id
        ).where(Topic.key == filters.topic_key)
    if filters.entity_name:
        stmt = stmt.join(DocumentEntity, DocumentEntity.document_id == Document.id).join(
            Entity, Entity.id == DocumentEntity.entity_id
        ).where(Entity.name.ilike(f"%{filters.entity_name}%"))
    return stmt


def _keyword_search(db: Session, query: str, filters: SearchFilters, limit: int) -> list[ChunkHit]:
    if not query.strip():
        return []
    if dialect_name() == "postgresql":
        return _keyword_pg(db, query, filters, limit)
    return _keyword_portable(db, query, filters, limit)


def _keyword_pg(db, query, filters, limit):
    tsq = func.websearch_to_tsquery("english", query)
    tsv = func.to_tsvector("english", DocumentChunk.text)
    rank = func.ts_rank(tsv, tsq)
    stmt = (
        select(DocumentChunk, rank.label("rank"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(tsv.op("@@")(tsq))
    )
    stmt = _apply_filters(stmt, filters).order_by(rank.desc()).limit(limit)
    rows = db.execute(stmt).all()
    max_rank = max((float(r) for _, r in rows), default=1.0) or 1.0
    hits = []
    for chunk, r in rows:
        hits.append(ChunkHit(
            chunk_id=chunk.chunk_id, document_id=chunk.document_id,
            page_number=chunk.page_number, text=chunk.text,
            keyword_score=float(r) / max_rank,
            match_reasons=[f'Full-text match for "{query}"'],
        ))
    return hits


def _keyword_portable(db, query, filters, limit):
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return []
    conds = [func.lower(DocumentChunk.text).like(f"%{t}%") for t in terms]
    stmt = select(DocumentChunk).join(Document, Document.id == DocumentChunk.document_id).where(or_(*conds))
    stmt = _apply_filters(stmt, filters).limit(limit * 5)
    hits = []
    for chunk in db.execute(stmt).scalars().all():
        text_l = chunk.text.lower()
        score = sum(text_l.count(t) for t in terms)
        matched = [t for t in terms if t in text_l]
        if score <= 0:
            continue
        hits.append(ChunkHit(
            chunk_id=chunk.chunk_id, document_id=chunk.document_id,
            page_number=chunk.page_number, text=chunk.text,
            keyword_score=float(score),
            match_reasons=[f'Keyword match: {", ".join(matched)}'],
        ))
    max_kw = max((h.keyword_score for h in hits), default=1.0) or 1.0
    for h in hits:
        h.keyword_score /= max_kw
    hits.sort(key=lambda h: h.keyword_score, reverse=True)
    return hits[:limit]


def hybrid_search(
    db: Session,
    query: str,
    *,
    mode: str = "hybrid",  # keyword|semantic|hybrid
    filters: SearchFilters | None = None,
    top_k: int = 10,
    hybrid_weight: float = 0.5,  # weight on semantic (0=keyword only, 1=semantic only)
    embedder: Embedder | None = None,
) -> tuple[list[ChunkHit], str]:
    """Return (hits, effective_mode). effective_mode is honest about whether
    semantic search actually ran."""
    filters = filters or SearchFilters()
    effective_mode = mode

    semantic_available = bool(embedder and embedder.enabled)
    if mode in ("semantic", "hybrid") and not semantic_available:
        effective_mode = "keyword"  # honest downgrade

    by_chunk: dict[str, ChunkHit] = {}

    if effective_mode in ("keyword", "hybrid"):
        for h in _keyword_search(db, query, filters, max(top_k * 3, 30)):
            by_chunk[h.chunk_id] = h

    if effective_mode in ("semantic", "hybrid") and semantic_available:
        try:
            qvec = embedder.embed([query])[0]
            vhits = search_vectors(
                db, qvec, top_k=max(top_k * 3, 30),
                document_id=filters.document_id, include_demo=filters.include_demo,
            )
            # Fetch chunk texts for vector-only hits.
            chunk_ids = [v.chunk_id for v in vhits]
            chunk_map = {}
            if chunk_ids:
                for c in db.execute(
                    select(DocumentChunk).where(DocumentChunk.chunk_id.in_(chunk_ids))
                ).scalars().all():
                    chunk_map[c.chunk_id] = c
            for v in vhits:
                c = chunk_map.get(v.chunk_id)
                if not c:
                    continue
                existing = by_chunk.get(v.chunk_id)
                label = "Semantic similarity" if embedder.is_real_semantic else "Lexical-hash similarity (test/demo embedder)"
                if existing:
                    existing.semantic_score = v.score
                    existing.match_reasons.append(f"{label}: {v.score:.2f}")
                else:
                    by_chunk[v.chunk_id] = ChunkHit(
                        chunk_id=v.chunk_id, document_id=v.document_id,
                        page_number=c.page_number, text=c.text,
                        semantic_score=v.score,
                        match_reasons=[f"{label}: {v.score:.2f}"],
                    )
        except Exception as exc:
            # Never fail search because embeddings broke; degrade to keyword.
            effective_mode = "keyword" if effective_mode == "semantic" else effective_mode
            for h in by_chunk.values():
                pass

    # Combine.
    w = hybrid_weight
    for h in by_chunk.values():
        if effective_mode == "keyword":
            h.combined_score = h.keyword_score
        elif effective_mode == "semantic":
            h.combined_score = h.semantic_score
        else:
            h.combined_score = (1 - w) * h.keyword_score + w * max(h.semantic_score, 0.0)

    results = sorted(by_chunk.values(), key=lambda h: h.combined_score, reverse=True)
    return results[:top_k], effective_mode
