"""Wayback Machine discovery for dead source URLs.

Only used when a source URL is unavailable and wayback_fallback is enabled.
Never overwrites the original source_url — returns a separate archived_url.
Never claims archival provenance unless the availability API confirms a
snapshot exists.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class WaybackResult:
    original_url: str
    archived_url: str | None
    snapshot_timestamp: str | None
    archive_provider: str = "wayback"
    archive_status: str = "not_found"  # found|not_found|error


def lookup(original_url: str, timeout: float = 15.0) -> WaybackResult:
    api = "https://archive.org/wayback/available"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(api, params={"url": original_url})
            if resp.status_code != 200:
                return WaybackResult(original_url, None, None, archive_status="error")
            data = resp.json()
            snap = (data.get("archived_snapshots") or {}).get("closest")
            if snap and snap.get("available") and snap.get("url"):
                return WaybackResult(
                    original_url=original_url,
                    archived_url=snap["url"],
                    snapshot_timestamp=snap.get("timestamp"),
                    archive_status="found",
                )
            return WaybackResult(original_url, None, None, archive_status="not_found")
    except Exception:
        return WaybackResult(original_url, None, None, archive_status="error")
