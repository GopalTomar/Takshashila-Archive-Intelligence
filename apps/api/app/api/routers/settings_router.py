"""Non-secret application settings (retrieval defaults, appearance, system info).

Secret values (provider keys) are handled only by the providers router and are
never read or written here.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.db.base import dialect_name, get_db
from app.db.models import AppSetting

router = APIRouter(prefix="/api/settings", tags=["settings"])

_DEFAULT_RETRIEVAL = {
    "chunk_target_chars": 1200, "chunk_overlap_chars": 150,
    "top_k": 8, "hybrid_weight": 0.5,
}


def _get(db: Session, key: str):
    row = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one_or_none()
    return row


@router.get("/retrieval")
def get_retrieval(db: Session = Depends(get_db)) -> dict:
    row = _get(db, "retrieval")
    if row and row.value:
        try:
            return {**_DEFAULT_RETRIEVAL, **json.loads(row.value)}
        except json.JSONDecodeError:
            pass
    return dict(_DEFAULT_RETRIEVAL)


@router.put("/retrieval")
def put_retrieval(body: dict, db: Session = Depends(get_db)) -> dict:
    merged = {**_DEFAULT_RETRIEVAL, **{k: v for k, v in body.items() if v is not None}}
    row = _get(db, "retrieval")
    if not row:
        row = AppSetting(key="retrieval", is_secret=False)
        db.add(row)
    row.value = json.dumps(merged)
    db.commit()
    return merged


@router.get("/appearance")
def get_appearance(db: Session = Depends(get_db)) -> dict:
    row = _get(db, "appearance")
    default = {"theme": "system"}
    if row and row.value:
        try:
            return {**default, **json.loads(row.value)}
        except json.JSONDecodeError:
            pass
    return default


@router.put("/appearance")
def put_appearance(body: dict, db: Session = Depends(get_db)) -> dict:
    row = _get(db, "appearance")
    if not row:
        row = AppSetting(key="appearance", is_secret=False)
        db.add(row)
    row.value = json.dumps(body)
    db.commit()
    return body


@router.get("/system")
def system_info() -> dict:
    s = get_settings()
    return {
        "version": __version__,
        "database_dialect": dialect_name(),
        "is_postgres": s.is_postgres,
        "jobs_backend": "celery" if s.use_celery else "in-process",
        "embedding_provider": s.embedding_provider,
        "max_download_mb": s.max_download_mb,
        "cors_origins": s.cors_origin_list,
    }
