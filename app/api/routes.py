"""REST API routes for the Flask microservice.

All business endpoints require API key authentication.
Health endpoints (registered separately) remain public.
"""
from __future__ import annotations

import json
import logging

from flask import Blueprint, abort, jsonify, request
from marshmallow import ValidationError

from ..auth import require_api_key
from ..extensions import celery_app, db, limiter
from ..models import Event, Job
from ..schemas import EventCreateSchema, JobCreateSchema

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)

# Schema instances (reused across requests)
_job_create_schema = JobCreateSchema()
_event_create_schema = EventCreateSchema()


# ---------------------------------------------------------------------------
# Job endpoints
# ---------------------------------------------------------------------------


@api_bp.post("/jobs")
@require_api_key
@limiter.limit("30 per minute")
def enqueue_job():
    """Enqueue a new background job.

    Validates the request body, creates a ``Job`` row, and dispatches
    to Celery.  Returns 202 Accepted with the new job's ID.
    """
    data = request.get_json(force=True) or {}
    try:
        validated = _job_create_schema.load(data)
    except ValidationError as exc:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "status": 422,
                "details": exc.messages,
            }
        }), 422

    task_name = validated["task_name"]
    payload = validated["payload"]

    job = Job(task_name=task_name, payload=json.dumps(payload), status="pending")
    db.session.add(job)
    db.session.flush()

    # Dispatch to Celery
    celery_result = celery_app.send_task(task_name, kwargs=payload)
    job.celery_task_id = celery_result.id
    db.session.commit()

    logger.info("Job enqueued: %s (task=%s)", job.id, task_name)

    return jsonify({
        "id": job.id,
        "task_name": job.task_name,
        "status": job.status,
        "celery_task_id": job.celery_task_id,
    }), 202


@api_bp.get("/jobs")
@require_api_key
def list_jobs():
    """Return a paginated list of jobs."""
    page = max(int(request.args.get("page", 1)), 1)
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
@require_api_key
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
@require_api_key
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

    logger.info("Job cancelled: %s", job_id)
    return "", 204


# ---------------------------------------------------------------------------
# Event endpoints
# ---------------------------------------------------------------------------


@api_bp.post("/events")
@require_api_key
@limiter.limit("60 per minute")
def create_event():
    """Record a new domain event.

    Validates the request body and persists an ``Event`` row.
    Returns 201 Created with the event details.
    """
    data = request.get_json(force=True) or {}
    try:
        validated = _event_create_schema.load(data)
    except ValidationError as exc:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "status": 422,
                "details": exc.messages,
            }
        }), 422

    event = Event(
        event_type=validated["event_type"],
        source=validated["source"],
        severity=validated.get("severity", "info"),
        payload=json.dumps(validated["payload"]),
        metadata_json=json.dumps(validated.get("metadata", {})),
    )
    db.session.add(event)
    db.session.commit()

    logger.info("Event created: %s (type=%s, source=%s)", event.id, event.event_type, event.source)

    return jsonify({
        "id": event.id,
        "event_type": event.event_type,
        "source": event.source,
        "severity": event.severity,
        "is_processed": event.is_processed,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }), 201


@api_bp.get("/events")
@require_api_key
def list_events():
    """Return a paginated list of events with optional filters."""
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(int(request.args.get("per_page", 20)), 100)
    event_type = request.args.get("event_type")
    source = request.args.get("source")
    severity = request.args.get("severity")

    query = db.select(Event).order_by(Event.created_at.desc())
    if event_type:
        query = query.where(Event.event_type == event_type)
    if source:
        query = query.where(Event.source == source)
    if severity:
        query = query.where(Event.severity == severity)

    total = db.session.execute(
        db.select(db.func.count()).select_from(query.subquery())
    ).scalar_one()
    events = db.session.execute(
        query.offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "results": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "source": e.source,
                "severity": e.severity,
                "is_processed": e.is_processed,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    })


@api_bp.get("/events/<event_id>")
@require_api_key
def get_event(event_id: str):
    """Return a single event by ID."""
    event = db.session.get(Event, event_id)
    if event is None:
        abort(404, description=f"Event {event_id!r} not found")
    return jsonify({
        "id": event.id,
        "event_type": event.event_type,
        "source": event.source,
        "severity": event.severity,
        "payload": json.loads(event.payload) if event.payload else {},
        "metadata": json.loads(event.metadata_json) if event.metadata_json else {},
        "is_processed": event.is_processed,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    })


@api_bp.patch("/events/<event_id>/process")
@require_api_key
def mark_event_processed(event_id: str):
    """Mark an event as processed.

    Idempotent — calling on an already-processed event returns 200.
    """
    event = db.session.get(Event, event_id)
    if event is None:
        abort(404, description=f"Event {event_id!r} not found")
    event.is_processed = True
    db.session.commit()

    logger.info("Event marked processed: %s", event_id)
    return jsonify({"id": event.id, "is_processed": True}), 200
