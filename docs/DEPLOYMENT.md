# Deployment

## Docker Compose (recommended)

```bash
cp .env.example .env      # set APP_SECRET_KEY; optionally provider keys
docker compose up --build
```

Services: `postgres` (pgvector image), `redis`, `api` (FastAPI + OCR deps,
runs `alembic upgrade head` on start), `worker` (Celery), `web` (Next.js
standalone). Data persists in `pgdata` and `archivedata` volumes. Health checks
are defined for postgres, redis and api.

Endpoints: web `:3000`, api `:8000` (`/health`, `/ready`, `/docs`).

## Environment variables

See `.env.example`. Key ones:

| Var | Purpose |
|---|---|
| `DATABASE_URL` | Postgres DSN (`postgresql+psycopg://…`) |
| `REDIS_URL` + `JOBS_INLINE=false` | Celery jobs |
| `APP_SECRET_KEY` | encrypts provider keys at rest — set a strong value |
| `CORS_ORIGINS` | allowed browser origins (never `*`) |
| `GROQ_API_KEY` / `OPENAI_API_KEY` / … | optional provider keys |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | embeddings |
| `NEXT_PUBLIC_API_BASE_URL` | API base URL for the web app |

## Local (no Docker)

Requires Python 3.11, Node 20+, Postgres 16 + pgvector, Tesseract, Ghostscript.

```bash
make setup && cp .env.example .env && make migrate
make api   # terminal 1
make web   # terminal 2
```

## Production notes

- Put the API behind a TLS-terminating reverse proxy; add API rate limiting there.
- Set a strong `APP_SECRET_KEY`; rotating it invalidates stored encrypted keys
  (re-enter provider keys after rotation).
- Add pgvector index (IVFFlat/HNSW) and FTS GIN indexes for large corpora.
- Back up the Postgres volume and the archive data volume.
- Scale Celery workers for heavier ingestion/OCR workloads.
