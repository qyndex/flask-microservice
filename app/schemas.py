"""Marshmallow schemas for request/response validation.

Each schema validates inbound JSON and serialises outbound model instances.
Used by route handlers for consistent validation and error messages.
"""
from __future__ import annotations

from marshmallow import Schema, fields, validate


# ---------------------------------------------------------------------------
# Job schemas
# ---------------------------------------------------------------------------


class JobCreateSchema(Schema):
    """Validate POST /api/v1/jobs body."""

    task_name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    payload = fields.Dict(load_default={})


class JobResponseSchema(Schema):
    """Serialise a Job model for API responses."""

    id = fields.String()
    task_name = fields.String()
    status = fields.String()
    payload = fields.String()
    result = fields.String(allow_none=True)
    error = fields.String(allow_none=True)
    celery_task_id = fields.String(allow_none=True)
    duration_seconds = fields.Float(allow_none=True)
    created_at = fields.DateTime(format="iso")
    started_at = fields.DateTime(format="iso", allow_none=True)
    completed_at = fields.DateTime(format="iso", allow_none=True)


class JobListResponseSchema(Schema):
    """Serialise paginated job list."""

    total = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()
    results = fields.List(fields.Nested(JobResponseSchema))


# ---------------------------------------------------------------------------
# Event schemas
# ---------------------------------------------------------------------------


class EventCreateSchema(Schema):
    """Validate POST /api/v1/events body."""

    event_type = fields.String(required=True, validate=validate.Length(min=1, max=100))
    source = fields.String(required=True, validate=validate.Length(min=1, max=100))
    severity = fields.String(
        load_default="info",
        validate=validate.OneOf(["info", "warning", "error", "critical"]),
    )
    payload = fields.Dict(load_default={})
    metadata = fields.Dict(load_default={})


class EventResponseSchema(Schema):
    """Serialise an Event model for API responses."""

    id = fields.String()
    event_type = fields.String()
    source = fields.String()
    severity = fields.String()
    payload = fields.String()
    metadata_json = fields.String()
    is_processed = fields.Boolean()
    created_at = fields.DateTime(format="iso")


class EventListResponseSchema(Schema):
    """Serialise paginated event list."""

    total = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()
    results = fields.List(fields.Nested(EventResponseSchema))
