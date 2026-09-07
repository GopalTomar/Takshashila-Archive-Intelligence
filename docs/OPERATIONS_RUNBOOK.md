# Operations runbook

## Start / stop

- Start: `docker compose up --build` (or `make api` + `make web` locally).
- Stop: `docker compose down` (add `-v` to also drop volumes — destroys data).
- Health: `GET /health` (liveness), `GET /ready` (DB, pgvector, embeddings, OCR,
  jobs backend).

## Routine operations

**Seed / clear demo data**
- `POST /api/ingestion/demo/seed` · `POST /api/ingestion/demo/clear`.

**Run a controlled crawl**
1. Add verified public URLs to `config/sources.yaml` `seed_urls`.
2. `POST /api/ingestion/crawl {"source_key":"arpi","confirm":true,"max_pages":5}`.
3. Watch `GET /api/ingestion/jobs` and `GET /api/ingestion/crawls/{id}`.
4. Reports are written to `reports/crawl-*.json|md`.

**Generate the archive manifest**
- `make manifest` → `archive_manifest.csv` / `.json` (real DB rows only).

**Retry a failed job**
- `POST /api/ingestion/jobs/{id}/retry`.

## Backups

- Back up the Postgres volume (`pgdata`) and the archive data volume
  (`archivedata`). The originals under `DATA_DIR/store` are the source of truth.
- Verify integrity via stored SHA-256 checksums.

## Incidents

| Symptom | Action |
|---|---|
| API 500s | Check API logs (structured JSON, request_id); `/ready` for dependencies |
| Jobs stuck | Check Celery worker + Redis; fall back to `JOBS_INLINE=true` for local |
| Provider errors | Settings → Test Connection; verify key/base URL/egress |
| Disk full | Prune `DATA_DIR` derivatives/caches; grow the volume |
| Bad OCR on a doc | Mark `review_status=ocr_poor`; re-run ingestion for that doc |

## Security operations

- Rotating `APP_SECRET_KEY` invalidates stored encrypted provider keys — re-enter
  keys afterward.
- Never commit `.env` or archive data. Confirm `.gitignore` before pushing.
- Review crawl allowlists (`allowed_domains`) before enabling a new source.

## Data governance

See [`DATA_GOVERNANCE.md`](DATA_GOVERNANCE.md) for what is collected, why, how it
is stored, and how rights are handled.
