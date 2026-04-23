"""WSGI entry point for gunicorn."""
import os

from app import create_app

app = create_app(os.environ.get("FLASK_CONFIG", "config.ProductionConfig"))

if __name__ == "__main__":
    app.run()
