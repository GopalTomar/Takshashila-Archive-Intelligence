# OCR & text extraction

Implemented in `app/ocr/pdf.py`.

## Decision flow

1. Extract embedded text per page with PyMuPDF (`fitz`).
2. If mean chars/page ≥ threshold (40), use embedded text (no OCR needed).
3. Otherwise the PDF is treated as scanned and OCR runs (Tesseract via
   rasterised page images).
4. If OCR would yield less text than the embedded layer, the embedded text is
   kept and a note recorded.

## What is recorded

- Per-page text and its source (`embedded` or `ocr`) on `document_pages`.
- OCR engine + version, pages processed, mean confidence on `ocr_runs`.
- Statuses on the document: `text_extraction_status`, `ocr_status`.

## Honesty

- The **original is never modified** — OCR derivatives are separate.
- Poor OCR is **not** silently substituted; failures are marked explicitly.
- If Tesseract is not installed, OCR is reported as **not performed** with a
  clear reason (embedded text, if any, is still preserved) — never faked.

## Dependencies

Tesseract (`tesseract-ocr`) and Ghostscript are installed in the API Docker
image. For local dev install them via your package manager. `pytesseract` and
`PyMuPDF` are Python dependencies. `ocrmypdf` is available for producing
searchable OCR-PDF derivatives.

## Confidence

Per-word confidence is read from Tesseract's TSV output and averaged per page /
document where available; stored as `ocr_confidence` and `mean_confidence`.
