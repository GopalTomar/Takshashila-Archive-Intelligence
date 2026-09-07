# AI providers

## Abstraction

`app/ai/base.py` defines the `AIProvider` interface (`chat`, `stream_chat`,
`structured_output`, `embed`, `list_models`, `test_connection`). Adapters live
in `app/ai/providers/`:

- `openai_compatible.py` — the core adapter (OpenAI-shaped `/chat/completions`,
  `/models`, `/embeddings`).
- `groq.py`, `openai.py`, `local.py` — thin subclasses with default base URLs.

The UI and RAG layer depend only on the interface — no provider-specific logic
leaks into the UI. The UI → API → AI service → adapter.

## Capability registry

`app/ai/registry.py` holds a `DEFAULT_CATALOG` describing each provider and its
default models with capabilities: `supports_streaming/tools/structured_output/
reasoning/embeddings/vision`, `context_window`, `pricing_info`,
`availability_status`. The UI shows only compatible features (e.g. the reasoning
selector appears only for reasoning-capable models).

**Availability is validated, not asserted** — models default to `unknown` until
a live `test_connection` / `refresh-models` call. `list_models` fetches live
models where the provider supports it (spec 70).

## Groq (first-class)

- Base URL `https://api.groq.com/openai/v1`.
- Models include `openai/gpt-oss-120b` and `openai/gpt-oss-20b`.
- Pricing is **never** hard-coded as "free": the app shows "Provider pricing/
  availability depends on the provider account."
- Key via `GROQ_API_KEY` env or Settings → AI Providers.

## Other providers

- **OpenAI** — `OPENAI_API_KEY`.
- **OpenAI-compatible (custom)** — set base URL + key (OpenRouter, vLLM, LM
  Studio, etc.).
- **Local** — OpenAI-compatible endpoint on localhost, no cloud key required.
- **Anthropic** — registry entry present; a native adapter is a documented TODO.

## Key security (spec 5, 40)

Keys are:
- stored **encrypted at rest** (Fernet, derived from `APP_SECRET_KEY`);
- **never** returned by the API (only `has_key` + a masked hint like `****abcd`);
- **never** logged (structured logging redacts secret keys and bearer tokens);
- **never** included in error messages (provider errors redact the key).

## Test connection

`POST /api/providers/{id}/test` makes a **real** minimal request (lists models).
Success/failure is reported honestly — never faked.

## Embeddings

Configured independently (`EMBEDDING_PROVIDER/MODEL/DIMENSIONS/BATCH_SIZE`). See
[`SEARCH.md`](SEARCH.md). If unset, semantic search is disabled and keyword
search remains available.
