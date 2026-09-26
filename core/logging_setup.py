"""
Application-wide logging (SRS 16.9): separate rotating log file, never
logs passwords / full documents / tokens, includes a short reference id
that can be shown to the user for unexpected errors.
"""
from __future__ import annotations

import logging
import logging.handlers
import uuid

from core.config import get_log_dir

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    log_dir = get_log_dir()
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    root.addHandler(console)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_error_reference() -> str:
    """Short id shown to the user; full details go to the log under this id."""
    return uuid.uuid4().hex[:8].upper()


def mask(value: str | None, keep: int = 2) -> str:
    """Mask a sensitive value for safe logging, e.g. passwords/passport numbers."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)
