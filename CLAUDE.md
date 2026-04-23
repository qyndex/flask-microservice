# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask Microservice — Production-ready Flask 3 microservice with Celery task queue, Redis, health checks, Prometheus metrics endpoint, and Docker Compose setup.

Built with Flask 3.x, Python 3.13, and SQLAlchemy.

## Commands

```bash
cp .env.example .env                     # Configure environment variables
pip install -r requirements.txt          # Install dependencies
flask --app wsgi:app run --reload        # Start dev server (http://localhost:5000)
python -m pytest                         # Run tests
ruff check .                             # Lint
ruff format .                            # Format
mypy .                                   # Type check
```

### Celery worker (separate terminal)

```bash
celery -A wsgi.app.extensions.celery_app worker --loglevel=info
```

### Docker

```bash
docker compose up                        # Starts API + Celery worker + Redis + Postgres
```

## Architecture

```
app/
  __init__.py          # Application factory (create_app)
  extensions.py        # Shared extension instances (db, ma, migrate, redis_client, celery_app)
  models.py            # SQLAlchemy models (Job, JobStatus enum)
  tasks.py             # Celery task definitions + signal handlers (prerun/postrun/failure)
  health.py            # Blueprint: GET /health/, /health/ready, /health/metrics
  api/
    __init__.py
    routes.py          # Blueprint: POST|GET /api/v1/jobs, GET /api/v1/jobs/<id>, DELETE /api/v1/jobs/<id>
config.py              # DevelopmentConfig / TestingConfig / ProductionConfig
wsgi.py                # WSGI entry point for gunicorn
tests/
  conftest.py          # Fixtures: app, db (rollback-per-test), client, sample_job
  test_health.py       # Liveness, readiness, metrics endpoint tests
  test_models.py       # Job model defaults, field persistence, enum values
  test_routes.py       # REST API: enqueue, list, get, cancel
```

### Job lifecycle

`POST /api/v1/jobs` creates a `Job` row (status=`pending`) and dispatches to Celery via `send_task`. Celery signals automatically transition the job through `running` → `completed` / `failed` and record `started_at`, `completed_at`, and `duration_seconds`.

### Health endpoints

| Path | Purpose |
|------|---------|
| `GET /health/` | Liveness — always 200 if the process is alive |
| `GET /health/ready` | Readiness — checks DB + Redis; 503 if either is down |
| `GET /health/metrics` | Prometheus text format — job counts by status |

## Configuration

Copy `.env.example` to `.env` and adjust values. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_APP` | `wsgi:app` | Entrypoint for the `flask` CLI |
| `FLASK_CONFIG` | `config.DevelopmentConfig` | Config class to load |
| `SECRET_KEY` | (must set in prod) | Flask session signing key |
| `DATABASE_URL` | `sqlite:///dev.db` (dev) | SQLAlchemy database URI |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CELERY_BROKER_URL` | same as `REDIS_URL` | Celery broker |
| `CELERY_RESULT_BACKEND` | same as `REDIS_URL` | Celery result backend |

## Testing

Tests use an in-memory SQLite database and run Celery tasks synchronously (TASK_ALWAYS_EAGER). Each test rolls back its DB changes — no teardown required.

```bash
python -m pytest                         # All tests
python -m pytest tests/test_health.py   # Health endpoint tests only
python -m pytest tests/test_models.py   # Model tests only
python -m pytest tests/test_routes.py   # Route tests only
python -m pytest -v --tb=short          # Verbose with short tracebacks
```

## Rules

- Use Flask Blueprints for all route organisation — never register routes directly on `app`
- SQLAlchemy for all database access — no raw SQL
- Environment variables for all configuration — never hardcode secrets or URLs
- Error handlers for 404, 500, and validation errors are registered in `create_app`
- Celery tasks must be registered task names; use `celery_app.send_task(name, kwargs=payload)` pattern
- Add new extension instances to `app/extensions.py` and initialise them inside `create_app`
- New Blueprint files go in `app/` and are registered with a `url_prefix` in `create_app`
- TestingConfig sets `CELERY_TASK_ALWAYS_EAGER = True` — do not add `broker_url` mocks in test code unless testing broker failure scenarios
