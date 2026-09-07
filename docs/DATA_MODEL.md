# Data model

All models are in `apps/api/app/db/models.py`. Unknown values are `NULL`/
`unknown` — never guessed. Demo/synthetic rows are flagged `is_demo=True`.

## Tables

| Table | Purpose |
|---|---|
| `sources` | Archive sources; allocates `document_id` sequences per source |
| `archive_collections` | Named collections (incl. a separate demo collection) |
| `documents` | Logical document + provenance + per-step statuses |
| `document_files` | Physical files per document (original/ocr/text/images/derived) |
| `document_versions` | Version history; originals never overwritten |
| `document_pages` | Page-level text, source (embedded/ocr), OCR confidence |
| `document_chunks` | Provenance-preserving chunks + embedding vector |
| `categories`, `topics`, `document_topics` | Taxonomy + evidence-backed tags |
| `entities`, `document_entities` | Entities + mentions (type, page, confidence) |
| `events`, `document_events` | Timeline events (AI-extracted until verified) |
| `citations` | Audit trail of citations produced + validation result |
| `crawl_runs`, `crawl_items` | Crawl state + honest per-URL outcomes |
| `processing_jobs` | Background jobs: status, payload, result, retries, errors |
| `ocr_runs` | OCR engine/version, pages processed, mean confidence |
| `ai_runs` | Each AI answer: provider/model/retrieval/tokens/confidence |
| `ai_providers`, `ai_models` | Provider registry; encrypted key; capabilities |
| `app_settings` | Non-secret settings (retrieval defaults, appearance) |
| `saved_searches`, `research_sessions`, `research_notes` | Research notebook |

## Document record fields (spec 10)

`document_id, title, subtitle, author, authors, doc_date, date_precision,
publisher, document_type, collection, description, language, page_count,
source_url, archived_url, local_path, mime_type, file_size, sha256,
rights_status, access_status, retrieved_at, created_at, updated_at, ocr_status,
text_extraction_status, metadata_status, index_status, embedding_status,
metadata_source, review_status, duplicate_of_id, is_demo`.

## Status enums

- `ProcessingStatus`: pending / running / succeeded / failed / skipped / not_applicable
- `MetadataSource`: verified / deterministic / ai / unknown
- `ReviewStatus`: unreviewed / verified / needs_review / incorrect_metadata / duplicate / ocr_poor / source_uncertain
- `DatePrecision`: exact / month / year / decade / unknown

## Provenance chain

`documents.source_url` + `archived_url` + `local_path` + `sha256` +
`retrieved_at`, and `document_chunks.(document_id, page_number, chunk_id)` so a
citation resolves to an exact page. See [`PROVENANCE.md`](PROVENANCE.md).
