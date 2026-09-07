# Security

## Secrets

- Provider API keys are stored **encrypted at rest** (Fernet key derived from
  `APP_SECRET_KEY`), server-side only.
- Keys are **never** returned by the API (only `has_key` + masked hint), **never**
  logged (structured logging redacts secret-bearing keys and bearer tokens in
  `app/logging_config.py`), and **never** included in error messages.
- The browser never receives keys and never calls providers directly.

## SSRF protection (`app/security/ssrf.py`)

Every crawler/fetcher URL is validated:
- scheme must be http/https;
- host must be within the source's `allowed_domains` allowlist;
- host must resolve to a **public** IP (loopback/private/link-local/reserved/
  multicast rejected). `169.254.169.254` (cloud metadata) and private ranges are
  blocked. Localhost is allowed only for the explicit local test-fixture source.
- redirects are re-validated against the same rules.

## File security (`app/security/files.py`)

- Downloads validated by **magic bytes**, not filename extension.
- Filenames sanitised; path traversal blocked (`ensure_within`), so files can
  never be written or read outside the storage root.
- The file endpoint refuses `metadata_only` documents and any path outside the
  store root.

## API hardening (`app/main.py`)

- CORS restricted to `CORS_ORIGINS` (never `*`).
- Request body size limit (413 on oversize).
- Structured request IDs; unhandled errors return a generic message (no stack
  traces or secrets leaked to clients).
- Pydantic validation on all request bodies; size caps on query/question fields.

## Prompt-injection defence (spec 106)

Retrieved document text is untrusted input. It is wrapped in explicit delimiters
and the system prompt forbids treating any instruction inside evidence as a
command. Document text is data, never instructions. This protects citation
rules and security rules from being overridden by malicious document content.

## Rate limiting

The crawler rate-limits outbound requests per source config. API-level rate
limiting can be added at the reverse proxy for public deployments.

## Reporting

Do not commit secrets. `.gitignore` excludes `.env`, keys, and all archive data.
