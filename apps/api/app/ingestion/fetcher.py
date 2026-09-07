"""SSRF-safe HTTP fetch with size limits, retries and content-type recording."""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.ingestion.robots import USER_AGENT
from app.security.ssrf import validate_url


class FetchError(Exception):
    pass


class TransientFetchError(FetchError):
    pass


@dataclass
class FetchResult:
    url: str
    status_code: int
    content_type: str | None
    content: bytes
    size: int


@retry(
    retry=retry_if_exception_type(TransientFetchError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    reraise=True,
)
def fetch(
    url: str,
    allowed_domains: list[str],
    *,
    allow_private: bool = False,
    binary: bool = False,
) -> FetchResult:
    settings = get_settings()
    max_bytes = settings.max_download_mb * 1024 * 1024

    # SSRF validation on every request (revalidated after redirects below).
    validate_url(url, allowed_domains, allow_private=allow_private)

    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            with client.stream("GET", url, headers=headers) as resp:
                # Revalidate the final URL after redirects.
                final_url = str(resp.url)
                validate_url(final_url, allowed_domains, allow_private=allow_private)

                if resp.status_code >= 500:
                    raise TransientFetchError(f"server error {resp.status_code}")
                if resp.status_code == 429:
                    raise TransientFetchError("rate limited (429)")

                content_type = resp.headers.get("content-type")
                declared = resp.headers.get("content-length")
                if declared and int(declared) > max_bytes:
                    raise FetchError(f"content-length {declared} exceeds max {max_bytes}")

                chunks = bytearray()
                for chunk in resp.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > max_bytes:
                        raise FetchError(f"download exceeds max {max_bytes} bytes")

                return FetchResult(
                    url=final_url,
                    status_code=resp.status_code,
                    content_type=content_type,
                    content=bytes(chunks),
                    size=len(chunks),
                )
    except httpx.TimeoutException as exc:
        raise TransientFetchError(f"timeout: {exc}") from exc
    except httpx.TransportError as exc:
        raise TransientFetchError(f"transport error: {exc}") from exc
