"""Shared pytest fixtures for the Flask microservice test suite."""
import json
import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Create a Flask application configured for testing.

    Uses an in-memory SQLite database so tests are fast and isolated, with
    Celery tasks running eagerly (synchronously) inside the test process.
    """
    flask_app = create_app("config.TestingConfig")
    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "CELERY_TASK_ALWAYS_EAGER": True,
            "CELERY_BROKER_URL": "memory://",
            "CELERY_RESULT_BACKEND": "cache+memory://",
            # Disable Flask-Redis actual connection during unit tests
            "REDIS_URL": "redis://localhost:6379/0",
        }
    )
    return flask_app


@pytest.fixture(scope="session")
def _db_tables(app):
    """Create all tables once for the session, then drop them."""
    with app.app_context():
        _db.create_all()
        yield
        _db.drop_all()


@pytest.fixture()
def db(app, _db_tables):
    """Yield a database session wrapped in a transaction that rolls back after
    each test, keeping tests isolated without recreating the schema."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        _db.session.bind = connection  # type: ignore[attr-defined]
        yield _db
        _db.session.remove()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(app, db):
    """Flask test client with an active database context."""
    return app.test_client()


@pytest.fixture()
def sample_job(db):
    """Persist a single Job row and return it for use in tests."""
    from app.models import Job

    job = Job(task_name="myapp.tasks.sample_task", status="pending", payload=json.dumps({"x": 1}))
    db.session.add(job)
    db.session.commit()
    return job
