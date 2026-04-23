"""Tests for API key authentication.

Covers X-API-Key header, Authorization: Bearer, missing key, and invalid key
scenarios.  Health endpoints must remain public.
"""
import json


class TestApiKeyViaHeader:
    """Authentication using the X-API-Key header."""

    def test_valid_key_allows_access(self, client, auth_headers):
        resp = client.get("/api/v1/jobs", headers=auth_headers)
        assert resp.status_code == 200

    def test_second_valid_key_also_works(self, client):
        resp = client.get("/api/v1/jobs", headers={"X-API-Key": "test-key-002"})
        assert resp.status_code == 200


class TestApiKeyViaBearer:
    """Authentication using Authorization: Bearer."""

    def test_bearer_token_allows_access(self, client):
        resp = client.get(
            "/api/v1/jobs",
            headers={"Authorization": "Bearer test-key-001"},
        )
        assert resp.status_code == 200


class TestMissingApiKey:
    """Requests without any API key."""

    def test_missing_key_returns_401(self, client):
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 401

    def test_401_body_has_error_structure(self, client):
        data = client.get("/api/v1/jobs").get_json()
        assert "error" in data

    def test_post_jobs_without_key_returns_401(self, client):
        resp = client.post(
            "/api/v1/jobs",
            data=json.dumps({"task_name": "t"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


class TestInvalidApiKey:
    """Requests with a wrong API key."""

    def test_invalid_key_returns_403(self, client):
        resp = client.get("/api/v1/jobs", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403

    def test_invalid_bearer_returns_403(self, client):
        resp = client.get(
            "/api/v1/jobs",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 403


class TestHealthEndpointsPublic:
    """Health endpoints must never require authentication."""

    def test_liveness_no_key(self, client):
        resp = client.get("/health/")
        assert resp.status_code == 200

    def test_readiness_no_key(self, client):
        from unittest.mock import patch

        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.return_value = True
            resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_metrics_no_key(self, client):
        resp = client.get("/health/metrics")
        assert resp.status_code == 200
