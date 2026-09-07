# Contributing

## Principles (non-negotiable)

1. **Never fabricate data.** No fake documents, URLs, metadata, OCR text, search
   results, citations, or AI answers. Unknown → `NULL`/`unknown`, labelled.
2. **Provenance first.** Preserve source URL, archived URL, local path, checksum,
   retrieval date, page numbers.
3. **AI is grounded.** RAG answers only from retrieved evidence; citations are
   validated against the DB; confidence is derived from validation.
4. **Secrets stay server-side.** Never expose, log, or echo API keys.
5. **Public web only.** Never bypass auth, paywalls, robots, or protections.

## Layout & boundaries

Keep modules separated (UI / API / DB / ingestion / OCR / retrieval / AI / jobs
/ config). The UI talks to the API; the API talks to the AI service; the AI
service talks to provider adapters. Don't leak provider specifics into the UI.

## Dev setup

```bash
make setup
cp .env.example .env       # set APP_SECRET_KEY
make migrate               # against a Postgres+pgvector DB
make test                  # point DATABASE_URL at a Postgres test DB
make acceptance
```

## Tests

Add tests for new behaviour. Critical cases live in `tests/` (pipeline, search,
citations, crawler, OCR, security, RAG, API). Use synthetic fixtures only —
never commit real archival documents, and clearly label synthetic data.

## Adding things

- **Archive source** → `config/sources.yaml`.
- **AI provider** → adapter in `app/ai/providers/` + `DEFAULT_CATALOG` entry.
- **Topic/entity** → `config/taxonomy.yaml`.
- **Schema change** → `alembic revision --autogenerate` + review the migration.

## Style

Match surrounding code. Keep functions honest about failure — record errors,
don't swallow them; never mark a step succeeded unless it did.
