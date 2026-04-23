"""REST API routes for the Flask microservice."""
import json

from flask import Blueprint, abort, jsonify, request

from ..extensions import celery_app, db
from ..models import Job

api_bp = Blueprint("api", __name__)


@api_bp.post("/jobs")
def enqueue_job():
    """Enqueue a new background job."""
    data = request.get_json(force=True) or {}
    task_name = data.get("task_name", "")
    if not task_name:
        abort(400, description="task_name is required")
    payload = data.get("payload", {})

    job = Job(task_name=task_name, payload=json.dumps(payload), status="pending")
    db.session.add(job)
    db.session.flush()

    # Dispatch to Celery
    celery_result = celery_app.send_task(task_name, kwargs=payload)
    job.celery_task_id = celery_result.id
    db.session.commit()

    return jsonify({
        "id": job.id,
        "task_name": job.task_name,
        "status": job.status,
        "celery_task_id": job.celery_task_id,
    }), 202


@api_bp.get("/jobs")
def list_jobs():
    """Return a paginated list of jobs."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    status_filter = request.args.get("status")

    query = db.select(Job).order_by(Job.created_at.desc())
    if status_filter:
        query = query.where(Job.status == status_filter)

    total = db.session.execute(
        db.select(db.func.count()).select_from(query.subquery())
    ).scalar_one()
    jobs = db.session.execute(
        query.offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "results": [
            {
                "id": j.id,
                "task_name": j.task_name,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "duration_seconds": j.duration_seconds,
            }
            for j in jobs
        ],
    })


@api_bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    """Return a single job by ID."""
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404, description=f"Job {job_id!r} not found")
    return jsonify({
        "id": job.id,
        "task_name": job.task_name,
        "status": job.status,
        "payload": json.loads(job.payload) if job.payload else {},
        "result": json.loads(job.result) if job.result else None,
        "error": job.error,
        "celery_task_id": job.celery_task_id,
        "duration_seconds": job.duration_seconds,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    })


@api_bp.delete("/jobs/<job_id>")
def cancel_job(job_id: str):
    """Cancel (revoke) a pending Celery task and mark the job cancelled."""
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404, description=f"Job {job_id!r} not found")
    if job.status not in ("pending", "running"):
        abort(409, description=f"Cannot cancel job with status {job.status!r}")
    if job.celery_task_id:
        celery_app.control.revoke(job.celery_task_id, terminate=True)
    job.status = "failed"
    job.error = "Cancelled by user"
    db.session.commit()
    return "", 204
