"""DEMO seed data.

Generates SYNTHETIC PDFs (clearly labelled "DEMO DATA — NOT ARCHIVAL
MATERIAL") and ingests them through the real pipeline into a dedicated demo
source and collection with ``is_demo=True``. Demo records are never mixed with
production archival records. The synthetic text is illustrative and fictional —
it is NOT a real historical document and must not be cited as one.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedder
from app.db.models import ArchiveCollection, Document, Source
from app.ingestion.pipeline import ingest_document_bytes

DEMO_BANNER = "DEMO DATA — NOT ARCHIVAL MATERIAL (synthetic, illustrative only)"

# Synthetic documents. Content is fictional and clearly illustrative.
DEMO_DOCS = [
    {
        "filename": "demo_aksai_chin_note_1959.pdf",
        "title": "DEMO: Note on Aksai Chin Frontier Concerns (synthetic, 1959)",
        "pages": [
            f"{DEMO_BANNER}\n\nNote on Aksai Chin Frontier Concerns\n(SYNTHETIC DEMONSTRATION DOCUMENT — 1959)\n\n"
            "This synthetic note illustrates how a diplomatic memorandum about the "
            "Aksai Chin region and the India-China boundary might be catalogued. "
            "It references the McMahon Line and Ladakh purely to demonstrate topic "
            "tagging. Nothing here is a real historical statement.",
            f"{DEMO_BANNER}\n\nPage 2. The demonstration continues discussing the "
            "Tibet frontier and diplomacy between India and China in 1959. The "
            "Dalai Lama and Lhasa are mentioned only to exercise entity extraction. "
            "This page exists to show page-level provenance and citation to page 2.",
        ],
    },
    {
        "filename": "demo_tibet_1962_summary.pdf",
        "title": "DEMO: Summary of 1962 Border Situation (synthetic)",
        "pages": [
            f"{DEMO_BANNER}\n\nSummary of the 1962 Border Situation\n(SYNTHETIC)\n\n"
            "A fictional summary used to demonstrate hybrid search across the 1962 "
            "India-China War topic, NEFA, and Arunachal Pradesh. The text is not a "
            "primary source and should never be treated as one.",
            f"{DEMO_BANNER}\n\nPage 2 discusses military movements and foreign policy "
            "in a synthetic manner, mentioning China and India to demonstrate "
            "country entity linking and timeline extraction workflows.",
        ],
    },
]


def _make_pdf(pages: list[str]) -> bytes:
    import fitz
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 545, 780), text, fontsize=11, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def _get_or_create_demo_source(db: Session) -> Source:
    row = db.execute(select(Source).where(Source.source_key == "demo")).scalar_one_or_none()
    if not row:
        row = Source(
            source_key="demo", name="DEMO source (synthetic — not archival)",
            doc_prefix="DEMO", is_demo=True,
            rights_status="synthetic-demo", access_status="demo",
            copyright_notes="Synthetic demo data. Not archival material.",
        )
        db.add(row)
        db.flush()
    return row


def _get_or_create_demo_collection(db: Session) -> ArchiveCollection:
    row = db.execute(
        select(ArchiveCollection).where(ArchiveCollection.collection_key == "demo")
    ).scalar_one_or_none()
    if not row:
        row = ArchiveCollection(
            collection_key="demo", name="DEMO collection (synthetic)",
            description=DEMO_BANNER, is_demo=True,
        )
        db.add(row)
        db.flush()
    return row


def seed_demo(db: Session) -> list[str]:
    """Ingest demo documents idempotently. Returns list of document_ids."""
    source = _get_or_create_demo_source(db)
    collection = _get_or_create_demo_collection(db)
    embedder = get_embedder(db)
    created: list[str] = []
    for spec in DEMO_DOCS:
        content = _make_pdf(spec["pages"])
        doc = ingest_document_bytes(
            db, source=source, content=content,
            source_url=f"demo://{spec['filename']}",
            filename=spec["filename"], content_type="application/pdf",
            is_demo=True, collection_id=collection.id, embedder=embedder,
        )
        # Override the title with the explicit demo title.
        if doc.title != spec["title"]:
            doc.title = spec["title"]
        doc.document_type = "demo-synthetic"
        created.append(doc.document_id)
    db.commit()
    return created


def clear_demo(db: Session) -> int:
    docs = db.execute(select(Document).where(Document.is_demo.is_(True))).scalars().all()
    n = len(docs)
    for d in docs:
        db.delete(d)
    db.commit()
    return n
