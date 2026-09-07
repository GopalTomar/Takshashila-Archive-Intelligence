"""SSRF protection and URL scope enforcement for the crawler/fetcher.

The crawler must never become an SSRF vector. Every URL is validated:
  * scheme must be http/https
  * host must resolve to a PUBLIC IP (no loopback/private/link-local/reserved)
  * host must be within the source's ``allowed_domains`` allowlist

A localhost allowlist entry (used by the test fixture server) is permitted
ONLY when explicitly present in ``allowed_domains`` — never by default.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(ValueError):
    pass


def _host_matches_allowlist(host: str, allowed_domains: list[str]) -> bool:
    host = host.lower()
    for dom in allowed_domains:
        dom = dom.lower().strip()
        if not dom:
            continue
        if host == dom or host.endswith("." + dom):
            return True
    return False


def _resolve_ips(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None)
    return list({info[4][0] for info in infos})


def validate_url(
    url: str,
    allowed_domains: list[str],
    *,
    allow_private: bool = False,
) -> str:
    """Validate a URL against SSRF rules and the domain allowlist.

    Returns the URL if valid, raises ``SSRFError`` otherwise.
    ``allow_private`` is only set True for local test fixtures.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"scheme not allowed: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise SSRFError("URL has no host")

    if allowed_domains and not _host_matches_allowlist(host, allowed_domains):
        raise SSRFError(f"host {host!r} not in allowed_domains")

    # Resolve and check every IP.
    try:
        ips = _resolve_ips(host)
    except socket.gaierror as exc:
        raise SSRFError(f"could not resolve host {host!r}: {exc}") from exc

    for ip_str in ips:
        ip = ipaddress.ip_address(ip_str)
        is_bad = (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_multicast or ip.is_reserved or ip.is_unspecified
        )
        if is_bad and not allow_private:
            raise SSRFError(f"host {host!r} resolves to non-public IP {ip_str}")
    return url
