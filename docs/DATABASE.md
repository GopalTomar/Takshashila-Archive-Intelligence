# Database

PostgreSQL 16 with the `vector` (pgvector) and `pg_trgm` extensions is the
production target. SQLite is supported for quick local tests (with portable
fallbacks for FTS and vector search).

## Migrations

Alembic owns the schema in production.

```bash
cd apps/api
PYTHONPATH=. alembic upgrade head      # apply
PYTHONPATH=. alembic revision --autogenerate -m "message"   # new migration
```

`alembic/env.py` ensures `CREATE EXTENSION vector` / `pg_trgm` before running on
PostgreSQL. The Docker `api` service runs `alembic upgrade head` on startup.

For SQLite or ephemeral test runs the app can also create tables directly via
`app.bootstrap.init_db()` (used by the test suite and on API startup as a safety
net); production relies on migrations.

## Integrity

- Foreign keys everywhere (enforced on SQLite via `PRAGMA foreign_keys=ON`).
- Unique constraints: `documents.document_id`, `document_chunks.chunk_id`,
  `(document_id, page_number)`, `(entity_type, name)`, `(provider_id, model_id)`.
- Indexes on `sha256`, `document_id`, foreign keys, `job_type`, entity name/type.
- Transactions: the ingestion pipeline flushes per step and the caller commits;
  crawl runs commit incrementally so partial progress is never lost.

## Extensions

| Extension | Use |
|---|---|
| `vector` (pgvector) | embedding column + cosine distance search |
| `pg_trgm` | fuzzy text matching support |

## Embedding column dimension

`document_chunks.embedding` is a **dimensionless** pgvector column (`vector`,
no length modifier). This is deliberate: `EMBEDDING_DIMENSIONS` is configurable
per deployment (a Groq/OpenAI/local embedder may emit 256, 1024, 1536, … dims),
so the schema must not pin a single dimension. A dimensionless column accepts
whatever the configured embedder emits, and the cosine-distance operator works
because every row shares one dimension (a single configured embedder). To add
an ANN index (IVFFlat/HNSW) for a large corpus, first pin the column to your
embedder's dimension in a follow-up migration, then create the index.

See [`DATA_MODEL.md`](DATA_MODEL.md) for the full table list.
