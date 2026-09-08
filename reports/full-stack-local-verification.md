# Full-Stack Local Verification

**Date:** 2026-09-08
**Verification environment:** remote cloud **Linux** sandbox (not the user's
Windows machine). PostgreSQL 16 + pgvector 0.6.0, Redis 7, Tesseract 5.3.4 are
installed here, so the full production pipeline was run and verified **natively**
(the same processes the containers wrap). Docker **image pulls are egress-blocked
in this sandbox**, so `docker compose up --build` could not be executed here —
that remains the user's Windows Docker Desktop test. Nothing below is fabricated;
credential-gated steps are marked `NOT TESTED` with the reason.

Legend: **PASS** = executed and verified · **NOT TESTED** = could not run here,
reason given · **FAIL** = executed and failed.

---

## Environment

| Item | Value |
|---|---|
| Python (sandbox) | 3.11.15 (user's Windows: 3.14.3) |
| Node (sandbox) | 22.22.2 (user's Windows: 24.14.0) |
| Docker (sandbox) | 29.3.1 CLI; daemon startable; **registry egress blocked** |
| Docker Compose | v5.1.1 (sandbox); user's Windows: 5.5.0 |
| PostgreSQL | 16.13 |
| pgvector | 0.6.0 |
| pg_trgm | 1.6 |
| Redis | 7.0.15 |
| Tesseract | 5.3.4 |
| Next.js | 15.5.25 (upgraded from 14.2.15) |
| React | 19.0.8 (upgraded from 18.3.1) |

## Results

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | Docker Compose config valid | PASS | `docker compose config` -> VALID |
| 2 | Docker `up --build` (containers) | NOT TESTED | sandbox registry egress blocks Docker Hub image pulls (403). Run on Windows Docker Desktop. |
| 3 | PostgreSQL connection | PASS | `/ready` database ok, dialect=postgresql |
| 4 | pgvector available | PASS | `/ready` pgvector available, version 0.6.0 |
| 5 | pg_trgm available | PASS | extension present (1.6) |
| 6 | Alembic migrations | PASS | `alembic upgrade head` -> 27 tables, extensions created |
| 7 | Redis connectivity | PASS | `/ready` redis connected=true; `redis-cli ping`=PONG |
| 8 | Celery worker | PASS | `/ready` worker running=true (1 worker); connected to Redis |
| 9 | FastAPI `/health` | PASS | 200 `{"status":"ok"}` |
| 10 | FastAPI `/ready` | PASS | ready=true (db, pgvector, redis, worker, embeddings, ocr, jobs) |
| 11 | Worker path (API->Redis->Celery->DB) | PASS | crawl job dispatched via API, processed by worker, status=succeeded, 1 PDF ingested |
| 12 | Real document ingestion (controlled) | PASS | `scripts/verify_full_stack.py`: PILOT-00002, SHA-256, 2 pages |
| 13 | PDF extraction (PyMuPDF) | PASS | page 1 native text (source=embedded) |
| 14 | OCR (real Tesseract) | PASS | page 2 image-only -> source=ocr, text recovered ("HIMALAYA/1962") |
| 15 | Per-page OCR (mixed doc) | PASS | native page preserved, only scanned page OCR'd (new behavior + test) |
| 16 | Page-preserving chunks | PASS | 2 chunks, each bound to its page |
| 17 | Embeddings generated + stored | PASS (hash embedder) | 2/2 chunks embedded, dims=256 |
| 18 | Vector stored in pgvector | PASS | queried back: `vector_dims`=256 |
| 19 | Keyword search | PASS | returns the document |
| 20 | Semantic search (pgvector) | PASS (hash embedder) | vector retrieval returns the document |
| 21 | Hybrid search (keyword+vector) | PASS | effective mode hybrid; top hit kw=1.0, sem=0.77 |
| 22 | Citation resolves to document+page | PASS | PILOT-00002 p.1, confidence=supported |
| 23 | Dashboard stats (live DB) | PASS | 1 non-demo doc, 2 pages, 2 chunks, 2 embeddings, ocr=1, indexed=1, ingestion_jobs=1, crawl_jobs=1 |
| 24 | Dashboard distributions | PASS | by_year=[1962], ocr_status/index_status/sources populated from DB |
| 25 | Frontend build | PASS | `next build` (Next 15) -> all routes compiled |
| 26 | Frontend serves | PASS | pages / /ask /search /archive /settings /timeline /entities /documents/[id] -> 200 |
| 27 | CORS frontend<->backend | PASS | `access-control-allow-origin: http://localhost:3000` |
| 28 | Real semantic embedding provider | NOT TESTED | no embedding API key/local model available; hash embedder used to exercise pgvector mechanics (clearly labelled not-semantic) |
| 29 | Groq live authenticated request | NOT TESTED | `GROQ_API_KEY` not configured in sandbox |
| 30 | RAG grounded answer via Groq | NOT TESTED | needs Groq key; retrieval + citation validation verified independently |
| 31 | Real internet PDF download | NOT TESTED | sandbox egress blocks external hosts (403 CONNECT). A local genuine PDF fixture was used for the pipeline test. |
| 32 | npm audit | PASS | **0 vulnerabilities** after Next 15.5.25 + React 19 + postcss 8.5.28 override |
| 33 | Python test suite | PASS | **48 passed** (44 existing + 4 new: dashboard stats, distributions, per-page OCR) |

## Security note (npm audit)

`npm audit` on Next 14.2.15 reported 1 critical (postcss) + high (Next.js). The
npm advisory range flags **all** Next.js versions up to 15.5.20, so no 14.2.x
patch clears it and `npm audit fix --force` would jump to next@16 (breaking).
Resolution applied: upgraded to **Next 15.5.25 + React 19.0.8** (the supported
line above the vulnerable range) and pinned **postcss 8.5.28** via an `overrides`
entry. Result: `npm audit` -> **found 0 vulnerabilities**; `next build` and a
runtime serve of all routes pass. The Next 15 upgrade was verified by build +
route serving; the app uses only client-side App-Router hooks (no Server
Actions, custom server, i18n middleware, Image Optimizer remotePatterns, or
rewrites), which is why the residual advisories were low-exposure and the
migration was low-risk.

## What changed in this pass (code)

- `apps/api/app/api/routers/stats.py` — added real counts (chunks, embeddings,
  ingestion_jobs, crawl_jobs, job breakdown) and a new
  `/api/stats/distributions` endpoint (by year, type, OCR/index/embedding
  status, sources) — all live DB queries.
- `apps/api/app/api/routers/health.py` — `/ready` now checks Redis and the
  Celery worker.
- `apps/api/app/ocr/pdf.py` — per-page OCR: native-text pages preserved, only
  low-text pages OCR'd; per-page source recorded.
- `apps/web/app/page.tsx` + `app/lib/api.ts` — dashboard shows live stats,
  restrained bar charts (with "No data available" empty states), full system
  health (db/pgvector/redis/worker/embeddings/ocr/jobs), and an include-demo
  toggle.
- `apps/web/package.json` — Next 15.5.25, React 19.0.8, postcss 8.5.28 override.
- `scripts/verify_full_stack.py` — controlled real-document acceptance test.

## Not done (by instruction)

- No Claude Arpi discovery, download, or ingestion (deferred to the source-
  inventory stage per the directive).
- No forced/breaking dependency changes beyond the reviewed Next 15 upgrade.

## Honest status

The full production pipeline (PostgreSQL + pgvector + Redis + Celery + OCR +
embeddings + ingestion + hybrid search + citation validation) is **verified
working natively**. Docker containerization, a real semantic-embedding provider,
and live Groq generation are **NOT TESTED here** for the environmental/credential
reasons stated and must be confirmed on the user's Windows machine (Docker) and
with real keys (embeddings/Groq). This is **not** declared "production ready" —
it is a verified end-to-end local system with the three gated items outstanding.
