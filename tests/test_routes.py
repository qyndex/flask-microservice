"""Tests for /api/v1 REST routes: jobs and events.

All business endpoints require authentication via X-API-Key header.
"""
import json
import uuid
from unittest.mock import MagicMock, patch


def _unique_task_id() -> str:
    """Return a unique Celery task ID to avoid UNIQUE constraint collisions."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# POST /api/v1/jobs -- enqueue
# ---------------------------------------------------------------------------

class TestEnqueueJob:
    def _post(self, client, body, headers=None):
        return client.post(
            "/api/v1/jobs",
            data=json.dumps(body),
            content_type="application/json",
            headers=headers or {},
        )

    def test_returns_202_on_success(self, client, auth_headers):
        with patch("app.api.routes.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id=_unique_task_id())
            resp = self._post(client, {"task_name": "myapp.tasks.echo", "payload": {}}, auth_headers)
        assert resp.status_code == 202

    def test_response_contains_job_id(self, client, auth_headers):
        with patch("app.api.routes.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id=_unique_task_id())
            data = self._post(client, {"task_name": "myapp.tasks.echo"}, auth_headers).get_json()
        assert "id" in data
        assert len(data["id"]) == 36  # UUID

    def test_response_contains_status_pending(self, client, auth_headers):
        with patch("app.api.routes.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id=_unique_task_id())
            data = self._post(client, {"task_name": "myapp.tasks.echo"}, auth_headers).get_json()
        assert data["status"] == "pending"

    def test_response_contains_celery_task_id(self, client, auth_headers):
        tid = _unique_task_id()
        with patch("app.api.routes.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id=tid)
            data = self._post(client, {"task_name": "myapp.tasks.echo"}, auth_headers).get_json()
        assert data["celery_task_id"] == tid

    def test_celery_send_task_called_with_task_name(self, client, auth_headers):
        with patch("app.api.routes.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id=_unique_task_id())
            self._post(client, {"task_name": "myapp.tasks.process", "payload": {"k": "v"}}, auth_headers)
        mock_celery.send_task.assert_called_once_with("myapp.tasks.process", kwargs={"k": "v"})

    def test_returns_422_when_task_name_missing(self, client, auth_headers):
        resp = self._post(client, {"payload": {}}, auth_headers)
        assert resp.status_code == 422

    def test_returns_422_when_task_name_empty_string(self, client, auth_headers):
        resp = self._post(client, {"task_name": ""}, auth_headers)
        assert resp.status_code == 422

    def test_accepts_empty_payload(self, client, auth_headers):
        with patch("app.api.routes.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id=_unique_task_id())
            resp = self._post(client, {"task_name": "myapp.tasks.noop"}, auth_headers)
        assert resp.status_code == 202

    def test_job_is_persisted_in_db(self, client, db, auth_headers):
        from app.models import Job

        with patch("app.api.routes.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id=_unique_task_id())
            data = self._post(client, {"task_name": "myapp.tasks.store"}, auth_headers).get_json()

        job = db.session.get(Job, data["id"])
        assert job is not None
        assert job.task_name == "myapp.tasks.store"

    def test_returns_401_without_api_key(self, client):
        resp = self._post(client, {"task_name": "myapp.tasks.echo"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/jobs -- list
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_returns_200(self, client, auth_headers):
        resp = client.get("/api/v1/jobs", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_has_results_key(self, client, auth_headers):
        data = client.get("/api/v1/jobs", headers=auth_headers).get_json()
        assert "results" in data

    def test_response_has_pagination_fields(self, client, auth_headers):
        data = client.get("/api/v1/jobs", headers=auth_headers).get_json()
        for key in ("total", "page", "per_page"):
            assert key in data, f"Missing key: {key}"

    def test_default_page_is_1(self, client, auth_headers):
        data = client.get("/api/v1/jobs", headers=auth_headers).get_json()
        assert data["page"] == 1

    def test_default_per_page_is_20(self, client, auth_headers):
        data = client.get("/api/v1/jobs", headers=auth_headers).get_json()
        assert data["per_page"] == 20

    def test_results_contains_expected_job(self, client, sample_job, auth_headers):
        data = client.get("/api/v1/jobs", headers=auth_headers).get_json()
        ids = [j["id"] for j in data["results"]]
        assert sample_job.id in ids

    def test_result_item_has_required_fields(self, client, sample_job, auth_headers):
        data = client.get("/api/v1/jobs", headers=auth_headers).get_json()
        item = next(j for j in data["results"] if j["id"] == sample_job.id)
        for field in ("id", "task_name", "status", "created_at"):
            assert field in item, f"Missing field: {field}"

    def test_status_filter_returns_only_matching(self, client, sample_job, auth_headers):
        data = client.get("/api/v1/jobs?status=pending", headers=auth_headers).get_json()
        for item in data["results"]:
            assert item["status"] == "pending"

    def test_status_filter_excludes_non_matching(self, client, sample_job, auth_headers):
        data = client.get("/api/v1/jobs?status=completed", headers=auth_headers).get_json()
        ids = [j["id"] for j in data["results"]]
        assert sample_job.id not in ids

    def test_per_page_is_capped_at_100(self, client, auth_headers):
        data = client.get("/api/v1/jobs?per_page=9999", headers=auth_headers).get_json()
        assert data["per_page"] <= 100

    def test_total_is_integer(self, client, auth_headers):
        data = client.get("/api/v1/jobs", headers=auth_headers).get_json()
        assert isinstance(data["total"], int)

    def test_returns_401_without_api_key(self, client):
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/<job_id> -- single job
# ---------------------------------------------------------------------------

class TestGetJob:
    def test_returns_200_for_existing_job(self, client, sample_job, auth_headers):
        resp = client.get(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_returns_404_for_unknown_id(self, client, auth_headers):
        resp = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000", headers=auth_headers)
        assert resp.status_code == 404

    def test_response_contains_all_fields(self, client, sample_job, auth_headers):
        data = client.get(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers).get_json()
        for field in (
            "id", "task_name", "status", "payload",
            "result", "error", "celery_task_id",
            "duration_seconds", "created_at", "started_at", "completed_at",
        ):
            assert field in data, f"Missing field: {field}"

    def test_id_matches_requested(self, client, sample_job, auth_headers):
        data = client.get(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers).get_json()
        assert data["id"] == sample_job.id

    def test_task_name_matches(self, client, sample_job, auth_headers):
        data = client.get(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers).get_json()
        assert data["task_name"] == sample_job.task_name

    def test_payload_is_decoded_dict(self, client, sample_job, auth_headers):
        data = client.get(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers).get_json()
        assert isinstance(data["payload"], dict)

    def test_status_is_pending(self, client, sample_job, auth_headers):
        data = client.get(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers).get_json()
        assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# DELETE /api/v1/jobs/<job_id> -- cancel
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_returns_204_for_pending_job(self, client, sample_job, auth_headers):
        with patch("app.api.routes.celery_app"):
            resp = client.delete(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_response_body_is_empty(self, client, sample_job, auth_headers):
        with patch("app.api.routes.celery_app"):
            resp = client.delete(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers)
        assert resp.data == b""

    def test_returns_404_for_unknown_id(self, client, auth_headers):
        resp = client.delete("/api/v1/jobs/00000000-0000-0000-0000-000000000000", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_409_for_completed_job(self, client, db, auth_headers):
        from app.models import Job

        job = Job(task_name="t", status="completed")
        db.session.add(job)
        db.session.commit()
        resp = client.delete(f"/api/v1/jobs/{job.id}", headers=auth_headers)
        assert resp.status_code == 409

    def test_job_status_set_to_failed_after_cancel(self, client, sample_job, db, auth_headers):
        from app.models import Job

        with patch("app.api.routes.celery_app"):
            client.delete(f"/api/v1/jobs/{sample_job.id}", headers=auth_headers)

        fetched = db.session.get(Job, sample_job.id)
        assert fetched.status == "failed"

    def test_celery_revoke_called_when_celery_task_id_set(self, client, db, auth_headers):
        from app.models import Job

        job = Job(task_name="t", status="pending", celery_task_id="task-xyz")
        db.session.add(job)
        db.session.commit()

        with patch("app.api.routes.celery_app") as mock_celery:
            client.delete(f"/api/v1/jobs/{job.id}", headers=auth_headers)
        mock_celery.control.revoke.assert_called_once_with("task-xyz", terminate=True)

    def test_returns_401_without_api_key(self, client, sample_job):
        resp = client.delete(f"/api/v1/jobs/{sample_job.id}")
        assert resp.status_code == 401
