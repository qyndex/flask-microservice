"""Tests for health-check endpoints: liveness, readiness, and metrics."""
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------

class TestLiveness:
    def test_returns_200(self, client):
        resp = client.get("/health/")
        assert resp.status_code == 200

    def test_body_has_status_ok(self, client):
        data = client.get("/health/").get_json()
        assert data["status"] == "ok"

    def test_body_has_uptime_seconds(self, client):
        data = client.get("/health/").get_json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0


# ---------------------------------------------------------------------------
# Readiness — both deps healthy
# ---------------------------------------------------------------------------

class TestReadinessAllHealthy:
    def _mock_redis_ping(self):
        return MagicMock(return_value=True)

    def test_returns_200_when_all_ok(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.return_value = True
            resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_body_status_ok_when_all_ok(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.return_value = True
            data = client.get("/health/ready").get_json()
        assert data["status"] == "ok"

    def test_checks_dict_present(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.return_value = True
            data = client.get("/health/ready").get_json()
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]

    def test_db_check_ok(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.return_value = True
            data = client.get("/health/ready").get_json()
        assert data["checks"]["database"] == "ok"

    def test_redis_check_ok(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.return_value = True
            data = client.get("/health/ready").get_json()
        assert data["checks"]["redis"] == "ok"


# ---------------------------------------------------------------------------
# Readiness — Redis down
# ---------------------------------------------------------------------------

class TestReadinessRedisDegraded:
    def test_returns_503_when_redis_down(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.side_effect = ConnectionError("refused")
            resp = client.get("/health/ready")
        assert resp.status_code == 503

    def test_body_status_degraded_when_redis_down(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.side_effect = ConnectionError("refused")
            data = client.get("/health/ready").get_json()
        assert data["status"] == "degraded"

    def test_redis_check_contains_error_text(self, client):
        with patch("app.health.redis_client") as mock_redis:
            mock_redis.ping.side_effect = ConnectionError("refused")
            data = client.get("/health/ready").get_json()
        assert "error" in data["checks"]["redis"]


# ---------------------------------------------------------------------------
# Readiness — DB down
# ---------------------------------------------------------------------------

class TestReadinessDbDegraded:
    def test_returns_503_when_db_down(self, client):
        with patch("app.health.db") as mock_db, \
             patch("app.health.redis_client") as mock_redis:
            mock_db.session.execute.side_effect = Exception("connection refused")
            mock_redis.ping.return_value = True
            resp = client.get("/health/ready")
        assert resp.status_code == 503

    def test_db_check_contains_error_text(self, client):
        with patch("app.health.db") as mock_db, \
             patch("app.health.redis_client") as mock_redis:
            mock_db.session.execute.side_effect = Exception("connection refused")
            mock_redis.ping.return_value = True
            data = client.get("/health/ready").get_json()
        assert "error" in data["checks"]["database"]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_returns_200(self, client):
        resp = client.get("/health/metrics")
        assert resp.status_code == 200

    def test_content_type_is_prometheus(self, client):
        resp = client.get("/health/metrics")
        assert "text/plain" in resp.content_type
        assert "0.0.4" in resp.content_type

    def test_contains_jobs_total_metric(self, client):
        body = client.get("/health/metrics").data.decode()
        assert "jobs_total" in body

    def test_contains_jobs_pending_metric(self, client):
        body = client.get("/health/metrics").data.decode()
        assert "jobs_pending" in body

    def test_contains_jobs_running_metric(self, client):
        body = client.get("/health/metrics").data.decode()
        assert "jobs_running" in body

    def test_contains_jobs_failed_metric(self, client):
        body = client.get("/health/metrics").data.decode()
        assert "jobs_failed" in body

    def test_metric_values_are_integers(self, client):
        """Each gauge/counter value must be a parsable integer."""
        body = client.get("/health/metrics").data.decode()
        for line in body.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            _name, value = line.rsplit(" ", 1)
            assert int(value) >= 0

    def test_counts_reflect_db_state(self, client, sample_job):
        """jobs_total should be >= 1 once a job is persisted."""
        body = client.get("/health/metrics").data.decode()
        for line in body.splitlines():
            if line.startswith("jobs_total "):
                total = int(line.split(" ")[1])
                assert total >= 1
                return
        raise AssertionError("jobs_total metric line not found")
