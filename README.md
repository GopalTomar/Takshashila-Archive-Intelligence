# Takshashila Archive Intelligence

A provenance-first archival intelligence and AI research platform: a digital
preservation system, archival catalogue, OCR/document-processing pipeline,
hybrid (keyword + semantic) search engine, and a **grounded** RAG research
assistant with strict, validated citations — wrapped in a Takshashila-branded
research workstation.

> **Operating principle:** the system never fabricates documents, URLs,
> metadata, OCR text, search results, citations, or AI answers. Unknown values
> are stored as `NULL`/`unknown`. The AI answers only from retrieved archive
> evidence and says so when evidence is insufficient. Original documents remain
> the source of truth.

The initial intended corpus is publicly accessible material associated with
Claude Arpi's historical/digital archive. The architecture is multi-archive:
new sources are added in `config/sources.yaml` with no code changes.

---

## What it is

1. Digital preservation system (originals preserved, checksummed, never overwritten)
2. Archival catalogue (rich, provenance-aware metadata)
3. Document processing / OCR pipeline (PyMuPDF + Tesseract/OCRmyPDF)
4. Provenance-aware research database (PostgreSQL + pgvector)
5. Full-text + semantic hybrid search
6. Grounded AI/RAG research assistant with citation validation
7. Historical timeline, entity explorer, geographic explorer
8. Configurable multi-model AI interface (Groq, OpenAI, OpenAI-compatible, local)
9. Takshashila-branded, accessible research workstation

## Architecture (modular monorepo)

```
apps/
  api/            FastAPI backend (modular monolith)
    app/
      db/         SQLAlchemy models + portable Vector type
      storage/    provenance-aware file storage + checksums
      ingestion/  crawler, fetcher (SSRF-safe), metadata, chunking, taxonomy, pipeline
      ocr/        text extraction + Tesseract OCR
      retrieval/  hybrid search (FTS + vector)
      ai/         provider adapters, registry, embeddings, RAG, citation validation
      jobs/       background job runner (Celery or in-process)
      api/routers API endpoints
      security/   SSRF guard, secret crypto, safe file handling, redaction
    alembic/      migrations
  web/            Next.js + TypeScript + Tailwind frontend (Takshashila design language)
config/           sources.yaml, taxonomy.yaml
data/             local archive data (git-ignored)
docs/             architecture, database, ingestion, OCR, search, RAG, security, ...
scripts/          acceptance.py (vertical slice), generate_manifest.py
tests/            pytest suite (pipeline, search, citations, crawler, OCR, security, RAG, API)
```

Strict separation is maintained between UI, API, database, ingestion, document
processing, OCR, retrieval, AI providers, background jobs and configuration.
See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Requirements

- Docker + Docker Compose (recommended), **or** for local dev:
- Python 3.11+, Node.js 20+, PostgreSQL 16 with `pgvector`, Tesseract + Ghostscript (for OCR)

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env: set APP_SECRET_KEY (python -c "import secrets;print(secrets.token_urlsafe(48))")
docker compose up --build
```

Then open:

- Web UI: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>, readiness: <http://localhost:8000/ready>

The API container runs `alembic upgrade head` on start. Postgres and archive
data persist in named volumes.

## Quick start (local, no Docker)

```bash
make setup                 # venv + backend deps + frontend deps
cp .env.example .env       # set APP_SECRET_KEY and DATABASE_URL
# Point DATABASE_URL at a Postgres with pgvector, or use sqlite for a quick spin.
make migrate               # apply migrations (Postgres) — for sqlite the app auto-creates tables
make api                   # terminal 1  -> http://localhost:8000
make web                   # terminal 2  -> http://localhost:3000
```

Seed synthetic demo data from **Settings → Processing → Seed Demo Data** (or
`POST /api/ingestion/demo/seed`). Demo records are clearly labelled
"DEMO DATA — NOT ARCHIVAL MATERIAL" and kept separate from production records.

## Configuring Groq (and other providers)

Keys are stored **server-side only**, encrypted at rest, and are never returned
to the browser, logged, or included in errors.

Two ways to configure Groq:

1. **Environment**: set `GROQ_API_KEY` in `.env`.
2. **UI**: Settings → AI Providers → Groq → paste key → **Save Key** →
   **Test Connection** (makes a real request to Groq).

Select the model in the main interface: **Provider = Groq**,
**Model = GPT-OSS 120B** (`openai/gpt-oss-120b`); `openai/gpt-oss-20b` is also
available. Pricing/availability depends on your provider account (never asserted
by this app). See [`docs/AI_PROVIDERS.md`](docs/AI_PROVIDERS.md).

Other providers: OpenAI, any OpenAI-compatible endpoint (OpenRouter, vLLM,
LM Studio), and local models — all via the same adapter and capability registry.

## Embeddings & semantic search

Embeddings are configured **independently** from the chat model
(`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`). If no
embedding provider is configured, semantic search is **disabled** and the app
uses keyword/full-text search — it never pretends semantic search is on.
`EMBEDDING_PROVIDER=hash` is a deterministic offline embedder for tests/demos,
clearly labelled as *not* a real semantic model.

## Ingesting the first real archive source

1. Verify specific **public** URLs are live and permitted.
2. Add them to `seed_urls` for the `arpi` source in `config/sources.yaml`
   (or paste them in Archive → Ingestion).
3. Start a **small** crawl (a few documents) with `confirm=true`. The crawler
   respects robots.txt, an allowlist, and rate limits, and produces an honest
   crawl report in `reports/`.
4. Verify download, checksum, metadata, OCR, search, citation and the viewer.
5. Only then widen the crawl. See [`docs/INGESTION.md`](docs/INGESTION.md).

## How it works

- **OCR** — [`docs/OCR.md`](docs/OCR.md): extract embedded text; OCR with
  Tesseract only when a PDF is scanned; failures are marked, never faked.
- **Search** — [`docs/SEARCH.md`](docs/SEARCH.md): Postgres FTS + pgvector,
  combined into a hybrid score with a configurable weight.
- **RAG** — [`docs/RAG.md`](docs/RAG.md): retrieve → ground → generate
  structured output → **validate every citation against the DB** → derive a
  confidence label from validation.
- **Citations** — resolve to an exact document and page; click to open the page.
- **Provenance** — [`docs/PROVENANCE.md`](docs/PROVENANCE.md).
- **Security** — [`docs/SECURITY.md`](docs/SECURITY.md): SSRF guard, path-traversal
  protection, file-signature checks, secret redaction, prompt-injection defence.

## Adding a new archive

Append an entry to `config/sources.yaml` (`id`, `name`, `base_url`, `seed_urls`,
`allowed_domains`, `file_extensions`, `crawl_rules`, `rights`). No code change is
required. See [`docs/INGESTION.md`](docs/INGESTION.md).

## Testing

```bash
make test          # pytest (point DATABASE_URL at a Postgres test DB for pgvector/FTS)
make acceptance    # end-to-end vertical slice
```

## Documentation

`docs/`: ARCHITECTURE, DATABASE, DATA_MODEL, INGESTION, OCR, SEARCH, RAG,
AI_PROVIDERS, PROVENANCE, SECURITY, DEPLOYMENT, TROUBLESHOOTING, CONTRIBUTING,
OPERATIONS_RUNBOOK, plus INITIAL_ARCHITECTURE_AUDIT, IMPLEMENTATION_PLAN and
FINAL_IMPLEMENTATION_REPORT.

## License / rights

Source code is provided for the project. Archival content retains its own
rights; see [`docs/DATA_GOVERNANCE.md`](docs/DATA_GOVERNANCE.md).
