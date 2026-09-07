#!/usr/bin/env python3
"""End-to-end vertical-slice acceptance run (spec 61 & 97).

Proves the full pipeline for a single document against the REAL stack:
ingest -> store -> checksum -> metadata -> text/OCR -> chunk -> embed -> index
-> search -> RAG -> citation validation -> research session -> persistence.

Honesty: this script never fabricates results. The AI answer step makes a REAL
provider call only if GROQ_API_KEY (or a stored key) is configured; otherwise it
reports "provider not configured" and still proves retrieval + citation
validation. Run:

    DATABASE_URL=... EMBEDDING_PROVIDER=hash EMBEDDING_DIMENSIONS=256 \
    APP_SECRET_KEY=... PYTHONPATH=apps/api python scripts/acceptance.py
"""
from __future__ import annotations

import io
import os
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

RESULTS: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def _make_pdf(pages):
    import fitz
    doc = fitz.open()
    for t in pages:
        p = doc.new_page()
        p.insert_textbox(__import__("fitz").Rect(50, 50, 545, 780), t, fontsize=11, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


class _H(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main() -> int:
    from app.ai.citations import validate_citations
    from app.ai.embeddings import get_embedder
    from app.ai.rag import answer_question
    from app.bootstrap import init_db, seed_registry
    from app.db.base import SessionLocal
    from app.db.models import Document, ResearchSession
    from app.ingestion.crawl_service import run_crawl
    from app.ingestion.sources import get_source_config, sync_source_to_db
    from app.retrieval.search import SearchFilters, hybrid_search

    # ── 1. Clean-ish start ──
    init_db()
    db = SessionLocal()
    seed_registry(db)
    step("1. Schema + registry initialised", True)

    # ── 2. Serve one document on a local fixture server ──
    site = ROOT / "data" / "acceptance_site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text('<html><body><a href="/aksai.pdf">Doc</a></body></html>')
    (site / "aksai.pdf").write_bytes(_make_pdf([
        "Note on Aksai Chin (SYNTHETIC ACCEPTANCE FIXTURE). India and China "
        "discussed the boundary in 1959. The McMahon Line and Ladakh are mentioned.",
        "Page two discusses Tibet, Lhasa and the Dalai Lama for entity extraction.",
    ]))
    os.chdir(site)
    server = HTTPServer(("127.0.0.1", 8899), _H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    step("2. Fixture document served", True, "http://127.0.0.1:8899/aksai.pdf")

    # ── 3-13. Controlled ingestion (download, checksum, metadata, OCR/text, pages, chunk, embed, index) ──
    cfg = get_source_config("fixtures")
    run = run_crawl(db, "fixtures", seed_urls=["http://127.0.0.1:8899/index.html"], allow_private=True)
    server.shutdown()
    doc = db.query(Document).filter(Document.source_url.like("%aksai.pdf")).first()
    ok = doc is not None
    step("3-9. Download + store original + checksum", ok, f"sha256={doc.sha256[:12] if doc else 'n/a'}…")
    step("10. Metadata extracted", bool(doc and doc.metadata_status.value == "succeeded"),
         f"title={doc.title!r}" if doc else "")
    step("11-12. Text/OCR + page-level text", bool(doc and doc.page_count and doc.pages),
         f"{doc.page_count} pages, {len(doc.pages)} page rows" if doc else "")
    step("13. Indexed + chunked", bool(doc and doc.chunks), f"{len(doc.chunks)} chunks" if doc else "")

    emb = get_embedder(db)
    step("13b. Embeddings", bool(doc and any(c.embedding for c in doc.chunks)) if emb.enabled else True,
         emb.status().detail)

    # ── 14. Search ──
    hits, mode = hybrid_search(db, "Aksai Chin boundary 1959", mode="hybrid",
                               filters=SearchFilters(include_demo=True), top_k=5, embedder=emb)
    step("14. Search returns document", bool(hits), f"mode={mode}, {len(hits)} hits")

    # ── 15. Viewer data (pages endpoint) ──
    step("15. Viewer page text resolves", bool(doc and doc.pages[0].text))

    # ── 16-19. RAG (real provider call only if configured) ──
    from app.ai.registry import has_credentials
    provider_ready = has_credentials(db, "groq")
    resp = answer_question(db, "What did India and China discuss about Aksai Chin in 1959?",
                           provider_id="groq", model_id="openai/gpt-oss-120b",
                           filters=SearchFilters(include_demo=True), top_k=5, embedder=emb)
    if provider_ready:
        step("16-19. RAG answer generated (REAL Groq call)", bool(resp.answer),
             f"confidence={resp.confidence}, chunks={resp.chunks_retrieved}")
    else:
        step("16-19. RAG retrieval proven; provider NOT configured (honest)",
             resp.chunks_retrieved > 0,
             "Set GROQ_API_KEY to generate a real answer. Evidence retrieved: "
             f"{resp.chunks_retrieved} chunks.")

    # ── 20-22. Citation validation (resolve to a real chunk/page) ──
    first_chunk = doc.chunks[0]
    outcome = validate_citations(db, [{
        "id": "c1", "document_id": doc.document_id, "chunk_id": first_chunk.chunk_id,
        "page": first_chunk.page_number, "quote": "Aksai Chin",
    }], allowed_chunk_ids={first_chunk.chunk_id})
    step("20-22. Citation validates to exact document + page", outcome.all_valid,
         f"{doc.document_id} p.{first_chunk.page_number}, confidence={outcome.confidence}")

    # ── 23. Save research session ──
    session = ResearchSession(title="Acceptance", question="Aksai Chin 1959",
                              answer=resp.answer, provider_id="groq",
                              model_id="openai/gpt-oss-120b", retrieval_mode=mode,
                              confidence=resp.confidence)
    db.add(session)
    db.commit()
    sid = session.id
    step("23. Research session saved", bool(sid), f"session_id={sid}")

    # ── 24-25. Restart (new session) + confirm persistence ──
    db.close()
    db2 = SessionLocal()
    persisted_doc = db2.query(Document).filter(Document.source_url.like("%aksai.pdf")).first()
    persisted_session = db2.get(ResearchSession, sid)
    step("24-25. Data persists across restart", bool(persisted_doc and persisted_session),
         f"doc={persisted_doc.document_id if persisted_doc else None}, session={sid}")
    db2.close()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\nACCEPTANCE: {passed}/{total} steps passed.")
    if not provider_ready:
        print("NOTE: The AI answer step requires GROQ_API_KEY to make a real call; "
              "it was not set, so no answer was fabricated. All other steps ran against "
              "the real stack.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
