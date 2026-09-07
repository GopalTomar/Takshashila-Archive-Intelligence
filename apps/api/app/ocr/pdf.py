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


def _ocr_pages(path: str, dpi: int = 200) -> ExtractionResult:
    import fitz
    import pytesseract
    from PIL import Image
    import io

    engine_version = tesseract_version()
    doc = fitz.open(path)
    pages: list[PageText] = []
    confs: list[float] = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img)
        # Per-word confidence via TSV output.
        conf = None
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            vals = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
            if vals:
                conf = sum(vals) / len(vals)
                confs.append(conf)
        except Exception:
            pass
        pages.append(PageText(page_number=i + 1, text=text, source="ocr", confidence=conf))
    doc.close()
    return ExtractionResult(
        page_count=len(pages),
        pages=pages,
        used_ocr=True,
        engine="tesseract",
        engine_version=engine_version,
        mean_confidence=(sum(confs) / len(confs)) if confs else None,
    )


def extract_text(path: str, *, force_ocr: bool = False) -> ExtractionResult:
    """Extract per-page text, running OCR only when needed (or forced).

    Never raises for a bad PDF — returns a result with ``error`` set so the
    pipeline can record an explicit failure without losing the document.
    """
    try:
        embedded = _extract_embedded(path)
    except Exception as exc:  # corrupt/empty/non-PDF
        return ExtractionResult(page_count=0, error=f"text extraction failed: {exc}")

    if embedded.page_count == 0:
        embedded.error = "PDF has zero pages"
        return embedded

    if not force_ocr and not _needs_ocr(embedded):
        return embedded

    # Needs OCR.
    if not tesseract_available():
        embedded.error = (
            "OCR required (little/no embedded text) but Tesseract is not "
            "installed. Embedded text preserved; OCR NOT performed."
        )
        return embedded

    try:
        ocr = _ocr_pages(path)
        # If forced but embedded had text, keep both isn't needed; OCR wins only
        # when embedded was insufficient. Preserve embedded text where richer.
        if not force_ocr and embedded.total_chars > ocr.total_chars:
            embedded.error = "OCR produced less text than embedded; kept embedded."
            return embedded
        return ocr
    except Exception as exc:
        embedded.error = f"OCR failed: {exc}"
        return embedded
