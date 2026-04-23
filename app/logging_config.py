"""Structured JSON logging configuration for the Flask microservice."""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    Fields: timestamp, level, logger, message, module, funcName, lineno,
    plus any extras attached via ``extra={...}``.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        # Merge any extra keys the caller passed
        for key in ("request_id", "method", "path", "status", "duration_ms", "remote_addr", "user"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def configure_logging(app_name: str = "flask-microservice", level: str = "INFO") -> None:
    """Replace the root logger's handler with a structured JSON handler.

    Call once at application startup (inside ``create_app``).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any pre-existing handlers (werkzeug, default StreamHandler, etc.)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Quieten overly-chatty libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
