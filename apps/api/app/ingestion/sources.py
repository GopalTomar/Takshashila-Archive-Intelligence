"""Load source definitions from config/sources.yaml and sync to the DB."""
from __future__ import annotations

import functools

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config_dir
from app.db.models import Source


@functools.lru_cache
def load_sources_config() -> list[dict]:
    path = config_dir() / "sources.yaml"
    if not path.exists():
        return []
    with open(path) as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("sources", [])


def get_source_config(source_key: str) -> dict | None:
    for s in load_sources_config():
        if s.get("id") == source_key:
            return s
    return None


def sync_source_to_db(db: Session, cfg: dict) -> Source:
    key = cfg["id"]
    row = db.execute(select(Source).where(Source.source_key == key)).scalar_one_or_none()
    rights = cfg.get("rights", {}) or {}
    prefix = key.upper()[:8]
    if not row:
        row = Source(
            source_key=key,
            name=cfg.get("name", key),
            base_url=cfg.get("base_url") or None,
            doc_prefix=prefix,
            rights_status=rights.get("default_rights_status"),
            access_status=rights.get("default_access_status"),
            copyright_notes=rights.get("copyright_notes"),
            is_demo=(key == "fixtures"),
        )
        db.add(row)
        db.flush()
    return row
