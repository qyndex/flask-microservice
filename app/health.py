"""Health check Blueprint for the Flask microservice."""
import time

from flask import Blueprint, jsonify

from .extensions import db, redis_client

health_bp = Blueprint("health", __name__)

_start_time = time.time()


@health_bp.get("/")
def liveness():
    """Basic liveness probe — always returns 200 if the app is running."""
    return jsonify({"status": "ok", "uptime_seconds": round(time.time() - _start_time, 1)})


@health_bp.get("/ready")
def readiness():
    """Readiness probe — checks database and Redis connectivity."""
    checks: dict[str, str] = {}
    overall_ok = True

    # Database check
    try:
        db.session.execute(db.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        overall_ok = False

    # Redis check
    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        overall_ok = False

    status_code = 200 if overall_ok else 503
    return jsonify({"status": "ok" if overall_ok else "degraded", "checks": checks}), status_code


@health_bp.get("/metrics")
def metrics():
    """Basic Prometheus-style text metrics endpoint."""
    from .extensions import db
    from .models import Job

    try:
        total = db.session.execute(db.select(db.func.count(Job.id))).scalar_one()
        pending = db.session.execute(
            db.select(db.func.count(Job.id)).where(Job.status == "pending")
        ).scalar_one()
        running = db.session.execute(
            db.select(db.func.count(Job.id)).where(Job.status == "running")
        ).scalar_one()
        failed = db.session.execute(
            db.select(db.func.count(Job.id)).where(Job.status == "failed")
        ).scalar_one()
    except Exception:
        total = pending = running = failed = 0

    lines = [
        "# HELP jobs_total Total number of jobs",
        "# TYPE jobs_total counter",
        f"jobs_total {total}",
        "# HELP jobs_pending Pending jobs",
        "# TYPE jobs_pending gauge",
        f"jobs_pending {pending}",
        "# HELP jobs_running Running jobs",
        "# TYPE jobs_running gauge",
        f"jobs_running {running}",
        "# HELP jobs_failed Failed jobs",
        "# TYPE jobs_failed counter",
        f"jobs_failed {failed}",
    ]
    return "\n".join(lines), 200, {"Content-Type": "text/plain; version=0.0.4"}
