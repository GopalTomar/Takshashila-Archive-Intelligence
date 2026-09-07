# Ingestion

## Pipeline

```
DISCOVER → NORMALIZE → CHECK ROBOTS/ACCESS/SSRF → FETCH → VALIDATE (signature)
→ HASH (sha256) → DEDUPLICATE → STORE ORIGINAL → EXTRACT METADATA
→ TEXT EXTRACTION → OCR IF REQUIRED → PAGE SEGMENTATION → CHUNKING
→ ENTITY EXTRACTION → TOPIC CLASSIFICATION → EMBEDDING → INDEXING
```

Every step has an explicit status on the `documents` row. Ingestion is **not**
all-or-nothing: a document whose OCR fails is still stored, catalogued and
keyword-searchable. Implemented in `app/ingestion/pipeline.py`.

## Crawler (`app/ingestion/crawler.py`)

- Seed URLs, internal link + document discovery, URL normalization, dedup.
- Respects `robots.txt`; rate-limits; bounded by `max_pages`/`max_depth`.
- SSRF-safe: every URL validated against the source allowlist and public-IP
  rules (`app/security/ssrf.py`).
- Treats non-2xx responses as failures and validates PDF magic bytes — it never
  ingests an error page as a document.
- Produces an honest report (discovered/attempted/downloaded/failed/blocked/
  skipped/duplicates/errors) written to `reports/crawl-*.json` and `.md`.

The crawler never claims it "found everything" — it reports exactly what
happened.

## Configuring sources (`config/sources.yaml`)

```yaml
sources:
  - id: arpi
    name: "Claude Arpi — Historical / Digital Archive"
    base_url: ""            # set a VERIFIED public base URL
    seed_urls: []           # add only verified public URLs
    allowed_domains: []     # crawler scope / SSRF guard
    file_extensions: [".pdf"]
    crawl_rules: { max_pages: 500, max_depth: 3, requests_per_second: 0.5, respect_robots: true, wayback_fallback: true }
    rights: { default_rights_status: "unknown", default_access_status: "public-web" }
```

`seed_urls` is empty by design until a human verifies specific public URLs.
The crawler only uses `seed_urls` (not `candidate_seed_urls`).

## First real ingestion (controlled)

1. Verify a handful of public URLs are live and permitted.
2. Add them to `seed_urls` (or pass them via the API/UI).
3. `POST /api/ingestion/crawl {"source_key":"arpi","confirm":true,"max_pages":5}`.
4. Verify download, checksum, metadata, OCR, search, citation, viewer.
5. Widen only after verification.

## Single-URL ingest

`POST /api/ingestion/ingest-url {"source_key":"arpi","url":"…","confirm":true}`
fetches and ingests one verified document synchronously.

## Wayback fallback (`app/ingestion/wayback.py`)

When a source URL is dead and `wayback_fallback` is on, the Internet Archive
availability API is queried. A found snapshot is stored as a **separate**
`archived_url` — the original `source_url` is never overwritten, and archival
provenance is only claimed when the API confirms a snapshot.

## Deduplication

By SHA-256 and by source URL. Duplicates are detected and never silently
deleted; a duplicate returns the existing document.

## Metadata

Deterministic first (PDF metadata, filename, first-page year), marked
`metadata_source=deterministic`. AI-assisted metadata (if used) is marked `ai`
and enters review — never promoted to `verified` automatically.

## Chunking

Page-preserving: chunks never cross page boundaries, so every chunk keeps an
exact page number. Paragraph-aware packing to a target size with overlap.
