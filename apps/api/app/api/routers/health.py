"""Health / readiness / observability endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.ai.embeddings import get_embedder
from app.config import get_settings
from app.db.base import dialect_name, get_db
from app.ocr.pdf import tesseract_available, tesseract_version

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "takshashila-api", "version": __version__}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    checks: dict = {}
    ok = True

    # Database.
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True, "dialect": dialect_name()}
    except Exception as exc:
        ok = False
        checks["database"] = {"ok": False, "error": str(exc)}

    # pgvector (only meaningful on postgres).
    if dialect_name() == "postgresql":
        try:
            row = db.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'")).first()
            checks["pgvector"] = {"available": bool(row), "version": row[0] if row else None}
        except Exception as exc:
            checks["pgvector"] = {"available": False, "error": str(exc)}
    else:
        checks["pgvector"] = {"available": False, "note": "not postgres; using python cosine fallback"}

    # Embeddings.
    emb = get_embedder(db).status()
    checks["embeddings"] = {
        "enabled": emb.enabled, "provider": emb.provider,
        "is_real_semantic": emb.is_real_semantic, "detail": emb.detail,
    }

    # OCR.
    checks["ocr"] = {"tesseract_available": tesseract_available(), "version": tesseract_version()}

    # Jobs.
    s = get_settings()
    checks["jobs"] = {"backend": "celery" if s.use_celery else "in-process"}

    return {"ready": ok, "checks": checks}
