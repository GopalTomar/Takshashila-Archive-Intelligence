"""Search: keyword, hybrid, no-results, many-results, semantic honesty."""
from __future__ import annotations

from conftest import make_text_pdf

from app.ai.embeddings import Embedder, get_embedder
from app.ingestion.pipeline import ingest_document_bytes
from app.retrieval.search import SearchFilters, hybrid_search


def _ingest(db, source, text, url):
    return ingest_document_bytes(db, source=source, content=make_text_pdf([text]),
                                 source_url=url, filename=url.split("/")[-1], is_demo=True)


def test_keyword_search_finds_match(db, demo_source):
    _ingest(db, demo_source, "The Aksai Chin plateau and Ladakh border.", "http://x/1.pdf")
    _ingest(db, demo_source, "Unrelated document about maritime trade.", "http://x/2.pdf")
    db.commit()
    hits, mode = hybrid_search(db, "Aksai Chin", mode="keyword",
                               filters=SearchFilters(include_demo=True), top_k=5)
    assert hits
    assert any("Aksai" in h.text for h in hits)


def test_no_results_returns_empty(db, demo_source):
    _ingest(db, demo_source, "Aksai Chin note.", "http://x/1.pdf")
    db.commit()
    hits, mode = hybrid_search(db, "zzzznonexistentterm12345", mode="keyword",
                               filters=SearchFilters(include_demo=True), top_k=5)
    assert hits == []


def test_semantic_downgrades_honestly_when_disabled(db, demo_source):
    _ingest(db, demo_source, "Tibet and the Dalai Lama.", "http://x/1.pdf")
    db.commit()
    disabled = Embedder(provider="none", model=None, dimensions=256)
    hits, mode = hybrid_search(db, "Tibet", mode="semantic",
                               filters=SearchFilters(include_demo=True), top_k=5, embedder=disabled)
    # Honest downgrade: mode reported as keyword, not faked as semantic.
    assert mode == "keyword"


def test_hybrid_with_embedder_reports_hybrid(db, demo_source):
    _ingest(db, demo_source, "Aksai Chin frontier and the 1962 war.", "http://x/1.pdf")
    db.commit()
    emb = get_embedder(db)  # hash embedder in tests
    hits, mode = hybrid_search(db, "border conflict 1962", mode="hybrid",
                               filters=SearchFilters(include_demo=True), top_k=5, embedder=emb)
    assert mode == "hybrid"


def test_many_documents_stay_responsive(db, demo_source):
    for i in range(60):
        _ingest(db, demo_source, f"Document {i} about India China border and Tibet.", f"http://x/{i}.pdf")
    db.commit()
    hits, mode = hybrid_search(db, "border", mode="keyword",
                               filters=SearchFilters(include_demo=True), top_k=10)
    assert len(hits) == 10  # capped to top_k
