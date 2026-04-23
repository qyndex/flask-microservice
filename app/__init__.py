"""Flask microservice application factory."""
from flask import Flask, jsonify

from .extensions import celery_app, db, ma, migrate, redis_client
from .api.routes import api_bp
from .health import health_bp
from .tasks import configure_celery


def create_app(config_object: str = "config.DevelopmentConfig") -> Flask:
    """Create and configure the Flask microservice.

    Registers Blueprints for health checks, the REST API, and wires up
    Celery with the application context.

    Args:
        config_object: Dotted-path to a config class.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Initialise extensions
    db.init_app(app)
    ma.init_app(app)
    migrate.init_app(app, db)
    redis_client.init_app(app)

    # Celery
    configure_celery(app, celery_app)

    # Register blueprints
    app.register_blueprint(health_bp, url_prefix="/health")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Generic error handlers
    @app.errorhandler(404)
    def not_found(err):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def server_error(err):
        return jsonify({"error": "Internal server error"}), 500

    return app
