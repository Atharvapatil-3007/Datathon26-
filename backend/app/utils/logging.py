"""Structured logging helpers.

We intentionally keep this simple (stdlib `logging` + JSON-ish key/value
formatter) so the module has no third-party dependency and can be replaced
later with structlog or loguru without touching call sites.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from app.config.settings import get_settings


_CONFIGURED = False


class _KeyValueFormatter(logging.Formatter):
    """Human-readable structured logs of the form:

        2026-09-07 12:00:00Z INFO app.ingestion.manager msg="..." key1=val1
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        base = (
            f"{self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z')} "
            f"{record.levelname} {record.name} "
            f"msg=\"{record.getMessage()}\""
        )
        extras = getattr(record, "_extras", None)
        if extras:
            parts = []
            for k, v in extras.items():
                # Redact anything that looks sensitive
                if _is_sensitive_key(k):
                    v = "***"
                parts.append(f"{k}={_stringify(v)}")
            base = f"{base} {' '.join(parts)}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


_SENSITIVE_TOKENS = ("password", "secret", "token", "api_key", "apikey", "authorization", "service_role")


def _is_sensitive_key(key: str) -> bool:
    k = key.lower()
    return any(t in k for t in _SENSITIVE_TOKENS)


def _stringify(v: Any) -> str:
    s = str(v)
    if " " in s or "=" in s:
        return f'"{s}"'
    return s


class _StructuredAdapter(logging.LoggerAdapter):
    """Adapter that lets callers write `logger.info("msg", key=value)`."""

    def process(self, msg: str, kwargs: dict) -> tuple:  # type: ignore[override]
        extras = {k: v for k, v in kwargs.items() if k not in _RESERVED_KWARGS}
        for k in list(extras.keys()):
            kwargs.pop(k, None)
        record_extras = kwargs.setdefault("extra", {})
        record_extras["_extras"] = extras
        return msg, kwargs


_RESERVED_KWARGS = {"exc_info", "stack_info", "stacklevel", "extra"}


def configure_logging() -> None:
    """Configure the root logger. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings = get_settings()

    root = logging.getLogger()
    root.setLevel(settings.app_log_level)

    # Remove any pre-existing handlers (e.g. from uvicorn) to avoid duplicates
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_KeyValueFormatter())
    root.addHandler(handler)

    # Tame overly chatty libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> _StructuredAdapter:
    """Return a structured logger. Usage:

        log = get_logger(__name__)
        log.info("upload_started", dataset_id=ds_id, size=1234)
    """
    configure_logging()
    return _StructuredAdapter(logging.getLogger(name), {})
