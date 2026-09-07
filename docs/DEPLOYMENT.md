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

## Deployment verification

The stack has been verified service-by-service. Two paths:

### A. Docker Compose (the documented target)

```bash
cp .env.example .env            # set APP_SECRET_KEY
docker compose config           # validate topology (no pull needed) — should print the merged config
docker compose up --build       # build + start postgres, redis, api, worker, web
curl http://localhost:8000/health
curl http://localhost:8000/ready
open http://localhost:3000
```

`docker compose config` validates the compose file (services, env, healthchecks,
ports, volumes, dependencies). `up --build` pulls the base images
(`pgvector/pgvector:pg16`, `redis:7-alpine`, `python:3.11-slim`,
`node:22-alpine`) from Docker Hub and builds the app images — requires outbound
access to the container registry.

> **Restricted-egress environments:** if your network blocks the container
> image CDN (Docker Hub / ECR / ghcr blob storage), `up --build` cannot pull
> base images. In that case either configure a reachable registry mirror, or
> run the equivalent native stack below (same processes the containers wrap).

### B. Native stack (no Docker) — equivalent services, verified

```bash
# 1) Postgres 16 + pgvector running and reachable via DATABASE_URL
# 2) Redis running (for the Celery worker)
redis-server --daemonize yes --port 6379

# 3) Migrations
cd apps/api && PYTHONPATH=. alembic upgrade head && cd ../..

# 4) Celery worker (Redis-backed; REDIS_URL set, JOBS_INLINE=false)
PYTHONPATH=apps/api .venv/bin/celery -A app.jobs.celery_app.celery_app worker --loglevel=info &

# 5) API
PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 6) Web (built)
cd apps/web && npm run build && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next start -p 3000 &
```

Verify:

```bash
curl http://localhost:8000/health     # {"status":"ok",...}
curl http://localhost:8000/ready       # database ok, pgvector available, ocr, jobs backend=celery
curl -X POST http://localhost:8000/api/ingestion/crawl -d '{"source_key":"fixtures"}' -H 'Content-Type: application/json'
#   -> job runs on the Celery worker; poll GET /api/ingestion/jobs/<id> until "succeeded"
curl "http://localhost:8000/api/stats?include_demo=true"     # real counts
```

Set `EMBEDDING_DIMENSIONS` to match your embedder; the DB column is
dimensionless so any value works (see DATABASE.md).

## Production notes

- Put the API behind a TLS-terminating reverse proxy; add API rate limiting there.
- Set a strong `APP_SECRET_KEY`; rotating it invalidates stored encrypted keys
  (re-enter provider keys after rotation).
- Add pgvector index (IVFFlat/HNSW) and FTS GIN indexes for large corpora.
- Back up the Postgres volume and the archive data volume.
- Scale Celery workers for heavier ingestion/OCR workloads.
