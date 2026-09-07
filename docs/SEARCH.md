# Search

Implemented in `app/retrieval/search.py` and `app/retrieval/vectors.py`.

## Modes

- **Keyword** — PostgreSQL full-text search (`websearch_to_tsquery` + `ts_rank`)
  on Postgres; a portable `LIKE` term-frequency scorer on other backends.
- **Semantic** — embedding similarity over `document_chunks.embedding`. On
  Postgres+pgvector this uses the native `cosine_distance` operator; elsewhere a
  NumPy cosine fallback. Runs **only** when an embedder is configured.
- **Hybrid** (default) — combines normalised keyword and semantic scores:
  `combined = (1 − w)·keyword + w·semantic`, where `w` is the hybrid weight
  (Settings → Retrieval).

## Honest degradation

If semantic search is requested but no embedder is configured, the effective
mode is reported as `keyword` (never faked as semantic). The API's `/api/search`
response includes `requested_mode`, `effective_mode`, and `semantic_available`.

## Filters (spec 25)

`author, document_type, collection_key, language, source_key, date_from,
date_to, topic_key, entity_name, include_demo, document_id`.

## Result explanation (spec 66)

Every hit includes `match_reasons` (e.g. `Full-text match for "…"`,
`Semantic similarity: 0.87`) and real per-signal scores — never fabricated.

## Scale

Keyword candidates are retrieved first and re-ranked; results are capped to
`top_k`. For large archives, add a pgvector index (IVFFlat/HNSW) on
`document_chunks.embedding` and standard GIN indexes for FTS; server-side
filtering and pagination keep queries responsive.
