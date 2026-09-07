"""Pytest fixtures.

Tests run against the database in DATABASE_URL. The CI/dev harness points this
at a dedicated PostgreSQL test database so pgvector + full-text search are
exercised for real; if a plain SQLite URL is given, the portable fallbacks are
exercised instead. Tables are created once and truncated between tests.
"""
from __future__ import annotations

import io
import os
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

# Ensure the api package is importable and env has safe test defaults.
API_DIR = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_DIR))
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-please-change-1234567890")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "256")
os.environ.setdefault("JOBS_INLINE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./data/test.db")


@pytest.fixture(scope="session", autouse=True)
def _schema():
    from app.bootstrap import init_db, seed_registry
    from app.db.base import SessionLocal
    init_db()
    db = SessionLocal()
    try:
        seed_registry(db)
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    from app.db.base import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _clean(db):
    """Delete document-related rows before each test (keep provider/topic seed)."""
    from app.db import models as m
    from app.db.base import SessionLocal
    s = SessionLocal()
    try:
        for model in (
            m.Citation, m.AiRun, m.DocumentEvent, m.Event, m.DocumentEntity, m.Entity,
            m.DocumentTopic, m.DocumentChunk, m.DocumentPage, m.DocumentFile, m.DocumentVersion,
            m.OcrRun, m.CrawlItem, m.CrawlRun, m.ProcessingJob, m.ResearchNote,
            m.ResearchSession, m.SavedSearch, m.Document, m.ArchiveCollection,
        ):
            s.query(model).delete()
        # Reset source sequences but keep source rows.
        for src in s.query(m.Source).all():
            src.next_seq = 1
        s.commit()
    finally:
        s.close()
    yield


def make_text_pdf(pages: list[str]) -> bytes:
    import fitz
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 545, 780), text, fontsize=11, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def make_empty_pdf() -> bytes:
    import fitz
    doc = fitz.open()
    doc.new_page()  # blank page, no text
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def demo_source(db):
    from app.ingestion.sources import get_source_config, sync_source_to_db
    cfg = get_source_config("fixtures")
    return sync_source_to_db(db, cfg)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # silence
        pass


@pytest.fixture()
def fixture_server(tmp_path):
    """Serve a tiny site (index.html + a PDF) on 127.0.0.1:8899 for crawler tests."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(
        '<html><body><a href="/doc1.pdf">Doc 1</a> '
        '<a href="/page2.html">More</a></body></html>'
    )
    (site / "page2.html").write_text('<html><body><a href="/doc2.pdf">Doc 2</a></body></html>')
    (site / "doc1.pdf").write_bytes(make_text_pdf(["Aksai Chin frontier note. India China Tibet 1959."]))
    (site / "doc2.pdf").write_bytes(make_text_pdf(["NEFA 1962 war summary. Dalai Lama Lhasa."]))
    # robots.txt allowing all.
    (site / "robots.txt").write_text("User-agent: *\nAllow: /\n")

    os.chdir(site)
    server = HTTPServer(("127.0.0.1", 8899), _QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:8899"
    server.shutdown()
