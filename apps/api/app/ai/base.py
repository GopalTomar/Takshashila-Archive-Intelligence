"""AI provider interface + shared data types.

Adapters implement this interface. The rest of the application talks to the
interface only — never to a specific provider's SDK. Capabilities are declared
per model so the UI can show only compatible features.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class ModelCapabilities:
    model_id: str
    display_name: str
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_structured_output: bool = False
    supports_reasoning: bool = False
    supports_embeddings: bool = False
    supports_vision: bool = False
    context_window: int | None = None
    pricing_info: str | None = None
    availability_status: str = "unknown"
    is_embedding: bool = False


@dataclass
class ChatMessage:
    role: str  # system|user|assistant
    content: str


@dataclass
class ChatResult:
    text: str
    model_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ConnectionTest:
    ok: bool
    detail: str
    models_seen: int | None = None


class AIProvider(ABC):
    provider_id: str = "base"
    provider_name: str = "Base"

    def __init__(self, api_key: str | None, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        reasoning: str | None = None,
        response_format: dict | None = None,
    ) -> ChatResult: ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        reasoning: str | None = None,
    ) -> Iterator[str]: ...

    def structured_output(
        self, messages: list[ChatMessage], *, model: str, schema: dict, **kwargs
    ) -> ChatResult:
        """Default: request JSON object response format. Adapters may override."""
        return self.chat(messages, model=model, response_format={"type": "json_object"}, **kwargs)

    @abstractmethod
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]: ...

    @abstractmethod
    def list_models(self) -> list[ModelCapabilities]: ...

    @abstractmethod
    def test_connection(self) -> ConnectionTest: ...
