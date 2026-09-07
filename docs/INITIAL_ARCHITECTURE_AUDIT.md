# Initial Architecture Audit

**Project:** Takshashila Archive Intelligence
**Date of audit:** 2026-09-07
**Auditor role:** Lead architect / full-stack / data / DevOps

This document records the *actual, observed* state of the repository and the
development environment at the start of implementation. Nothing here is
assumed or invented; every fact below was verified with a command.

---

## 1. Repository state

| Check | Result |
|---|---|
| Is a git repository | Yes |
| Current branch | `claude/takshashila-archive-platform-1gqt7p` |
| Commits | **None** — repository has no commits yet |
| Tracked files | **None** |
| Working-tree files | Only `.git/` |
| Remote `origin` | `https://github.com/GopalTomar/Takshashila-Archive-Intelligence` |

**Conclusion:** The repository is genuinely empty (greenfield). There is no
existing application code, schema, API, or UI to preserve or avoid
overwriting. Implementation starts from zero.

---

## 2. Development environment (observed)

| Tool | Present | Version | Notes |
|---|---|---|---|
| Python | Yes | 3.11.15 | `/usr/local/bin/python3` |
| pip | Yes | 24.0 | |
| Node.js | Yes | 22.22.2 | |
| npm | Yes | 10.9.7 | |
| Docker CLI | Yes | 29.3.1 | **daemon NOT running** in this environment |
| Docker Compose | Yes | v5.1.1 (plugin) | cannot run without daemon |
| PostgreSQL client | Yes | 16.13 | |
| PostgreSQL server | Installed | 16 (`/usr/lib/postgresql/16/bin`) | initially not running; started locally on port 55432 for verification |
| pgvector | Installed during audit | 0.6.0 | `postgresql-16-pgvector` |
| pg_trgm | Available | 1.6 | trigram fuzzy match |
| Tesseract OCR | Installed during audit | 5.3.4 | |
| Ghostscript | Installed during audit | 10.02.1 | needed by OCRmyPDF |
| make | Yes | GNU Make 4.3 | |

### Environment constraints that shaped the design

1. **The Docker daemon is not running here.** Docker/Compose is therefore the
   documented production/local path, but this session verifies the backend
   directly against a locally-started PostgreSQL 16 + pgvector cluster
   (port 55432) rather than through Compose. The Compose files are provided
   and linted for correctness but were **not** brought up in this session —
   this is stated honestly in the final report rather than claimed as tested.
2. **PostgreSQL + pgvector + Tesseract + Ghostscript are all available**, so
   the real production stack (Postgres FTS, pgvector similarity, OCR) is
   genuinely exercised by the test suite and the vertical-slice acceptance
   run — not simulated.
3. Outbound HTTPS is via an agent proxy with an allowlist. Live crawling of
   arbitrary external hosts may be blocked by egress policy; the crawler is
   built to record blocked/failed URLs honestly rather than fabricate
   successful downloads.

---

## 3. Design decisions arising from the audit

- **Modular monolith, not microservices.** The brief asks for a "modular
  monorepo" with strict module separation. A single FastAPI backend with
  cleanly separated internal packages (`ingestion`, `ocr`, `retrieval`,
  `ai`, `storage`, `provenance`) plus a Next.js frontend gives the required
  separation without the operational cost of many deployables. Background
  work runs on a job runner (Celery + Redis in Docker; an in-process
  fallback runner for environments without Redis) so long tasks never block
  the API.
- **Database portability with Postgres as the real target.** SQLAlchemy
  models are dialect-aware. On PostgreSQL the app uses `tsvector` full-text
  search and a `pgvector` column for embeddings (the production path, and the
  path tested here). A portable fallback (Python cosine similarity + `LIKE`)
  keeps unit tests runnable on SQLite, but semantic search is **only**
  reported as enabled when embeddings and a vector index are actually
  present — never faked.
- **No fabricated data.** Unknown metadata is stored as `NULL`/`unknown`.
  Demo data is clearly flagged and physically separated from production
  archival records via an `is_demo` column and a distinct collection.
- **Secrets server-side only.** API keys live in environment variables /
  server-side settings, are never returned by the API, never logged, and are
  redacted from errors.

See `docs/IMPLEMENTATION_PLAN.md` for the phased plan and
`docs/ARCHITECTURE.md` for the full architecture.
