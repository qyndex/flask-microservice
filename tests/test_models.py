"""Tests for SQLAlchemy models: Job and Event creation, defaults, and constraints."""
import json
from datetime import datetime, timezone

from app.models import Event, EventSeverity, Job, JobStatus


# ---------------------------------------------------------------------------
# Job model
# ---------------------------------------------------------------------------

class TestJobDefaults:
    def test_id_is_generated_on_persist(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert job.id is not None
        assert len(job.id) == 36  # UUID format

    def test_status_defaults_to_pending(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert job.status == "pending"

    def test_created_at_is_set(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert isinstance(job.created_at, datetime)

    def test_payload_defaults_to_empty_json(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert job.payload == "{}"

    def test_result_is_none_by_default(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert job.result is None

    def test_error_is_none_by_default(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert job.error is None

    def test_celery_task_id_is_none_by_default(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert job.celery_task_id is None

    def test_duration_seconds_is_none_by_default(self, db):
        job = Job(task_name="mytask")
        db.session.add(job)
        db.session.commit()
        assert job.duration_seconds is None


class TestJobFields:
    def test_task_name_persisted(self, db):
        job = Job(task_name="myapp.tasks.process")
        db.session.add(job)
        db.session.commit()
        fetched = db.session.get(Job, job.id)
        assert fetched.task_name == "myapp.tasks.process"

    def test_payload_stored_as_json_string(self, db):
        payload = {"key": "value", "count": 42}
        job = Job(task_name="t", payload=json.dumps(payload))
        db.session.add(job)
        db.session.commit()
        fetched = db.session.get(Job, job.id)
        assert json.loads(fetched.payload) == payload

    def test_celery_task_id_stored(self, db):
        job = Job(task_name="t", celery_task_id="abc-123")
        db.session.add(job)
        db.session.commit()
        fetched = db.session.get(Job, job.id)
        assert fetched.celery_task_id == "abc-123"

    def test_status_update_to_running(self, db):
        job = Job(task_name="t")
        db.session.add(job)
        db.session.commit()
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()
        fetched = db.session.get(Job, job.id)
        assert fetched.status == "running"
        assert fetched.started_at is not None

    def test_status_update_to_completed(self, db):
        job = Job(task_name="t")
        db.session.add(job)
        db.session.commit()
        job.status = "completed"
        job.result = json.dumps({"output": "done"})
        job.completed_at = datetime.now(timezone.utc)
        job.duration_seconds = 1.23
        db.session.commit()
        fetched = db.session.get(Job, job.id)
        assert fetched.status == "completed"
        assert fetched.duration_seconds == 1.23

    def test_status_update_to_failed_with_error(self, db):
        job = Job(task_name="t")
        db.session.add(job)
        db.session.commit()
        job.status = "failed"
        job.error = "ZeroDivisionError: division by zero"
        db.session.commit()
        fetched = db.session.get(Job, job.id)
        assert fetched.status == "failed"
        assert "ZeroDivisionError" in fetched.error


class TestJobRepr:
    def test_repr_contains_id_task_status(self, db):
        job = Job(task_name="myapp.tasks.echo")
        db.session.add(job)
        db.session.commit()
        r = repr(job)
        assert "myapp.tasks.echo" in r
        assert "pending" in r


class TestJobStatusEnum:
    def test_all_values_defined(self):
        values = {m.value for m in JobStatus}
        assert values == {"pending", "running", "completed", "failed"}


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------

class TestEventDefaults:
    def test_id_is_generated_on_persist(self, db):
        event = Event(event_type="test.created", source="unit-test")
        db.session.add(event)
        db.session.commit()
        assert event.id is not None
        assert len(event.id) == 36

    def test_severity_defaults_to_info(self, db):
        event = Event(event_type="test.created", source="unit-test")
        db.session.add(event)
        db.session.commit()
        assert event.severity == "info"

    def test_is_processed_defaults_to_false(self, db):
        event = Event(event_type="test.created", source="unit-test")
        db.session.add(event)
        db.session.commit()
        assert event.is_processed is False

    def test_created_at_is_set(self, db):
        event = Event(event_type="test.created", source="unit-test")
        db.session.add(event)
        db.session.commit()
        assert isinstance(event.created_at, datetime)

    def test_payload_defaults_to_empty_json(self, db):
        event = Event(event_type="test.created", source="unit-test")
        db.session.add(event)
        db.session.commit()
        assert event.payload == "{}"

    def test_metadata_defaults_to_empty_json(self, db):
        event = Event(event_type="test.created", source="unit-test")
        db.session.add(event)
        db.session.commit()
        assert event.metadata_json == "{}"


class TestEventFields:
    def test_event_type_persisted(self, db):
        event = Event(event_type="order.created", source="shop")
        db.session.add(event)
        db.session.commit()
        fetched = db.session.get(Event, event.id)
        assert fetched.event_type == "order.created"

    def test_source_persisted(self, db):
        event = Event(event_type="order.created", source="shop-service")
        db.session.add(event)
        db.session.commit()
        fetched = db.session.get(Event, event.id)
        assert fetched.source == "shop-service"

    def test_severity_set_to_error(self, db):
        event = Event(event_type="payment.failed", source="billing", severity="error")
        db.session.add(event)
        db.session.commit()
        fetched = db.session.get(Event, event.id)
        assert fetched.severity == "error"

    def test_payload_stored_as_json_string(self, db):
        payload = {"order_id": "ord-42", "amount": 99.99}
        event = Event(
            event_type="order.created", source="shop",
            payload=json.dumps(payload),
        )
        db.session.add(event)
        db.session.commit()
        fetched = db.session.get(Event, event.id)
        assert json.loads(fetched.payload) == payload

    def test_mark_as_processed(self, db):
        event = Event(event_type="test.created", source="unit-test")
        db.session.add(event)
        db.session.commit()
        event.is_processed = True
        db.session.commit()
        fetched = db.session.get(Event, event.id)
        assert fetched.is_processed is True


class TestEventRepr:
    def test_repr_contains_type_and_source(self, db):
        event = Event(event_type="deploy.completed", source="ci")
        db.session.add(event)
        db.session.commit()
        r = repr(event)
        assert "deploy.completed" in r
        assert "ci" in r


class TestEventSeverityEnum:
    def test_all_values_defined(self):
        values = {m.value for m in EventSeverity}
        assert values == {"info", "warning", "error", "critical"}
