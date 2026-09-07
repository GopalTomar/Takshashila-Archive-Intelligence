"""Search endpoint (keyword / semantic / hybrid)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedder
from app.db.base import get_db
from app.db.models import Document
from app.retrieval.search import SearchFilters, hybrid_search
from app.schemas import SearchRequest

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
def search(req: SearchRequest, db: Session = Depends(get_db)) -> dict:
    embedder = get_embedder(db)
    filters = SearchFilters(**req.filters.model_dump())
    hits, effective_mode = hybrid_search(
        db, req.query, mode=req.mode, filters=filters,
        top_k=req.top_k, hybrid_weight=req.hybrid_weight, embedder=embedder,
    )
    doc_ids = {h.document_id for h in hits}
    docs = {d.id: d for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()} if doc_ids else {}

    results = []
    for h in hits:
        d = docs.get(h.document_id)
        results.append({
            "document_id": d.document_id if d else None,
            "title": d.title if d else None,
            "author": d.author if d else None,
            "date": d.doc_date if d else None,
            "document_type": d.document_type if d else None,
            "source_url": d.source_url if d else None,
            "is_demo": d.is_demo if d else None,
            "page": h.page_number,
            "chunk_id": h.chunk_id,
            "matched_passage": h.text[:500],
            "keyword_score": round(h.keyword_score, 4),
            "semantic_score": round(h.semantic_score, 4),
            "combined_score": round(h.combined_score, 4),
            "match_reasons": h.match_reasons,
        })

    return {
        "query": req.query,
        "requested_mode": req.mode,
        "effective_mode": effective_mode,
        "semantic_available": embedder.enabled,
        "count": len(results),
        "results": results,
        "note": (
            "Semantic search unavailable (no embedding provider configured); "
            "results are keyword-only."
            if req.mode != "keyword" and not embedder.enabled else None
        ),
    }
