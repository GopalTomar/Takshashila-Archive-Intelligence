"""Generic OpenAI-compatible provider adapter.

Works with any endpoint exposing /chat/completions, /models and /embeddings in
the OpenAI shape: Groq, OpenAI, OpenRouter, vLLM, LM Studio, etc. Capability
detection lives in the registry; this adapter makes the real HTTP calls and
translates errors without ever leaking the API key.
"""
from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from app.ai.base import (
    AIProvider,
    ChatMessage,
    ChatResult,
    ConnectionTest,
    ModelCapabilities,
)


class ProviderError(Exception):
    pass


def _redact(text: str, api_key: str | None) -> str:
    if api_key and api_key in text:
        text = text.replace(api_key, "[REDACTED]")
    return text


class OpenAICompatibleProvider(AIProvider):
    provider_id = "openai_compatible"
    provider_name = "OpenAI-compatible"
    default_base_url = "https://api.openai.com/v1"

    def __init__(self, api_key: str | None, base_url: str | None = None, timeout: float = 60.0):
        super().__init__(api_key, base_url or self.default_base_url)
        self.timeout = timeout

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    def _post(self, path: str, payload: dict, *, stream: bool = False):
        try:
            client = httpx.Client(timeout=self.timeout)
            resp = client.post(self._url(path), headers=self._headers(), json=payload)
            if resp.status_code == 401:
                raise ProviderError("authentication failed (invalid API key)")
            if resp.status_code == 404:
                raise ProviderError(f"endpoint not found: {path} (check base URL/model)")
            if resp.status_code == 429:
                raise ProviderError("rate limited by provider (429)")
            if resp.status_code >= 400:
                detail = _redact(resp.text[:500], self.api_key)
                raise ProviderError(f"provider error {resp.status_code}: {detail}")
            return resp
        except httpx.TimeoutException as exc:
            raise ProviderError(f"provider timeout: {exc}") from exc
        except httpx.TransportError as exc:
            raise ProviderError(f"provider connection error: {_redact(str(exc), self.api_key)}") from exc

    def chat(
        self, messages, *, model, temperature=None, max_tokens=None,
        reasoning=None, response_format=None,
    ) -> ChatResult:
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if reasoning:
            payload["reasoning_effort"] = reasoning
        if response_format:
            payload["response_format"] = response_format

        resp = self._post("/chat/completions", payload)
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            model_id=model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            finish_reason=choice.get("finish_reason"),
            raw=data,
        )

    def stream_chat(
        self, messages, *, model, temperature=None, max_tokens=None, reasoning=None,
    ) -> Iterator[str]:
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if reasoning:
            payload["reasoning_effort"] = reasoning
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST", self._url("/chat/completions"),
                    headers=self._headers(), json=payload,
                ) as resp:
                    if resp.status_code >= 400:
                        body = _redact(resp.read().decode("utf-8", "ignore")[:500], self.api_key)
                        raise ProviderError(f"provider error {resp.status_code}: {body}")
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        delta = (obj.get("choices") or [{}])[0].get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            yield piece
        except httpx.TransportError as exc:
            raise ProviderError(f"provider connection error: {_redact(str(exc), self.api_key)}") from exc

    def embed(self, texts, *, model) -> list[list[float]]:
        resp = self._post("/embeddings", {"model": model, "input": texts})
        data = resp.json()
        items = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [item["embedding"] for item in items]

    def list_models(self) -> list[ModelCapabilities]:
        try:
            client = httpx.Client(timeout=self.timeout)
            resp = client.get(self._url("/models"), headers=self._headers())
            if resp.status_code >= 400:
                return []
            data = resp.json()
            out = []
            for m in data.get("data", []):
                mid = m.get("id")
                if not mid:
                    continue
                out.append(ModelCapabilities(model_id=mid, display_name=mid, availability_status="ok"))
            return out
        except Exception:
            return []

    def test_connection(self) -> ConnectionTest:
        """Real minimal request: list models. Never fabricated."""
        if not self.api_key and "localhost" not in (self.base_url or "") and "127.0.0.1" not in (self.base_url or ""):
            return ConnectionTest(ok=False, detail="no API key configured")
        try:
            client = httpx.Client(timeout=self.timeout)
            resp = client.get(self._url("/models"), headers=self._headers())
            if resp.status_code == 401:
                return ConnectionTest(ok=False, detail="authentication failed (invalid API key)")
            if resp.status_code >= 400:
                return ConnectionTest(ok=False, detail=f"HTTP {resp.status_code}")
            data = resp.json()
            n = len(data.get("data", []))
            return ConnectionTest(ok=True, detail="connection ok", models_seen=n)
        except httpx.TimeoutException:
            return ConnectionTest(ok=False, detail="timeout")
        except Exception as exc:
            return ConnectionTest(ok=False, detail=_redact(str(exc), self.api_key))
