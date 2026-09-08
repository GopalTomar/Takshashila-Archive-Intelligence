"""Integration tests for the expanded dashboard stats and per-page OCR."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from conftest import make_text_pdf
from app.db.models import ProcessingStatus
from app.ingestion.pipeline import ingest_document_bytes
from app.main import app
from app.ocr.pdf import tesseract_available

client = TestClient(app)


def test_stats_has_new_fields(db):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ["chunks", "embeddings", "ingestion_jobs", "crawl_jobs", "jobs"]:
        assert key in body
    for jk in ["queued", "running", "completed", "failed"]:
        assert jk in body["jobs"]
    # semantic_search reports provider/model/dimensions
    assert "dimensions" in body["semantic_search"]


def test_distributions_endpoint_shape(db):
    r = client.get("/api/stats/distributions")
    assert r.status_code == 200
    body = r.json()
    for key in ["documents_by_year", "documents_by_type", "ocr_status",
                "index_status", "embedding_status", "sources"]:
        assert key in body and isinstance(body[key], list)


def test_stats_counts_reflect_ingestion(db, demo_source):
    ingest_document_bytes(
        db, source=demo_source,
        content=make_text_pdf(["Aksai Chin 1962 in the year 1962."]),
        source_url="http://x/y.pdf", filename="y.pdf", is_demo=True,
    )
    db.commit()
    body = client.get("/api/stats?include_demo=true").json()
    assert body["documents"] >= 1
    assert body["chunks"] >= 1
    # distributions should now show the year 1962
    dist = client.get("/api/stats/distributions?include_demo=true").json()
    years = [d["label"] for d in dist["documents_by_year"]]
    assert "1962" in years


def _image_only_pdf(text: str) -> bytes:
    import fitz
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1000, 240), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    d.text((20, 90), text, fill="black", font=font)
    buf = io.BytesIO(); img.save(buf, format="PNG")
    doc = fitz.open()
    # page 1 native text
    p1 = doc.new_page()
    p1.insert_textbox(fitz.Rect(50, 50, 545, 780),
                      "Native text page with plenty of selectable content about the Himalaya frontier.",
                      fontsize=12, fontname="helv")
    # page 2 image only
    p2 = doc.new_page(width=1000, height=240)
    p2.insert_image(fitz.Rect(0, 0, 1000, 240), stream=buf.getvalue())
    data = doc.tobytes(); doc.close()
    return data


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract not installed")
def test_per_page_ocr_mixed_document(db, demo_source):
    """A mixed PDF: page 1 native text is preserved, page 2 (image) is OCR'd."""
    doc = ingest_document_bytes(
        db, source=demo_source, content=_image_only_pdf("SCANNED LADAKH 1962"),
        source_url="http://x/mixed.pdf", filename="mixed.pdf", is_demo=True,
    )
    db.commit()
    pages = {p.page_number: p for p in doc.pages}
    assert pages[1].text_source == "embedded"      # native preserved
    assert pages[2].text_source == "ocr"           # scanned page OCR'd
    assert doc.ocr_status == ProcessingStatus.succeeded
    combined = (pages[2].text or "").upper()
    assert any(w in combined for w in ("SCANNED", "LADAKH", "1962"))
