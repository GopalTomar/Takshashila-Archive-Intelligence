"""Provider adapters: unavailable/invalid-key handling, no secret leakage."""
from __future__ import annotations

from app.ai.base import ChatMessage
from app.ai.providers.openai_compatible import OpenAICompatibleProvider, ProviderError


def test_test_connection_no_key_is_honest():
    p = OpenAICompatibleProvider(api_key=None, base_url="https://api.example-nonexistent.invalid/v1")
    result = p.test_connection()
    assert result.ok is False
    assert "no api key" in result.detail.lower()


def test_invalid_endpoint_returns_error_not_crash():
    p = OpenAICompatibleProvider(api_key="bogus", base_url="https://nonexistent.invalid.example/v1")
    result = p.test_connection()
    assert result.ok is False  # honest failure, never faked success


def test_provider_error_redacts_key():
    key = "gsk_secret_value_123"
    p = OpenAICompatibleProvider(api_key=key, base_url="https://nonexistent.invalid.example/v1")
    try:
        p.chat([ChatMessage("user", "hi")], model="x")
    except ProviderError as exc:
        assert key not in str(exc)


def test_registry_default_catalog_has_groq_models():
    from app.ai.registry import DEFAULT_CATALOG
    groq = DEFAULT_CATALOG["groq"]
    model_ids = [m.model_id for m in groq.default_models]
    assert "openai/gpt-oss-120b" in model_ids
    assert "openai/gpt-oss-20b" in model_ids
    # Pricing is never asserted as "free".
    for m in groq.default_models:
        assert "free" not in (m.pricing_info or "").lower()
