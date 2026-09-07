"""robots.txt awareness. We respect crawl directives; we never bypass them."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "TakshashilaArchiveBot/0.1 (+respectful; contact archive operator)"


class RobotsCache:
    def __init__(self, client: httpx.Client | None = None):
        self._parsers: dict[str, RobotFileParser | None] = {}
        self._client = client

    def _robots_url(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}/robots.txt"

    def _load(self, url: str) -> RobotFileParser | None:
        robots_url = self._robots_url(url)
        if robots_url in self._parsers:
            return self._parsers[robots_url]
        rp = RobotFileParser()
        try:
            client = self._client or httpx.Client(timeout=10.0, follow_redirects=True)
            resp = client.get(robots_url, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                # No robots.txt => allowed by convention.
                rp = None
            if self._client is None:
                client.close()
        except Exception:
            rp = None
        self._parsers[robots_url] = rp
        return rp

    def allowed(self, url: str) -> bool:
        rp = self._load(url)
        if rp is None:
            return True
        return rp.can_fetch(USER_AGENT, url)
