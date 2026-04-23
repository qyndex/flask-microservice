"""Celery task definitions and app-context wiring."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun
from flask import Flask


def configure_celery(app: Flask, celery: Celery) -> None:
    """Bind Celery to the Flask application context.

    After calling this, every Celery task runs inside an active Flask app
    context so SQLAlchemy sessions and extensions work normally.
    """
    celery.config_from_object(
        {
            "broker_url": app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
            "result_backend": app.config.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "timezone": "UTC",
            "enable_utc": True,
        }
    )

    class ContextTask(celery.Task):  # type: ignore[misc]
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask


@task_prerun.connect
def on_task_prerun(task_id, task, **kwargs):
    from .extensions import db
    from .models import Job
    job = db.session.execute(
        db.select(Job).where(Job.celery_task_id == task_id)
    ).scalar_one_or_none()
    if job:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()


@task_postrun.connect
def on_task_postrun(task_id, task, retval, state, **kwargs):
    from .extensions import db
    from .models import Job
    job = db.session.execute(
        db.select(Job).where(Job.celery_task_id == task_id)
    ).scalar_one_or_none()
    if job:
        now = datetime.now(timezone.utc)
        job.completed_at = now
        if job.started_at:
            job.duration_seconds = (now - job.started_at).total_seconds()
        job.status = "completed" if state == "SUCCESS" else "failed"
        if isinstance(retval, (dict, list)):
            job.result = json.dumps(retval)
        db.session.commit()


@task_failure.connect
def on_task_failure(task_id, exception, **kwargs):
    from .extensions import db
    from .models import Job
    job = db.session.execute(
        db.select(Job).where(Job.celery_task_id == task_id)
    ).scalar_one_or_none()
    if job:
        job.status = "failed"
        job.error = str(exception)
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()
