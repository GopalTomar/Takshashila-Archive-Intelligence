"""Structured logging with secret redaction.

Never logs API keys, tokens, passwords, or Authorization headers. The
``redact`` processor scrubs common secret-bearing keys and any value that
looks like a bearer token before the record is emitted.
"""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

_SECRET_KEYS = {
    "api_key", "apikey", "authorization", "auth", "token", "access_token",
    "secret", "password", "groq_api_key", "openai_api_key", "anthropic_api_key",
    "embedding_api_key", "x-api-key", "app_secret_key",
}
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")
_KEYISH_RE = re.compile(r"\b(sk|gsk|xai|or)-[A-Za-z0-9._\-]{8,}\b")


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        value = _BEARER_RE.sub("Bearer [REDACTED]", value)
        value = _KEYISH_RE.sub("[REDACTED]", value)
    return value


def redact(_logger, _method, event_dict: dict) -> dict:
    for key in list(event_dict.keys()):
        if key.lower() in _SECRET_KEYS:
            event_dict[key] = "[REDACTED]"
        else:
            event_dict[key] = _scrub_value(event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "takshashila"):
    return structlog.get_logger(name)
