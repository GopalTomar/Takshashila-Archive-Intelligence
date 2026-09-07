"""OpenAI provider (OpenAI-compatible endpoint)."""
from __future__ import annotations

from app.ai.providers.openai_compatible import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    provider_id = "openai"
    provider_name = "OpenAI"
    default_base_url = "https://api.openai.com/v1"
