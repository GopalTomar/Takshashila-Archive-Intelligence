"""OCR pipeline against a genuinely image-only (scanned-style) PDF.

Requires Tesseract. If Tesseract is unavailable the test is skipped (and the
pipeline is expected to mark OCR as not performed — never faked)."""
from __future__ import annotations

import io

import pytest

from app.db.models import ProcessingStatus
from app.ingestion.pipeline import ingest_document_bytes
from app.ocr.pdf import tesseract_available


def _make_image_only_pdf(text: str) -> bytes:
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    # Render text to an image (no selectable text), then embed image in a PDF.
    img = Image.new("RGB", (1000, 300), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    draw.text((30, 120), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=1000, height=300)
    page.insert_image(fitz.Rect(0, 0, 1000, 300), stream=buf.getvalue())
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract not installed")
def test_scanned_pdf_is_ocred(db, demo_source):
    content = _make_image_only_pdf("AKSAI CHIN 1962")
    doc = ingest_document_bytes(db, source=demo_source, content=content,
                               source_url="http://x/scanned.pdf", filename="scanned.pdf",
                               is_demo=True)
    db.commit()
    assert doc.ocr_status == ProcessingStatus.succeeded
    # OCR actually produced text (fuzzy match — OCR is imperfect).
    pages = {p.page_number: (p.text or "") for p in doc.pages}
    combined = " ".join(pages.values()).upper()
    assert "AKSAI" in combined or "CHIN" in combined or "1962" in combined


def test_ocr_availability_reported_honestly():
    from app.ocr.pdf import tesseract_available, tesseract_version
    if tesseract_available():
        assert tesseract_version() is not None
    else:
        assert tesseract_version() is None
