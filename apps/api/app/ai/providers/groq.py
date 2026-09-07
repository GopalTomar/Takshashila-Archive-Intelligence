"""Groq provider — first-class, OpenAI-compatible endpoint."""
from __future__ import annotations

from app.ai.providers.openai_compatible import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    provider_id = "groq"
    provider_name = "Groq"
    default_base_url = "https://api.groq.com/openai/v1"

    def __init__(self, api_key, base_url=None, timeout: float = 60.0):
        super().__init__(api_key, base_url or self.default_base_url, timeout=timeout)
