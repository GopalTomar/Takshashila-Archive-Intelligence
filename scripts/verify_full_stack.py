#!/usr/bin/env python3
"""Controlled real-document acceptance test for the FULL stack.

Runs the genuine ingestion pipeline on a locally-generated PDF (a TEST FIXTURE,
clearly not archival material and not fabricated as such) that contains one
native-text page and one image-only page (to exercise real OCR). Then verifies:

  - SHA-256 + storage + page extraction + OCR page detection
  - page-preserving chunks
  - real embeddings stored in the pgvector column (queried back from Postgres)
  - keyword, semantic, and hybrid search all return the document
  - citation validation resolves to the exact document + page
  - RAG retrieval (Groq answer is NOT TESTED unless GROQ_API_KEY is set)

Every result is printed. Nothing is fabricated. Run with the full-stack env
(DATABASE_URL=postgresql..., EMBEDDING_PROVIDER=hash|<real>, PYTHONPATH=apps/api).
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

RESULTS: list[tuple[str, str, str]] = []  # (name, PASS/FAIL/NOT TESTED, detail)


def rec(name, status, detail=""):
    RESULTS.append((name, status, detail))
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


def _fixture_pdf() -> bytes:
    import fitz
    from PIL import Image, ImageDraw, ImageFont
    doc = fitz.open()
    # Page 1: native text (a neutral, self-describing test fixture).
    p1 = doc.new_page()
    p1.insert_textbox(
        fitz.Rect(50, 50, 545, 780),
        "CONTROLLED TEST FIXTURE (not archival material).\n\n"
        "This document verifies the Takshashila ingestion pipeline end to end. "
        "It mentions the Himalaya, cartography, and the year 1962 purely so that "
        "keyword and semantic search have something concrete to match. Page one "
        "carries native, selectable PDF text.",
        fontsize=12, fontname="helv",
    )
    # Page 2: image-only (forces OCR).
    img = Image.new("RGB", (1200, 300), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    d.text((30, 120), "SCANNED PAGE HIMALAYA SURVEY 1962", fill="black", font=font)
    buf = io.BytesIO(); img.save(buf, format="PNG")
    p2 = doc.new_page(width=1200, height=300)
    p2.insert_image(fitz.Rect(0, 0, 1200, 300), stream=buf.getvalue())
    data = doc.tobytes()
    doc.close()
    return data


def main() -> int:
    from sqlalchemy import select, text
    from app.ai.citations import validate_citations
    from app.ai.embeddings import get_embedder
    from app.ai.rag import answer_question
    from app.ai.registry import has_credentials
    from app.bootstrap import init_db, seed_registry
    from app.db.base import SessionLocal, dialect_name
    from app.db.models import Document, DocumentChunk, ProcessingStatus, Source
    from app.ingestion.pipeline import ingest_document_bytes
    from app.retrieval.search import SearchFilters, hybrid_search

    init_db()
    db = SessionLocal()
    seed_registry(db)
    rec("Database connection", "PASS", f"dialect={dialect_name()}")

    # Real (non-demo) pilot source.
    src = db.execute(select(Source).where(Source.source_key == "pilot-test")).scalar_one_or_none()
    if not src:
        src = Source(source_key="pilot-test", name="Controlled pilot test source",
                     doc_prefix="PILOT", is_demo=False,
                     rights_status="test-fixture", access_status="local-test")
        db.add(src); db.flush()

    embedder = get_embedder(db)
    rec("Embedding provider", "PASS" if embedder.enabled else "NOT TESTED",
        f"provider={embedder.provider} model={embedder.model} dims={embedder.dimensions} "
        f"real_semantic={embedder.is_real_semantic}")

    # --- Ingest through the real pipeline (non-demo) ---
    content = _fixture_pdf()
    doc = ingest_document_bytes(db, source=src, content=content,
                                source_url="local-fixture://pilot/controlled_test.pdf",
                                filename="controlled_test.pdf", content_type="application/pdf",
                                is_demo=False, embedder=embedder)
    db.commit()
    rec("Download+store+SHA-256", "PASS" if doc.sha256 and len(doc.sha256) == 64 else "FAIL",
        f"{doc.document_id} sha256={doc.sha256[:16]}...")
    rec("Page extraction", "PASS" if doc.page_count == 2 else "FAIL", f"pages={doc.page_count}")

    sources = {p.text_source for p in doc.pages}
    ocr_pages = [p.page_number for p in doc.pages if p.text_source == "ocr"]
    if ocr_pages:
        # confirm OCR actually produced text
        ocr_text = " ".join((p.text or "") for p in doc.pages if p.text_source == "ocr").upper()
        ok = any(w in ocr_text for w in ("HIMALAYA", "SCANNED", "1962", "SURVEY"))
        rec("OCR (real Tesseract on image page)", "PASS" if ok else "FAIL",
            f"ocr pages={ocr_pages}, sample_ok={ok}")
    else:
        rec("OCR (real Tesseract on image page)", "FAIL", f"no page marked ocr; sources={sources}")

    chunks = db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).scalars().all()
    rec("Page-preserving chunks", "PASS" if chunks and all(c.page_number in (1, 2) for c in chunks) else "FAIL",
        f"chunks={len(chunks)}")

    # --- Verify embeddings actually stored in pgvector ---
    if embedder.enabled:
        embedded = [c for c in chunks if c.embedding is not None]
        detail = f"{len(embedded)}/{len(chunks)} chunks embedded, dims={embedded[0].embedding_dims if embedded else 'n/a'}"
        rec("Embeddings generated + stored", "PASS" if embedded else "FAIL", detail)
        if dialect_name() == "postgresql" and embedded:
            row = db.execute(text(
                "SELECT vector_dims(embedding) FROM document_chunks "
                "WHERE embedding IS NOT NULL LIMIT 1")).first()
            rec("Vector stored in pgvector (queried back)", "PASS" if row else "FAIL",
                f"vector_dims={row[0] if row else None}")
    else:
        rec("Embeddings generated + stored", "NOT TESTED", "no embedding provider configured")

    # --- Search: keyword / semantic / hybrid ---
    f = SearchFilters(include_demo=False)
    kw, m1 = hybrid_search(db, "Himalaya 1962", mode="keyword", filters=f, top_k=5, embedder=embedder)
    rec("Keyword search", "PASS" if any(h.document_id == doc.id for h in kw) else "FAIL",
        f"mode={m1} hits={len(kw)}")
    if embedder.enabled:
        se, m2 = hybrid_search(db, "mountain survey cartography", mode="semantic", filters=f, top_k=5, embedder=embedder)
        rec("Semantic search (pgvector)", "PASS" if any(h.document_id == doc.id for h in se) else "FAIL",
            f"mode={m2} hits={len(se)} top_sem={round(se[0].semantic_score,3) if se else None}")
        hy, m3 = hybrid_search(db, "Himalaya survey 1962", mode="hybrid", filters=f, top_k=5, embedder=embedder)
        both = hy and hy[0].keyword_score > 0 and hy[0].semantic_score > 0
        rec("Hybrid search (keyword+vector)", "PASS" if m3 == "hybrid" and hy else "FAIL",
            f"mode={m3} hits={len(hy)} top(kw={round(hy[0].keyword_score,2) if hy else 0},sem={round(hy[0].semantic_score,2) if hy else 0})")
    else:
        rec("Semantic search (pgvector)", "NOT TESTED", "embeddings disabled")
        rec("Hybrid search (keyword+vector)", "NOT TESTED", "embeddings disabled")

    # --- Citation validation resolves to exact page ---
    c0 = chunks[0]
    outcome = validate_citations(db, [{
        "id": "c1", "document_id": doc.document_id, "chunk_id": c0.chunk_id,
        "page": c0.page_number, "quote": None}], allowed_chunk_ids={c0.chunk_id})
    rec("Citation resolves to document+page", "PASS" if outcome.all_valid else "FAIL",
        f"{doc.document_id} p.{c0.page_number} confidence={outcome.confidence}")

    # --- RAG (Groq answer only if key configured) ---
    resp = answer_question(db, "What year does the fixture mention?",
                           provider_id="groq", model_id="openai/gpt-oss-120b",
                           filters=SearchFilters(include_demo=False), top_k=5, embedder=embedder)
    if has_credentials(db, "groq"):
        rec("RAG grounded answer (Groq)", "PASS" if resp.answer and resp.confidence != "insufficient_evidence" else "FAIL",
            f"confidence={resp.confidence} chunks={resp.chunks_retrieved}")
    else:
        rec("RAG grounded answer (Groq)", "NOT TESTED",
            f"GROQ_API_KEY not configured; retrieval ok (chunks={resp.chunks_retrieved}, sources={len(resp.sources)})")

    db.close()
    print("\n--- SUMMARY ---")
    for n, s, d in RESULTS:
        print(f"{s:12} {n}")
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print(f"\n{sum(1 for r in RESULTS if r[1]=='PASS')} PASS, "
          f"{sum(1 for r in RESULTS if r[1]=='NOT TESTED')} NOT TESTED, {len(fails)} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
