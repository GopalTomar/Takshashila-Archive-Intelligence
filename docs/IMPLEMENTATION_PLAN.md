# Implementation Plan

Status legend: `TODO` · `IN PROGRESS` · `BLOCKED` · `DONE` (implemented) ·
`VERIFIED` (implemented **and** tested/run).

`DONE` never means "code written" alone — it means implemented and reviewed.
`VERIFIED` means a test or a live run proved it.

---

## Architecture contracts (agreed before implementation)

- **Document ID:** human-readable, source-prefixed, zero-padded, e.g.
  `ARPI-00001`. Allocated by the DB per source.
- **Provenance record** attached to every document: `source_url`,
  `archived_url`, `local_path`, `sha256`, `retrieved_at`, `page_number` on
  chunks.
- **Status enums** are explicit (`pending/running/succeeded/failed/skipped`)
  so ingestion is never all-or-nothing.
- **AI boundary:** UI → API → `ai` service → provider adapter. No
  provider-specific logic in the UI. Keys never cross to the browser.
- **Citation object:** `{id, document_id, page, chunk_id, title, source_url,
  archived_url}` — validated against the DB before display.

---

## Phases

| Phase | Task | Status | Files (primary) |
|---|---|---|---|
| 0 | Repo audit + architecture | VERIFIED | `docs/INITIAL_ARCHITECTURE_AUDIT.md`, `docs/ARCHITECTURE.md` |
| 1 | Scaffolding, config, env | VERIFIED | `pyproject`/`requirements`, `.gitignore`, `.env.example`, `config/sources.yaml`, `config/taxonomy.yaml` |
| 2 | Database + models | VERIFIED | `apps/api/app/db/models.py`, Alembic |
| 3 | Core API | VERIFIED | `apps/api/app/main.py`, `app/api/routers/*` |
| 4 | Document storage + checksums | VERIFIED | `app/storage/*` |
| 5 | Crawler (robots/SSRF-safe) | VERIFIED | `app/ingestion/crawler.py` |
| 6 | OCR pipeline | VERIFIED | `app/ocr/*` |
| 7 | Metadata extraction | VERIFIED | `app/ingestion/metadata.py` |
| 8 | Search (FTS + hybrid) | VERIFIED | `app/retrieval/search.py` |
| 9 | Embeddings abstraction | VERIFIED | `app/ai/embeddings.py`, `app/retrieval/vectors.py` |
| 10 | RAG + citation validation | VERIFIED | `app/ai/rag.py`, `app/ai/citations.py` |
| 11 | AI provider abstraction | VERIFIED | `app/ai/providers/*` |
| 12 | Frontend workspace | DONE | `apps/web/*` |
| 13 | Document viewer | DONE | `apps/web/app/documents/[id]` |
| 14 | Timeline / entities | DONE | `apps/web/app/timeline`, `.../entities` |
| 15 | Settings / model selector | DONE | `apps/web/app/settings`, components |
| 16 | Testing | VERIFIED | `tests/*` |
| 17 | Docker / deployment | DONE (not brought up here) | `docker-compose.yml`, `Dockerfile*` |
| 18 | Final integration + acceptance | VERIFIED | `scripts/acceptance.py`, `docs/FINAL_IMPLEMENTATION_REPORT.md` |

## Vertical slice (Phase 61 requirement)

One document → ingest → store → checksum → metadata → text/OCR → chunk →
embed → index → search → RAG → citation → viewer. Implemented as
`scripts/acceptance.py` and covered by `tests/test_acceptance_slice.py`.

## Honest status of verification

- Backend, DB (Postgres + pgvector), OCR, search, RAG grounding, and citation
  validation are exercised by the automated test suite run in this session.
- Docker Compose is provided but **not** started in this session (no daemon).
- Live external crawling depends on egress policy; the crawler is verified
  against a local fixture HTTP server, not a live public crawl in this
  session.
