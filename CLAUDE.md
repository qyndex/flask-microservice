# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask Microservice -- Production-ready Flask 3 microservice with API key authentication, Celery task queue, Redis, domain events, Alembic migrations, structured JSON logging, CORS, rate limiting, health checks, and Prometheus metrics.

Built with Flask 3.x, Python 3.13, and SQLAlchemy.

## Commands

```bash
cp .env.example .env                     # Configure environment variables
pip install -r requirements.txt          # Install dependencies
flask --app wsgi:app run --reload        # Start dev server (http://localhost:5000)
python -m pytest                         # Run all tests (126 tests)
python -m pytest tests/test_auth.py      # Auth tests only
python -m pytest tests/test_events.py    # Event route tests only
python seed.py                           # Seed database with sample data
ruff check .                             # Lint
ruff format .                            # Format
mypy .                                   # Type check
```

### Database migrations

```bash
flask --app wsgi:app db upgrade          # Apply migrations
flask --app wsgi:app db migrate -m "description"  # Auto-generate migration
flask --app wsgi:app db downgrade        # Roll back one migration
```

### Celery worker (separate terminal)

```bash
celery -A wsgi:celery_app worker --loglevel=info
```

### Docker

```bash
docker compose up                        # API + Celery worker + Redis + Postgres
docker compose up --build                # Rebuild after code changes
```

## Architecture

```
app/
  __init__.py          # Application factory (create_app) -- wires all extensions
  extensions.py        # Shared instances: db, ma, migrate, redis_client, celery_app, cors, limiter
  models.py            # SQLAlchemy models: Job (async tasks), Event (domain events)
  schemas.py           # Marshmallow schemas for request validation and response serialisation
  auth.py              # API key authentication decorator (X-API-Key / Bearer)
  errors.py            # Centralised error handlers: HTTPException, ValidationError, ServiceError
  middleware.py        # Request ID tracking, structured request/response logging
  logging_config.py    # JSON structured logging formatter
  tasks.py             # Celery task definitions + signal handlers (prerun/postrun/failure)
  health.py            # Blueprint: GET /health/, /health/ready, /health/metrics
  api/
    __init__.py
    routes.py          # Blueprint: /api/v1/jobs (CRUD) + /api/v1/events (CRUD + process)
config.py              # DevelopmentConfig / TestingConfig / ProductionConfig
wsgi.py                # WSGI entry point for gunicorn + celery_app export
seed.py                # Database seed script (5 jobs + 6 events)
migrations/
  env.py               # Alembic/Flask-Migrate environment
  versions/
    001_initial_schema.py  # Jobs + Events tables with indexes
tests/
  conftest.py          # Fixtures: app, db (rollback-per-test), client, auth_headers, sample_job, sample_event
  test_auth.py         # API key auth: valid/invalid/missing key, Bearer token, health public
  test_health.py       # Liveness, readiness, metrics endpoint tests
  test_models.py       # Job + Event model defaults, field persistence, enums
  test_routes.py       # Job REST API: enqueue, list, get, cancel + auth enforcement
  test_events.py       # Event REST API: create, list, get, mark processed + auth enforcement
```

### Authentication

API key authentication via `X-API-Key` header or `Authorization: Bearer <key>`. Keys are loaded from the `API_KEYS` environment variable (comma-separated). When `API_KEYS` is empty (dev mode), all requests are allowed. Health endpoints are always public.

### Data models

| Model | Purpose | Key fields |
|-------|---------|------------|
| `Job` | Async background task record | `task_name`, `status` (pending/running/completed/failed), `payload`, `result`, `celery_task_id` |
| `Event` | Domain event / audit trail | `event_type`, `source`, `severity` (info/warning/error/critical), `payload`, `is_processed` |

### Job lifecycle

`POST /api/v1/jobs` creates a `Job` row (status=`pending`) and dispatches to Celery via `send_task`. Celery signals automatically transition the job through `running` -> `completed` / `failed` and record `started_at`, `completed_at`, and `duration_seconds`.

### Event lifecycle

`POST /api/v1/events` records an immutable domain event. Events can be filtered by `event_type`, `source`, and `severity`. `PATCH /api/v1/events/<id>/process` marks an event as handled by downstream consumers.

### API endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/health/` | No | Liveness probe |
| `GET` | `/health/ready` | No | Readiness probe (DB + Redis) |
| `GET` | `/health/metrics` | No | Prometheus text metrics |
| `POST` | `/api/v1/jobs` | Yes | Enqueue background job |
| `GET` | `/api/v1/jobs` | Yes | List jobs (paginated, filterable) |
| `GET` | `/api/v1/jobs/<id>` | Yes | Get single job |
| `DELETE` | `/api/v1/jobs/<id>` | Yes | Cancel pending/running job |
| `POST` | `/api/v1/events` | Yes | Record domain event |
| `GET` | `/api/v1/events` | Yes | List events (paginated, filterable) |
| `GET` | `/api/v1/events/<id>` | Yes | Get single event |
| `PATCH` | `/api/v1/events/<id>/process` | Yes | Mark event processed |

### Rate limiting

- Default: 200 requests/minute, 50 requests/second per IP
- `POST /api/v1/jobs`: 30/minute
- `POST /api/v1/events`: 60/minute
- Disabled in test config (`RATELIMIT_ENABLED = False`)
- Production: backed by Redis (`RATELIMIT_STORAGE_URI`)

### Error handling

All errors return a consistent JSON envelope:
```json
{"error": {"code": "NOT_FOUND", "message": "...", "status": 404, "details": {}}}
```

Custom exception classes: `ServiceError`, `NotFoundError`, `ConflictError`, `BadRequestError`, `UnauthorizedError` in `app/errors.py`.

### Structured logging

JSON-formatted logs to stdout with fields: `timestamp`, `level`, `logger`, `message`, `request_id`, `method`, `path`, `status`, `duration_ms`. Every response includes an `X-Request-ID` header (propagated from request or auto-generated).

## Configuration

Copy `.env.example` to `.env` and adjust values. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_APP` | `wsgi:app` | Entrypoint for the `flask` CLI |
| `FLASK_CONFIG` | `config.DevelopmentConfig` | Config class to load |
| `SECRET_KEY` | (must set in prod) | Flask session signing key |
| `DATABASE_URL` | `sqlite:///dev.db` (dev) | SQLAlchemy database URI |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `API_KEYS` | (empty = no auth) | Comma-separated valid API keys |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `CELERY_BROKER_URL` | same as `REDIS_URL` | Celery broker |
| `CELERY_RESULT_BACKEND` | same as `REDIS_URL` | Celery result backend |

## Testing

Tests use an in-memory SQLite database and run Celery tasks synchronously (TASK_ALWAYS_EAGER). Rate limiting is disabled. Each test rolls back its DB changes. API_KEYS is set to `test-key-001,test-key-002` for auth testing.

```bash
python -m pytest                         # All tests (126)
python -m pytest tests/test_health.py    # Health endpoint tests only
python -m pytest tests/test_models.py    # Model tests only
python -m pytest tests/test_routes.py    # Job route tests only
python -m pytest tests/test_events.py    # Event route tests only
python -m pytest tests/test_auth.py      # Authentication tests only
python -m pytest -v --tb=short           # Verbose with short tracebacks
```

## Rules

- Use Flask Blueprints for all route organisation -- never register routes directly on `app`
- SQLAlchemy for all database access -- no raw SQL
- Marshmallow schemas for all request validation -- never trust raw `request.get_json()`
- Environment variables for all configuration -- never hardcode secrets or URLs
- API key authentication on all business endpoints -- health endpoints stay public
- Error handlers return consistent `{"error": {...}}` JSON envelope
- Celery tasks must be registered task names; use `celery_app.send_task(name, kwargs=payload)` pattern
- Add new extension instances to `app/extensions.py` and initialise them inside `create_app`
- New Blueprint files go in `app/` and are registered with a `url_prefix` in `create_app`
- All new routes must use the `@require_api_key` decorator (imported from `app.auth`)
- TestingConfig sets `CELERY_TASK_ALWAYS_EAGER = True` and `RATELIMIT_ENABLED = False`
- Migrations go in `migrations/versions/` with sequential numbering
- Structured logging via `logging.getLogger(__name__)` -- never use `print()`
- Custom business errors extend `ServiceError` from `app/errors.py`
