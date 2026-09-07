#!/usr/bin/env python3
"""Generate archive_manifest.csv and archive_manifest.json from the database.

Real data only — reads actual document rows. Never exports secrets.
Usage:
    PYTHONPATH=apps/api python scripts/generate_manifest.py [--include-demo]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

FIELDS = [
    "document_id", "title", "author", "date", "type", "source_url", "archived_url",
    "local_path", "sha256", "mime_type", "file_size", "page_count",
    "ocr_status", "index_status", "rights_status", "retrieved_at",
]


def main() -> int:
    include_demo = "--include-demo" in sys.argv
    from app.db.base import SessionLocal
    from app.db.models import Document

    db = SessionLocal()
    rows = []
    q = db.query(Document)
    if not include_demo:
        q = q.filter(Document.is_demo.is_(False))
    for d in q.all():
        rows.append({
            "document_id": d.document_id, "title": d.title, "author": d.author,
            "date": d.doc_date, "type": d.document_type, "source_url": d.source_url,
            "archived_url": d.archived_url, "local_path": d.local_path, "sha256": d.sha256,
            "mime_type": d.mime_type, "file_size": d.file_size, "page_count": d.page_count,
            "ocr_status": d.ocr_status.value, "index_status": d.index_status.value,
            "rights_status": d.rights_status,
            "retrieved_at": d.retrieved_at.isoformat() if d.retrieved_at else None,
        })
    db.close()

    (ROOT / "archive_manifest.json").write_text(json.dumps({"documents": rows}, indent=2))
    with open(ROOT / "archive_manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} records to archive_manifest.csv / .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
