"""Centralised error handlers for the Flask microservice.

Registers JSON error responses for common HTTP status codes and
application-specific exceptions.  Imported and called from
``create_app`` in ``app/__init__.py``.
"""
from __future__ import annotations

import logging
import traceback

from flask import Flask, jsonify
from marshmallow import ValidationError as MarshmallowValidationError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Base class for business-logic errors.

    Subclasses set ``status_code`` and ``code`` (a machine-readable tag)
    so the error handler can return a uniform JSON body.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ServiceError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(ServiceError):
    status_code = 409
    code = "CONFLICT"


class BadRequestError(ServiceError):
    status_code = 400
    code = "BAD_REQUEST"


class UnauthorizedError(ServiceError):
    status_code = 401
    code = "UNAUTHORIZED"


def register_error_handlers(app: Flask) -> None:
    """Attach JSON error handlers to *app*.

    Handles:
      - Werkzeug ``HTTPException`` (404, 405, 413, etc.)
      - Marshmallow ``ValidationError`` (request body validation)
      - ``ServiceError`` and subclasses (business-logic errors)
      - Unhandled ``Exception`` (500 with traceback in logs)
    """

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return jsonify({
            "error": {
                "code": exc.name.upper().replace(" ", "_"),
                "message": exc.description or exc.name,
                "status": exc.code,
            }
        }), exc.code

    @app.errorhandler(MarshmallowValidationError)
    def handle_validation_error(exc: MarshmallowValidationError):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "status": 422,
                "details": exc.messages,
            }
        }), 422

    @app.errorhandler(ServiceError)
    def handle_service_error(exc: ServiceError):
        if exc.status_code >= 500:
            logger.error("Service error: %s", exc.message, exc_info=True)
        return jsonify({
            "error": {
                "code": exc.code,
                "message": exc.message,
                "status": exc.status_code,
                "details": exc.details,
            }
        }), exc.status_code

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "status": 500,
            }
        }), 500
