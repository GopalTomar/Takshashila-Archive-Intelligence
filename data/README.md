# Data directory

This directory holds the local archive data. **Its contents are git-ignored**
(except this README). Downloaded documents, OCR outputs, page images, indexes
and caches live here and must never be committed.

## Layout

```
data/
  store/<document_id>/original/   Original downloaded files (never overwritten)
                     /ocr/        OCR-derived PDFs/text
                     /text/       Extracted plain text
                     /images/     Page images / thumbnails
                     /derived/    Other derivatives
  raw/         Scratch for raw crawl payloads (optional)
  processed/   Scratch for processed artifacts (optional)
  indexes/     Any on-disk index artifacts (optional)
  exports/     Generated exports (optional)
  cache/       HTTP / processing caches (optional)
```

The store root is configured by `DATA_DIR` (default `./data`). In Docker it is a
named volume (`archivedata`) mounted at `/data`, so data persists across
restarts.

## What is stored, and why

- **Original files** — the source of truth for preservation and citation.
- **Checksums (SHA-256)** — integrity + duplicate detection (in the database).
- **Page-level text** — enables page-accurate citations (in the database).
- **Provenance** (source URL, archived URL, retrieval date) — in the database.

## Rights

Public accessibility does not imply redistribution rights. Documents can be
stored *metadata-only* (`metadata_only = true`) when redistributing the file is
inappropriate; in that case the file endpoint is disabled but the catalogue
record and provenance are preserved.
