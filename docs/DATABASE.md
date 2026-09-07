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

See [`DATA_MODEL.md`](DATA_MODEL.md) for the full table list.
