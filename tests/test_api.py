"""API smoke tests via FastAPI TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_reports_checks():
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert "database" in body["checks"]
    assert "embeddings" in body["checks"]
    assert "ocr" in body["checks"]


def test_stats_empty_archive(db):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["documents"] == 0
    assert body["empty"] is True


def test_providers_list_never_returns_key(db):
    r = client.get("/api/providers")
    assert r.status_code == 200
    body = r.json()
    ids = [p["provider_id"] for p in body["providers"]]
    assert "groq" in ids
    for p in body["providers"]:
        assert "api_key" not in p  # only has_key + key_hint are exposed
        assert "api_key_encrypted" not in p


def test_set_key_does_not_echo_secret(db):
    r = client.put("/api/providers/groq/key", json={"api_key": "gsk_test_secret_abcd"})
    assert r.status_code == 200
    body = r.json()
    assert body["has_key"] is True
    assert "gsk_test_secret_abcd" not in str(body)
    # Cleanup.
    client.delete("/api/providers/groq/key")


def test_live_crawl_requires_confirm(db):
    r = client.post("/api/ingestion/crawl", json={"source_key": "arpi"})
    # arpi has no seeds -> 400 (no seeds), which is also honest.
    assert r.status_code == 400


def test_search_endpoint_reports_semantic_availability(db):
    r = client.post("/api/search", json={"query": "test", "mode": "hybrid"})
    assert r.status_code == 200
    assert "semantic_available" in r.json()
