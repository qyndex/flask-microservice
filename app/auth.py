"""API key authentication for the Flask microservice.

Business endpoints require a valid API key passed via the
``X-API-Key`` header or ``Authorization: Bearer <key>`` header.
Health endpoints are always public.

API keys are loaded from the ``API_KEYS`` environment variable (comma-separated).
Example: ``API_KEYS=key-abc123,key-xyz789``
"""
from __future__ import annotations

import functools
import hashlib
import hmac
import logging
import os

from flask import abort, g, request

logger = logging.getLogger(__name__)


def _load_api_keys() -> set[str]:
    """Read valid API keys from ``API_KEYS`` env var (comma-separated)."""
    raw = os.environ.get("API_KEYS", "")
    if not raw:
        return set()
    return {k.strip() for k in raw.split(",") if k.strip()}


def _constant_time_compare(a: str, b: str) -> bool:
    """Timing-safe string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


def _extract_key_from_request() -> str | None:
    """Extract an API key from the request headers.

    Checks (in order):
        1. ``X-API-Key`` header
        2. ``Authorization: Bearer <key>`` header
    """
    # Check X-API-Key header first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key

    # Fall back to Authorization: Bearer
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


def require_api_key(fn):
    """Decorator: reject requests without a valid API key.

    Sets ``g.api_key_hash`` to a SHA-256 digest of the matched key
    (useful for audit logging without storing the raw key).
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        valid_keys = _load_api_keys()

        # If no keys are configured, allow all (dev mode)
        if not valid_keys:
            g.api_key_hash = "dev-no-keys-configured"
            return fn(*args, **kwargs)

        provided = _extract_key_from_request()
        if not provided:
            logger.warning("Request missing API key", extra={"path": request.path, "method": request.method})
            abort(401, description="Missing API key. Provide X-API-Key header or Authorization: Bearer <key>.")

        # Constant-time comparison against each valid key
        matched = any(_constant_time_compare(provided, key) for key in valid_keys)
        if not matched:
            logger.warning("Invalid API key attempted", extra={"path": request.path, "method": request.method})
            abort(403, description="Invalid API key.")

        g.api_key_hash = hashlib.sha256(provided.encode()).hexdigest()[:16]
        return fn(*args, **kwargs)

    return wrapper
