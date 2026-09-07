"""Provider + model capability registry and provider factory.

The registry ships sensible DEFAULT model capabilities so the UI has something
to show before a live /models call, but model availability is always validated
against the provider (never asserted as permanently true). Pricing is never
invented — it is shown as depending on the provider account.

The factory resolves the API key for a provider from, in order:
  1. an encrypted key stored via the Settings UI (app DB), else
  2. the server environment variable.
Keys are used server-side only and never returned to clients.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, ModelCapabilities
from app.ai.providers.groq import GroqProvider
from app.ai.providers.local import LocalProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.config import get_settings
from app.db.models import AiProvider as AiProviderRow
from app.security.crypto import decrypt_secret

PRICING_NOTE = "Provider pricing/availability depends on the provider account."

_ADAPTERS = {
    "groq": GroqProvider,
    "openai": OpenAIProvider,
    "local": LocalProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


@dataclass
class ProviderInfo:
    provider_id: str
    provider_name: str
    adapter: str
    default_base_url: str | None
    default_models: list[ModelCapabilities]


# Default catalog. Availability is "unknown" until a live check runs.
DEFAULT_CATALOG: dict[str, ProviderInfo] = {
    "groq": ProviderInfo(
        provider_id="groq",
        provider_name="Groq",
        adapter="groq",
        default_base_url="https://api.groq.com/openai/v1",
        default_models=[
            ModelCapabilities(
                model_id="openai/gpt-oss-120b",
                display_name="GPT-OSS 120B",
                supports_streaming=True, supports_tools=True,
                supports_structured_output=True, supports_reasoning=True,
                context_window=131072, pricing_info=PRICING_NOTE,
                availability_status="unknown",
            ),
            ModelCapabilities(
                model_id="openai/gpt-oss-20b",
                display_name="GPT-OSS 20B",
                supports_streaming=True, supports_tools=True,
                supports_structured_output=True, supports_reasoning=True,
                context_window=131072, pricing_info=PRICING_NOTE,
                availability_status="unknown",
            ),
        ],
    ),
    "openai": ProviderInfo(
        provider_id="openai",
        provider_name="OpenAI",
        adapter="openai",
        default_base_url="https://api.openai.com/v1",
        default_models=[
            ModelCapabilities(
                model_id="gpt-4o-mini", display_name="GPT-4o mini",
                supports_streaming=True, supports_tools=True,
                supports_structured_output=True, supports_vision=True,
                pricing_info=PRICING_NOTE, availability_status="unknown",
            ),
            ModelCapabilities(
                model_id="text-embedding-3-small", display_name="text-embedding-3-small",
                supports_embeddings=True, is_embedding=True,
                pricing_info=PRICING_NOTE, availability_status="unknown",
            ),
        ],
    ),
    "openai_compatible": ProviderInfo(
        provider_id="openai_compatible",
        provider_name="OpenAI-compatible (custom endpoint)",
        adapter="openai_compatible",
        default_base_url="",
        default_models=[],
    ),
    "local": ProviderInfo(
        provider_id="local",
        provider_name="Local model",
        adapter="local",
        default_base_url="http://localhost:11434/v1",
        default_models=[],
    ),
    "anthropic": ProviderInfo(
        provider_id="anthropic",
        provider_name="Anthropic (future integration)",
        adapter="openai_compatible",  # placeholder; native adapter is a TODO
        default_base_url="",
        default_models=[],
    ),
}


def _stored_provider(db: Session, provider_id: str) -> AiProviderRow | None:
    return db.execute(
        select(AiProviderRow).where(AiProviderRow.provider_id == provider_id)
    ).scalar_one_or_none()


def resolve_credentials(db: Session, provider_id: str) -> tuple[str, str | None]:
    """Return (api_key, base_url) for a provider — from DB first, then env."""
    settings = get_settings()
    info = DEFAULT_CATALOG.get(provider_id)
    base_url = info.default_base_url if info else None
    api_key = ""

    row = _stored_provider(db, provider_id)
    if row:
        if row.base_url:
            base_url = row.base_url
        if row.api_key_encrypted:
            try:
                api_key = decrypt_secret(row.api_key_encrypted)
            except ValueError:
                api_key = ""
    if not api_key:
        api_key = settings.env_api_key_for(provider_id)
    if not base_url and provider_id == "openai_compatible":
        base_url = settings.openai_compatible_base_url or None
    return api_key, base_url


def build_provider(db: Session, provider_id: str) -> AIProvider:
    info = DEFAULT_CATALOG.get(provider_id)
    adapter = info.adapter if info else "openai_compatible"
    api_key, base_url = resolve_credentials(db, provider_id)
    cls = _ADAPTERS.get(adapter, OpenAICompatibleProvider)
    return cls(api_key=api_key or None, base_url=base_url)


def has_credentials(db: Session, provider_id: str) -> bool:
    api_key, base_url = resolve_credentials(db, provider_id)
    if provider_id == "local":
        return bool(base_url)
    return bool(api_key)
