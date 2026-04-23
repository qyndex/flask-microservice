"""WSGI entry point for gunicorn.

Also exports ``celery_app`` so the Celery worker can be started with::

    celery -A wsgi:celery_app worker --loglevel=info
"""
import os

from app import create_app
from app.extensions import celery_app  # noqa: F401 — used by celery CLI

app = create_app(os.environ.get("FLASK_CONFIG", "config.ProductionConfig"))

if __name__ == "__main__":
    app.run()
