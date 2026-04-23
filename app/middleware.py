"""Request/response middleware for the Flask microservice.

Adds:
  - Request ID tracking (``X-Request-ID`` header propagation / generation)
  - Request/response structured logging (method, path, status, duration)
"""
from __future__ import annotations

import logging
import time
import uuid

from flask import Flask, g, request

logger = logging.getLogger(__name__)


def register_middleware(app: Flask) -> None:
    """Attach before/after-request hooks to *app*."""

    @app.before_request
    def _inject_request_id():
        """Propagate or generate a unique request ID."""
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        g.request_start = time.monotonic()

    @app.after_request
    def _log_and_tag_response(response):
        """Log the request and set response headers."""
        duration_ms = round((time.monotonic() - getattr(g, "request_start", time.monotonic())) * 1000, 2)
        request_id = getattr(g, "request_id", "-")
        response.headers["X-Request-ID"] = request_id

        # Skip noisy health-check logging
        if not request.path.startswith("/health"):
            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "remote_addr": request.remote_addr,
                },
            )
        return response
