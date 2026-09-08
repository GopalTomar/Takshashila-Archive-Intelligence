"""PDF text extraction and OCR.

Policy (per spec section 18):
  1. Determine whether machine-readable text exists.
  2. If sufficient text exists, extract it (per page).
  3. If not, run OCR (Tesseract via PyMuPDF rasterisation).
  4. Preserve the original (handled by the storage layer — never touched here).
  5. Record page-level text, engine/version, timestamp, confidence.
  6. Mark failures explicitly; never silently replace poor OCR.

OCR requires Tesseract to be installed. If it is not, OCR is reported as
FAILED with a clear reason — never faked.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

# Below which mean chars/page we consider a PDF "scanned" (needs OCR).
MIN_CHARS_PER_PAGE = 40


@dataclass
class PageText:
    page_number: int
    text: str
    source: str  # "embedded" | "ocr"
    confidence: float | None = None


@dataclass
class ExtractionResult:
    page_count: int
    pages: list[PageText] = field(default_factory=list)
    used_ocr: bool = False
    engine: str | None = None
    engine_version: str | None = None
    mean_confidence: float | None = None
    error: str | None = None

    @property
    def total_chars(self) -> int:
        return sum(len(p.text or "") for p in self.pages)


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def tesseract_version() -> str | None:
    if not tesseract_available():
        return None
    try:
        out = subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True, timeout=10
        )
        first = (out.stdout or out.stderr).splitlines()[0] if (out.stdout or out.stderr) else ""
        return first.strip() or None
    except Exception:  # pragma: no cover
        return None


def _extract_embedded(path: str) -> ExtractionResult:
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    pages: list[PageText] = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = page.get_text("text") or ""
        pages.append(PageText(page_number=i + 1, text=text, source="embedded"))
    result = ExtractionResult(page_count=doc.page_count, pages=pages, used_ocr=False)
    doc.close()
    return result


def _needs_ocr(result: ExtractionResult) -> bool:
    if result.page_count == 0:
        return False
    return (result.total_chars / max(result.page_count, 1)) < MIN_CHARS_PER_PAGE


def _page_needs_ocr(text: str) -> bool:
    return len((text or "").strip()) < MIN_CHARS_PER_PAGE


def _ocr_render_page(doc, index: int, dpi: int = 200):
    """OCR a single already-open PDF page; returns (text, confidence)."""
    import io

    import pytesseract
    from PIL import Image

    page = doc.load_page(index)
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(img)
    conf = None
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        vals = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
        if vals:
            conf = sum(vals) / len(vals)
    except Exception:
        pass
    return text, conf


def extract_text(path: str, *, force_ocr: bool = False) -> ExtractionResult:
    """Extract per-page text, running OCR PER PAGE only where needed (or forced).

    Native-text pages are preserved - OCR never silently replaces them. Only
    pages with little/no embedded text are OCR'd, so a mixed PDF (a few scanned
    pages among native pages) is handled correctly, and each page records its
    source (``embedded`` vs ``ocr``). Never raises for a bad PDF - returns a
    result with ``error`` set so the pipeline can record an explicit failure
    without losing the document.
    """
    import fitz

    try:
        embedded = _extract_embedded(path)
    except Exception as exc:  # corrupt/empty/non-PDF
        return ExtractionResult(page_count=0, error=f"text extraction failed: {exc}")

    if embedded.page_count == 0:
        embedded.error = "PDF has zero pages"
        return embedded

    if force_ocr:
        need = [p.page_number for p in embedded.pages]
    else:
        need = [p.page_number for p in embedded.pages if _page_needs_ocr(p.text)]

    if not need:
        return embedded  # every page already has native text

    if not tesseract_available():
        embedded.error = (
            f"OCR required for {len(need)} page(s) with little/no embedded text, "
            "but Tesseract is not installed. Embedded text preserved; OCR NOT performed."
        )
        return embedded

    try:
        doc = fitz.open(path)
        by_num = {p.page_number: p for p in embedded.pages}
        confs: list[float] = []
        ocr_done = 0
        for num in need:
            text, conf = _ocr_render_page(doc, num - 1)
            existing = by_num[num]
            # Never lose richer native text.
            if not force_ocr and len((existing.text or "").strip()) >= len((text or "").strip()):
                continue
            existing.text = text
            existing.source = "ocr"
            existing.confidence = conf
            if conf is not None:
                confs.append(conf)
            ocr_done += 1
        doc.close()
        embedded.used_ocr = ocr_done > 0
        if ocr_done > 0:
            embedded.engine = "tesseract"
            embedded.engine_version = tesseract_version()
            embedded.mean_confidence = (sum(confs) / len(confs)) if confs else None
        return embedded
    except Exception as exc:
        embedded.error = f"OCR failed: {exc}"
        return embedded
