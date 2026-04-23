"""Flask microservice application factory."""
from __future__ import annotations

import os

from flask import Flask

from .api.routes import api_bp
from .errors import register_error_handlers
from .extensions import celery_app, cors, db, limiter, ma, migrate, redis_client
from .health import health_bp
from .logging_config import configure_logging
from .middleware import register_middleware
from .tasks import configure_celery


def create_app(config_object: str = "config.DevelopmentConfig") -> Flask:
    """Create and configure the Flask microservice.

    Registers Blueprints for health checks, the REST API, and wires up
    Celery with the application context.  Adds structured logging, CORS,
    rate limiting, request middleware, and centralised error handling.

    Args:
        config_object: Dotted-path to a config class.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Structured logging (call before extensions so library loggers are tamed)
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    configure_logging(level=log_level)

    # Initialise extensions
    db.init_app(app)
    ma.init_app(app)
    migrate.init_app(app, db)
    redis_client.init_app(app)
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": os.environ.get("CORS_ORIGINS", "*").split(","),
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
        }
    })
    limiter.init_app(app)

    # Celery
    configure_celery(app, celery_app)

    # Middleware (request ID, structured request logging)
    register_middleware(app)

    # Centralised error handlers
    register_error_handlers(app)

    # Register blueprints
    app.register_blueprint(health_bp, url_prefix="/health")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    return app
