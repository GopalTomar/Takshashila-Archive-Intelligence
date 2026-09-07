# Architecture

## Overview

Takshashila Archive Intelligence is a **modular monolith** backend (FastAPI)
plus a **Next.js** frontend, backed by **PostgreSQL + pgvector**, with
background work on **Celery/Redis** (or an in-process runner for local dev).

```
Browser (Next.js)  ──HTTP──▶  FastAPI API  ──▶  PostgreSQL + pgvector
                                   │
                                   ├── ingestion (crawler, fetcher, pipeline)
                                   ├── ocr (PyMuPDF, Tesseract)
                                   ├── retrieval (FTS + vector, hybrid)
                                   ├── ai (provider adapters, RAG, citations)
                                   └── jobs (Celery / in-process)  ──▶ Redis
                                   │
                                   └── storage (data/ volume)  ──▶ AI providers (Groq, ...)
```

The browser **never** talks to AI providers; the API holds keys server-side.

## Why a modular monolith

The brief calls for strict module separation (UI, API, DB, ingestion,
processing, OCR, retrieval, AI, jobs, config). A single deployable with clean
internal packages delivers that separation without multi-service operational
overhead. Boundaries are enforced by package structure and interfaces
(`app.ai.base.AIProvider`, the storage layer, the retrieval layer). The pieces
could be split into separate services later without changing the contracts.

## Layers & responsibilities

| Layer | Package | Responsibility |
|---|---|---|
| UI | `apps/web` | Research workstation; talks only to the API |
| API | `apps/api/app/api` | HTTP routers, validation, serialization |
| AI | `app/ai` | Provider adapters, registry, embeddings, RAG, citation validation |
| Retrieval | `app/retrieval` | Keyword (FTS), vector, hybrid search |
| Ingestion | `app/ingestion` | Crawler, fetcher, metadata, chunking, taxonomy, pipeline |
| OCR | `app/ocr` | Text extraction + OCR decision + Tesseract |
| Storage | `app/storage` | Provenance-aware files + checksums |
| Jobs | `app/jobs` | Background execution (Celery/in-process), retries |
| DB | `app/db` | SQLAlchemy models, portable Vector type |
| Security | `app/security` | SSRF, crypto, safe files, redaction |
| Config | `app/config`, `config/` | Settings + source/taxonomy YAML |

## Key contracts

- **AIProvider** (`app/ai/base.py`): `chat`, `stream_chat`, `structured_output`,
  `embed`, `list_models`, `test_connection`. All providers are adapters; the UI
  and RAG layer depend only on this interface.
- **Retrieval** returns `ChunkHit` objects carrying provenance (document id, page,
  chunk id) and per-signal scores.
- **RAG** returns a structured response: answer, claims, validated citations,
  sources, confidence (derived from validation), transparency (provider/model/
  retrieval/tokens).

## Database portability

Models are dialect-aware. On PostgreSQL, embeddings use a real `pgvector`
column and full-text search uses `tsvector`/`ts_rank`. On other backends
(SQLite for quick tests), a JSON embedding column + NumPy cosine and a portable
`LIKE` scorer are used. Semantic search is reported as enabled only when a real
embedder + vectors exist.

## Background jobs

`app/jobs/runner.py` dispatches to Celery when `REDIS_URL` is set and
`JOBS_INLINE=false`; otherwise a thread-pool in-process runner executes the same
`run_job(job_id)` implementation. Jobs record status/errors on
`processing_jobs` and are retryable.

## Extensibility

- New archive source → add to `config/sources.yaml`.
- New AI provider → add an adapter + a `DEFAULT_CATALOG` entry.
- New topic/entity → extend `config/taxonomy.yaml`.
