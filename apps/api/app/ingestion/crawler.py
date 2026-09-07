"""Configurable, robots-aware, SSRF-safe crawler.

Discovers internal links and document URLs from seed pages, normalises and
deduplicates URLs, respects robots.txt, rate-limits, and produces an honest
crawl report. It NEVER claims to have found "everything" — it reports exactly
what was discovered, attempted, downloaded, failed, blocked and skipped.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.ingestion.fetcher import FetchError, fetch
from app.ingestion.robots import RobotsCache
from app.security.ssrf import SSRFError, validate_url


def normalize_url(url: str) -> str:
    url, _frag = urldefrag(url)
    p = urlparse(url)
    scheme = p.scheme.lower()
    netloc = p.netloc.lower()
    path = p.path or "/"
    # Drop trailing slash duplication except root.
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, p.params, p.query, ""))


@dataclass
class DiscoveredItem:
    url: str
    outcome: str  # discovered|downloaded|failed|blocked|skipped|duplicate
    http_status: int | None = None
    content_type: str | None = None
    file_size: int | None = None
    reason: str | None = None
    content: bytes | None = None  # only for downloaded document bytes


@dataclass
class CrawlReport:
    seed_urls: list[str]
    started_at: float
    finished_at: float | None = None
    urls_discovered: int = 0
    urls_attempted: int = 0
    urls_downloaded: int = 0
    urls_failed: int = 0
    urls_blocked: int = 0
    urls_skipped: int = 0
    pdfs_discovered: int = 0
    documents_discovered: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "seed_urls": self.seed_urls,
            "duration_seconds": round((self.finished_at or time.time()) - self.started_at, 2),
            "urls_discovered": self.urls_discovered,
            "urls_attempted": self.urls_attempted,
            "urls_downloaded": self.urls_downloaded,
            "urls_failed": self.urls_failed,
            "urls_blocked": self.urls_blocked,
            "urls_skipped": self.urls_skipped,
            "pdfs_discovered": self.pdfs_discovered,
            "documents_discovered": self.documents_discovered,
            "duplicates": self.duplicates,
            "errors": self.errors[:100],
        }


class Crawler:
    def __init__(
        self,
        *,
        allowed_domains: list[str],
        file_extensions: list[str],
        max_pages: int = 100,
        max_depth: int = 3,
        requests_per_second: float = 1.0,
        respect_robots: bool = True,
        allow_private: bool = False,
    ):
        self.allowed_domains = allowed_domains
        self.file_extensions = [e.lower() for e in file_extensions]
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self.respect_robots = respect_robots
        self.allow_private = allow_private
        self.robots = RobotsCache()
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request = time.time()

    def _is_document(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in self.file_extensions)

    def crawl(self, seed_urls: list[str]):
        """Generator yielding ``DiscoveredItem`` objects as they are found.

        Document URLs are yielded with their downloaded bytes; HTML pages are
        parsed for further links but not themselves yielded as documents.
        """
        report = CrawlReport(seed_urls=list(seed_urls), started_at=time.time())
        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        for s in seed_urls:
            n = normalize_url(s)
            if n not in seen:
                seen.add(n)
                queue.append((n, 0))
                report.urls_discovered += 1

        pages_fetched = 0
        while queue and pages_fetched < self.max_pages:
            url, depth = queue.popleft()

            # Scope / SSRF check.
            try:
                validate_url(url, self.allowed_domains, allow_private=self.allow_private)
            except SSRFError as exc:
                report.urls_blocked += 1
                yield DiscoveredItem(url=url, outcome="blocked", reason=f"ssrf/scope: {exc}")
                continue

            # robots.
            if self.respect_robots and not self.robots.allowed(url):
                report.urls_blocked += 1
                yield DiscoveredItem(url=url, outcome="blocked", reason="disallowed by robots.txt")
                continue

            is_doc = self._is_document(url)
            self._rate_limit()
            report.urls_attempted += 1
            try:
                result = fetch(
                    url, self.allowed_domains,
                    allow_private=self.allow_private, binary=is_doc,
                )
            except FetchError as exc:
                report.urls_failed += 1
                report.errors.append(f"{url}: {exc}")
                yield DiscoveredItem(url=url, outcome="failed", reason=str(exc))
                continue

            pages_fetched += 1
            ctype = (result.content_type or "").lower()

            # Treat non-2xx as failure — never ingest an error page as a document.
            if result.status_code >= 400:
                report.urls_failed += 1
                report.errors.append(f"{url}: HTTP {result.status_code}")
                yield DiscoveredItem(url=result.url, outcome="failed",
                                     http_status=result.status_code,
                                     content_type=result.content_type,
                                     reason=f"HTTP {result.status_code}")
                continue

            if is_doc or "application/pdf" in ctype:
                # Validate the payload really is a document (magic bytes), not an
                # HTML error/redirect page served with a .pdf URL.
                from app.security.files import sniff_mime
                if url.lower().endswith(".pdf") and sniff_mime(result.content) != "application/pdf":
                    report.urls_failed += 1
                    report.errors.append(f"{result.url}: expected PDF but content is not a PDF")
                    yield DiscoveredItem(url=result.url, outcome="failed",
                                         http_status=result.status_code,
                                         content_type=result.content_type,
                                         reason="content is not a valid PDF")
                    continue
                report.pdfs_discovered += 1 if "pdf" in ctype or url.lower().endswith(".pdf") else 0
                report.documents_discovered += 1
                report.urls_downloaded += 1
                yield DiscoveredItem(
                    url=result.url, outcome="downloaded",
                    http_status=result.status_code, content_type=result.content_type,
                    file_size=result.size, content=result.content,
                )
                continue

            # HTML page: parse for links, don't emit as document.
            if "html" not in ctype and not url.endswith((".html", "/")):
                report.urls_skipped += 1
                yield DiscoveredItem(url=result.url, outcome="skipped",
                                     http_status=result.status_code,
                                     content_type=result.content_type,
                                     reason="non-HTML, non-document content")
                continue

            if depth >= self.max_depth:
                continue

            try:
                soup = BeautifulSoup(result.content, "lxml")
            except Exception:
                soup = BeautifulSoup(result.content, "html.parser")

            for a in soup.find_all("a", href=True):
                child = normalize_url(urljoin(result.url, a["href"]))
                if child in seen:
                    continue
                # Only follow same-scope links.
                host = urlparse(child).hostname or ""
                in_scope = any(
                    host == d.lower() or host.endswith("." + d.lower())
                    for d in self.allowed_domains
                ) if self.allowed_domains else True
                if not in_scope:
                    continue
                seen.add(child)
                report.urls_discovered += 1
                queue.append((child, depth + 1))

        report.finished_at = time.time()
        # Final sentinel carrying the report.
        yield DiscoveredItem(url="__report__", outcome="report", reason=None, content=None)
        self.last_report = report
