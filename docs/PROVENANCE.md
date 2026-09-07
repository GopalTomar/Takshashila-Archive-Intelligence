# Provenance

Provenance is first-class. Every document and every extracted claim is traceable.

## Per document

| Field | Meaning |
|---|---|
| `source_url` | Original public source URL (never overwritten) |
| `archived_url` + `archive_provider` + `archive_snapshot_timestamp` | Archived copy, if any (kept separate from the original) |
| `local_path` | Stored original file path |
| `sha256` | Checksum for integrity + dedup |
| `retrieved_at` | When it was fetched |
| `mime_type`, `file_size`, `page_count` | File facts |
| `rights_status`, `access_status`, `copyright_notes`, `metadata_only` | Rights |
| `metadata_source` | verified / deterministic / ai / unknown |
| `review_status` | human QC state |

## Per page / chunk

`document_pages(document_id, page_number, text, text_source, ocr_confidence)`
and `document_chunks(chunk_id, document_id, page_number, section, chunk_index,
char_start, char_end)`. Chunking never crosses page boundaries, so a chunk
always resolves to an exact page.

## Per citation

A validated citation carries `document_id`, `chunk_id`, `page`, and (optionally)
a verbatim `quote`, each checked against the database before display. Clicking a
citation opens the document viewer at the exact page.

## Source of truth

The original file is the source of truth. OCR/text derivatives are stored
separately and never overwrite the original. AI output is an interface over the
archive — it never modifies original documents.

## Distinguishing evidence from inference

The UI and prompts distinguish source evidence, source quotation, AI summary,
AI inference and researcher interpretation. AI-derived metadata is labelled `ai`
and requires review; AI-extracted timeline events are labelled "AI-extracted"
until verified.
