"""Structured logging configuration.

Two output formats are supported:

* ``text`` (default) - human-friendly, single-line records, good for local dev.
* ``json`` - one JSON object per record, suitable for log aggregators.

Both formats include a request-id field when available (set by the
:class:`~websearch_api.api.middleware.RequestIDMiddleware`).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, ClassVar


class JSONFormatter(logging.Formatter):
    """Render log records as compact JSON objects."""

    _RESERVED: ClassVar[set[str]] = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Surface anything attached via ``logger.info(..., extra={...})``.
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            payload[key] = value

        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable single-line format."""

    DEFAULT_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.DEFAULT_FMT, datefmt="%Y-%m-%d %H:%M:%S")


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Configure root logging exactly once.

    Idempotent: calling it twice replaces the existing handlers (useful when
    the FastAPI app is reloaded by ``uvicorn --reload``).
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JSONFormatter() if fmt == "json" else TextFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Tame noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(level.upper())
    logging.getLogger("playwright").setLevel("WARNING")
    logging.getLogger("asyncio").setLevel("WARNING")
