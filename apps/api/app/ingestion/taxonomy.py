"""Load taxonomy config and provide deterministic topic/entity tagging.

Deterministic tagging only assigns a topic/entity when a configured keyword or
gazetteer name actually appears in the document text — with the matched snippet
stored as evidence. Nothing is tagged on a guess.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

import yaml

from app.config import config_dir


@functools.lru_cache
def load_taxonomy() -> dict:
    path = config_dir() / "taxonomy.yaml"
    if not path.exists():
        return {"topics": [], "entity_types": [], "gazetteer": {}}
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def match_topics(text: str) -> list[dict]:
    """Return [{key, label, evidence}] for topics whose keywords appear."""
    text_l = (text or "").lower()
    out = []
    for topic in load_taxonomy().get("topics", []):
        for kw in topic.get("keywords", []) or []:
            kw_l = kw.lower()
            pos = text_l.find(kw_l)
            if pos != -1:
                snippet = text[max(0, pos - 40): pos + len(kw) + 40].strip()
                out.append({"key": topic["id"], "label": topic["label"], "evidence": snippet})
                break
    return out


def match_entities(text: str) -> list[dict]:
    """Return [{type, name, mention}] for gazetteer names appearing in text."""
    out = []
    gazetteer = load_taxonomy().get("gazetteer", {}) or {}
    for etype, names in gazetteer.items():
        for name in names or []:
            pattern = r"\b" + re.escape(name) + r"\b"
            m = re.search(pattern, text or "", flags=re.IGNORECASE)
            if m:
                out.append({"type": etype, "name": name, "mention": m.group(0)})
    return out
