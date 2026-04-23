"""SQLAlchemy models for the Flask microservice."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Job model — async background tasks
# ---------------------------------------------------------------------------


class JobStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(db.Model):
    """Asynchronous background job record."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending", "running", "completed", "failed",
            name="job_status_enum",
        ),
        default="pending",
        nullable=False,
    )
    payload: Mapped[str] = mapped_column(Text, default="{}")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id!r} task={self.task_name!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# Event model — domain events / webhook payloads
# ---------------------------------------------------------------------------


class EventSeverity(PyEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Event(db.Model):
    """Domain event for audit trails, webhooks, and inter-service communication.

    Events are immutable once created.  Use ``is_processed`` to track
    whether downstream consumers have handled the event.
    """

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_source_type", "source", "event_type"),
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_processed", "is_processed"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(
        Enum("info", "warning", "error", "critical", name="event_severity_enum"),
        default="info",
        nullable=False,
    )
    payload: Mapped[str] = mapped_column(Text, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    is_processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id!r} type={self.event_type!r} source={self.source!r}>"
