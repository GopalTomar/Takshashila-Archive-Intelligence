"""Local model provider (OpenAI-compatible endpoint on localhost).

For vLLM / LM Studio / Ollama's OpenAI-compatible server. No cloud key needed.
"""
from __future__ import annotations

from app.ai.providers.openai_compatible import OpenAICompatibleProvider


class LocalProvider(OpenAICompatibleProvider):
    provider_id = "local"
    provider_name = "Local model"
    default_base_url = "http://localhost:11434/v1"
