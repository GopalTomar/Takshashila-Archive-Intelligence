# Final Implementation Report

**Project:** Takshashila Archive Intelligence
**Date:** 2026-09-07
**Status:** Working end-to-end against the real stack (PostgreSQL 16 + pgvector
0.6.0 + Tesseract 5.3.4). Docker Compose provided but not brought up in this
build environment (no Docker daemon here) — stated honestly below.

This report contains actual results only. No metrics are invented.

---

## 1. What was built

A provenance-first archival intelligence and grounded-RAG research platform:

- **Backend** (FastAPI, `apps/api`): modular monolith with cleanly separated
  packages for db, storage, ingestion, ocr, retrieval, ai, jobs, security, api.
- **Frontend** (Next.js 14 + TypeScript + Tailwind, `apps/web`): Takshashila
  design-language research workstation — Home/dashboard, Archive (+Ingestion),
  Search, Ask the Archive, Collections, Timeline, Entities, Map, Research Notes,
  Settings, Document viewer, Methodology.
- **Database** (PostgreSQL + pgvector): 26 tables, Alembic migration, portable
  Vector type with SQLite fallback.
- **Ingestion**: SSRF-safe robots-aware crawler, fetcher with retries/size
  limits, dedup by checksum+URL, deterministic metadata, page-preserving
  chunking, evidence-backed topic/entity tagging, Wayback fallback, honest crawl
  reports.
- **OCR**: PyMuPDF text extraction + Tesseract OCR for scanned PDFs, with
  page-level text, confidence, and explicit failure marking.
- **Search**: hybrid (Postgres FTS + pgvector cosine), with honest degradation
  to keyword-only when embeddings are unconfigured.
- **AI**: provider abstraction (Groq, OpenAI, OpenAI-compatible, local),
  capability registry, independent embedding abstraction, grounded RAG with
  structured output, and citation validation (anti-hallucination).
- **Security**: encrypted-at-rest provider keys, SSRF guard, path-traversal
  protection, file-signature validation, secret redaction, prompt-injection
  defence.
- **Jobs**: Celery (Docker) or in-process runner (local), retryable.
- **Docs, tests, Docker, Makefile, acceptance script, manifest tooling.**

## 2. How to run it

- Docker: `cp .env.example .env` (set `APP_SECRET_KEY`), `docker compose up
  --build` → web `:3000`, api `:8000`.
- Local: `make setup && cp .env.example .env && make migrate && make api` +
  `make web`.

## 3. Environment variables required

`APP_SECRET_KEY` (required — encrypts provider keys), `DATABASE_URL`,
`CORS_ORIGINS`, optional `REDIS_URL`/`JOBS_INLINE`, optional provider keys
(`GROQ_API_KEY`, …), embedding config (`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`,
`EMBEDDING_DIMENSIONS`), `NEXT_PUBLIC_API_BASE_URL`. See `.env.example`.

## 4. Tests run & 5. Test status

Run in this session against PostgreSQL 16 + pgvector 0.6.0:

```
pytest → 44 passed
  test_api.py ............ FastAPI TestClient: health, ready, stats(empty),
                           providers-list (no key leaked), key not echoed,
                           live-crawl-requires-confirm, search availability
  test_pipeline.py ....... text PDF, empty PDF, dedup(checksum), missing metadata
                           stays NULL, non-PDF path
  test_search.py ......... keyword, no-results, honest semantic downgrade,
                           hybrid, many-docs capped to top_k
  test_citations.py ...... valid, fabricated chunk, impossible page, quote
                           mismatch, chunk-not-in-evidence
  test_crawler.py ........ normalize, fixture-server crawl+ingest, broken URL
                           recorded, SSRF/scope block, size handling
  test_ocr.py ............ real image-only PDF OCR'd via Tesseract; availability
                           reported honestly
  test_providers.py ...... no-key honest, invalid endpoint, key redacted in
                           errors, Groq default models present, not "free"
  test_rag.py ............ no-evidence returns insufficient WITHOUT calling model;
                           evidence-but-no-provider-key is honest
  test_security.py ....... SSRF (localhost/private/file), path traversal, safe
                           filename, magic-byte signatures, secret roundtrip/mask,
                           logging redaction
```

Portable fallback verified separately: `test_pipeline/search/citations/rag`
also pass against **SQLite** (17 passed).

Acceptance vertical slice (`scripts/acceptance.py`): **13/13 steps passed** —
ingest → store → checksum → metadata → text/OCR → chunk → embed(pgvector) →
index → search(hybrid) → viewer text → RAG retrieval → citation validation
(resolves to exact document+page) → save session → restart → persistence.

Frontend: `next build` → **all 14 routes compiled**, types valid; `next start`
serves Home/Ask/Settings (HTTP 200). Live API verified via curl (health, stats,
providers with masked keys, hybrid search returning results).

Backend: `compileall` clean; Alembic migration applies cleanly (27 relations).

## 6. How to configure Groq

`.env` `GROQ_API_KEY=…`, or Settings → AI Providers → Groq → Save Key → Test
Connection (real request). Select Provider=Groq, Model=GPT-OSS 120B
(`openai/gpt-oss-120b`; `openai/gpt-oss-20b` also available). Pricing/
availability depends on the provider account (not asserted by the app).

## 7. How to ingest the first real archive source

Verify specific public URLs → add to `seed_urls` for `arpi` in
`config/sources.yaml` → `POST /api/ingestion/crawl {"source_key":"arpi",
"confirm":true,"max_pages":5}` → verify download/checksum/metadata/OCR/search/
citation/viewer → widen only after verification. See `docs/INGESTION.md`.

## 8. Known limitations

- **Docker not brought up here** (no daemon in this build environment). Compose
  files + Dockerfiles are provided and internally consistent but were not
  `up`-tested in this session; verification used a locally-started Postgres 16 +
  pgvector cluster and direct uvicorn/next processes.
- **AI answer generation requires a real provider key.** With none configured,
  the system honestly reports "provider not configured" and still proves
  retrieval + citation validation; it never fabricates an answer. A live Groq
  answer was therefore not exercised in this session.
- **Live external crawl** depends on network egress policy; verified against a
  local fixture HTTP server, not a live public crawl.
- **Anthropic provider**: registry entry present; a native (non-OpenAI-shaped)
  adapter is a TODO.
- **Streaming**: adapter supports SSE streaming (`stream_chat`); the current UI
  uses the non-streaming `chat` path for validated structured output. Wiring a
  streaming UI is optional future work.
- **Map**: first-version document-linked geographic explorer (renders only
  entities with real coordinates); full GIS is a documented extension.
- **pgvector index**: for large corpora add IVFFlat/HNSW + FTS GIN indexes.
- **Reranker**: hybrid scoring is linear; a cross-encoder reranker is optional.

## 9. What was verified (in this session)

- Postgres + pgvector storage and cosine search (native operator path).
- Full ingestion pipeline incl. real Tesseract OCR of an image-only PDF.
- Deterministic metadata (unknowns kept NULL), dedup, page-preserving chunking.
- Hybrid search + honest keyword downgrade when embeddings absent.
- RAG no-evidence and no-provider paths never fabricate answers.
- Citation validation catches fabricated chunks, impossible pages, quote
  mismatches, and out-of-evidence citations.
- Security: SSRF blocks, path-traversal blocks, signature checks, secret
  encryption + redaction, no key returned by the API.
- Alembic migration applies; frontend builds and serves; live API responds.

## 10. What remains optional

Live Groq answer demo (needs a key), Docker Compose `up` in a Docker-enabled
host, streaming answer UI, native Anthropic adapter, cross-encoder reranker,
pgvector ANN index tuning, richer GIS map, and a live controlled crawl of a
verified public source.

---

## Deployment verification (2026-09-07)

The complete stack was started and tested. The Docker daemon (v29.3.1) was
started successfully and `docker compose config` validates the full topology,
but **base-image pulls are blocked** in this environment — Docker Hub / ECR /
ghcr blob CDNs return `403 Forbidden` (org egress policy). So `docker compose
up --build` cannot pull `pgvector/pgvector:pg16`, `redis:7-alpine`,
`python:3.11-slim`, `node:22-alpine` here. This is an environment/policy limit,
not a defect in the compose files.

The **equivalent native stack** (the same processes the containers wrap) was
brought up and verified end-to-end:

| Item | Result |
|---|---|
| PostgreSQL 16 + pgvector | up; `/ready` → db ok, pgvector 0.6.0 |
| Redis | up; `redis-cli ping` → PONG |
| Celery worker (Redis-backed) | connected + `celery@… ready`; processed a real crawl job |
| FastAPI | `/health` ok; `/ready` ready=true |
| Next.js (production build) | serves `http://localhost:3000` → 200 |
| Migrations | `alembic upgrade head` → 27 tables, extensions created |
| Frontend → backend | CORS `access-control-allow-origin: http://localhost:3000`; data returned |
| Backend → database | reads/writes verified |
| Worker connectivity | API → Redis → Celery → crawl → ingest → embed → DB (job `succeeded`) |
| Test suite (running-stack DB) | **44 passed** |
| Vertical slice (via HTTP) | crawl-ingest → hybrid search (pgvector+FTS, score 0.74) → document+pages → RAG retrieval + citation; AI answer honestly "provider not configured" (no key) |
| `docker compose config` | VALID |

### Real bug found and fixed during verification

The autogenerated migration created `document_chunks.embedding` as a fixed
`vector(1024)` column, so `EMBEDDING_DIMENSIONS` was silently ignored under the
migration path — any embedder whose dimension ≠ 1024 failed on insert
(`expected 1024 dimensions, not N`). **Fix:** `app/db/types.py` now emits a
**dimensionless** pgvector column (`vector`), so any configured embedding
dimension works under migrations. Re-verified: migration → column type
`vector`; 256-dim embeddings insert and search correctly; full suite green.

### Exact commands used to start the system (native, verified here)

```bash
redis-server --daemonize yes --port 6379
cd apps/api && PYTHONPATH=. DATABASE_URL=... alembic upgrade head && cd ../..
PYTHONPATH=apps/api .venv/bin/celery -A app.jobs.celery_app.celery_app worker --loglevel=info &
PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 &
cd apps/web && npm run build && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next start -p 3000 &
```

Docker path (in an egress-unrestricted host): `docker compose up --build`.
See `docs/DEPLOYMENT.md` for both paths.

### Remaining blocker

Container image pulls are blocked by egress policy in *this* build environment,
so `docker compose up --build` could not run here. On a normal host (or with a
reachable registry mirror) the documented `docker compose up --build` path is
expected to work — the compose file is valid and the identical services were
verified natively. A live Groq answer still requires a real `GROQ_API_KEY`.

---

### File inventory (high level)

- `apps/api/app/` — 40+ Python modules (db, storage, ingestion, ocr, retrieval,
  ai + providers, jobs, api routers, security, seed, bootstrap, config).
- `apps/api/alembic/` — migration env + initial schema revision.
- `apps/web/app/` — 13 route pages + components (Shell, ModelSelector,
  ModelContext, Logo, ui) + api client.
- `config/` — sources.yaml, taxonomy.yaml.
- `docs/` — 17 documents.
- `tests/` — 9 test modules (44 tests) + conftest with fixture server.
- `scripts/` — acceptance.py, generate_manifest.py.
- Docker: `docker-compose.yml`, `apps/api/Dockerfile`, `apps/web/Dockerfile`.
- `.env.example`, `.gitignore`, `Makefile`, `README.md`.
