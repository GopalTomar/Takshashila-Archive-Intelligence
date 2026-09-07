# Data governance

## What is collected

Publicly accessible documents (initially PDFs) from configured, verified
sources, plus derived data: extracted/OCR text, page-level text, chunks,
embeddings, deterministic metadata, and evidence-backed topic/entity tags.

## Why

To preserve, catalogue, search and analyse historical material with full
provenance, and to support grounded AI research over it.

## How it is stored

- Originals under `DATA_DIR/store/<document_id>/original/` — never overwritten.
- Derivatives (OCR/text/images) stored separately.
- Metadata, provenance, checksums, pages, chunks and embeddings in PostgreSQL.
- Archive data is git-ignored and lives on a persistent volume.

## How provenance is preserved

Source URL, archived URL (if any), local path, SHA-256, retrieval date, and
page numbers on chunks. See [`PROVENANCE.md`](PROVENANCE.md).

## How rights are handled

- `rights_status`, `access_status`, `copyright_notes` per document and per source.
- Public accessibility ≠ redistribution rights. Records can be **metadata-only**
  (`metadata_only=true`): the catalogue entry and provenance are kept, but the
  file is not served.
- Only publicly accessible material is collected; the system never bypasses
  authentication, paywalls, robots restrictions, or technical protections.

## What the AI does

Answers questions strictly from retrieved archive evidence, with validated
citations, and clearly separates evidence from interpretation.

## What the AI does not do

It does not fabricate documents, quotations, dates, pages or citations; it does
not modify original documents; it does not present AI-derived metadata or
AI-extracted events as verified primary-source fact.

## Research integrity

AI outputs are research assistance, not authoritative sources. Original
documents remain primary. Citations should be checked against the underlying
document. See the in-app Methodology page.
