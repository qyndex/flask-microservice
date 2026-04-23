"""Tests for /api/v1/events REST routes: create, list, get, mark processed."""
import json


# ---------------------------------------------------------------------------
# POST /api/v1/events -- create
# ---------------------------------------------------------------------------

class TestCreateEvent:
    def _post(self, client, body, headers=None):
        return client.post(
            "/api/v1/events",
            data=json.dumps(body),
            content_type="application/json",
            headers=headers or {},
        )

    def test_returns_201_on_success(self, client, auth_headers):
        resp = self._post(client, {
            "event_type": "order.created",
            "source": "shop-service",
        }, auth_headers)
        assert resp.status_code == 201

    def test_response_contains_event_id(self, client, auth_headers):
        data = self._post(client, {
            "event_type": "order.created",
            "source": "shop-service",
        }, auth_headers).get_json()
        assert "id" in data
        assert len(data["id"]) == 36

    def test_response_contains_event_type(self, client, auth_headers):
        data = self._post(client, {
            "event_type": "order.created",
            "source": "shop-service",
        }, auth_headers).get_json()
        assert data["event_type"] == "order.created"

    def test_severity_defaults_to_info(self, client, auth_headers):
        data = self._post(client, {
            "event_type": "deploy.started",
            "source": "ci",
        }, auth_headers).get_json()
        assert data["severity"] == "info"

    def test_custom_severity(self, client, auth_headers):
        data = self._post(client, {
            "event_type": "payment.failed",
            "source": "billing",
            "severity": "error",
        }, auth_headers).get_json()
        assert data["severity"] == "error"

    def test_is_processed_defaults_to_false(self, client, auth_headers):
        data = self._post(client, {
            "event_type": "test.event",
            "source": "test",
        }, auth_headers).get_json()
        assert data["is_processed"] is False

    def test_returns_422_when_event_type_missing(self, client, auth_headers):
        resp = self._post(client, {"source": "test"}, auth_headers)
        assert resp.status_code == 422

    def test_returns_422_when_source_missing(self, client, auth_headers):
        resp = self._post(client, {"event_type": "test.event"}, auth_headers)
        assert resp.status_code == 422

    def test_returns_422_for_invalid_severity(self, client, auth_headers):
        resp = self._post(client, {
            "event_type": "test.event",
            "source": "test",
            "severity": "catastrophic",
        }, auth_headers)
        assert resp.status_code == 422

    def test_event_is_persisted_in_db(self, client, db, auth_headers):
        from app.models import Event

        data = self._post(client, {
            "event_type": "order.shipped",
            "source": "warehouse",
            "payload": {"order_id": "ord-99"},
        }, auth_headers).get_json()

        event = db.session.get(Event, data["id"])
        assert event is not None
        assert event.event_type == "order.shipped"
        assert json.loads(event.payload)["order_id"] == "ord-99"

    def test_returns_401_without_api_key(self, client):
        resp = self._post(client, {
            "event_type": "test.event",
            "source": "test",
        })
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/events -- list
# ---------------------------------------------------------------------------

class TestListEvents:
    def test_returns_200(self, client, auth_headers):
        resp = client.get("/api/v1/events", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_has_results_key(self, client, auth_headers):
        data = client.get("/api/v1/events", headers=auth_headers).get_json()
        assert "results" in data

    def test_response_has_pagination_fields(self, client, auth_headers):
        data = client.get("/api/v1/events", headers=auth_headers).get_json()
        for key in ("total", "page", "per_page"):
            assert key in data, f"Missing key: {key}"

    def test_results_contains_expected_event(self, client, sample_event, auth_headers):
        data = client.get("/api/v1/events", headers=auth_headers).get_json()
        ids = [e["id"] for e in data["results"]]
        assert sample_event.id in ids

    def test_filter_by_event_type(self, client, sample_event, auth_headers):
        data = client.get(
            f"/api/v1/events?event_type={sample_event.event_type}",
            headers=auth_headers,
        ).get_json()
        for item in data["results"]:
            assert item["event_type"] == sample_event.event_type

    def test_filter_by_source(self, client, sample_event, auth_headers):
        data = client.get(
            f"/api/v1/events?source={sample_event.source}",
            headers=auth_headers,
        ).get_json()
        for item in data["results"]:
            assert item["source"] == sample_event.source

    def test_filter_by_severity(self, client, sample_event, auth_headers):
        data = client.get(
            "/api/v1/events?severity=info",
            headers=auth_headers,
        ).get_json()
        for item in data["results"]:
            assert item["severity"] == "info"

    def test_per_page_is_capped_at_100(self, client, auth_headers):
        data = client.get("/api/v1/events?per_page=9999", headers=auth_headers).get_json()
        assert data["per_page"] <= 100


# ---------------------------------------------------------------------------
# GET /api/v1/events/<event_id> -- single event
# ---------------------------------------------------------------------------

class TestGetEvent:
    def test_returns_200_for_existing_event(self, client, sample_event, auth_headers):
        resp = client.get(f"/api/v1/events/{sample_event.id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_returns_404_for_unknown_id(self, client, auth_headers):
        resp = client.get(
            "/api/v1/events/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_response_contains_all_fields(self, client, sample_event, auth_headers):
        data = client.get(f"/api/v1/events/{sample_event.id}", headers=auth_headers).get_json()
        for field in (
            "id", "event_type", "source", "severity",
            "payload", "metadata", "is_processed", "created_at",
        ):
            assert field in data, f"Missing field: {field}"

    def test_payload_is_decoded_dict(self, client, sample_event, auth_headers):
        data = client.get(f"/api/v1/events/{sample_event.id}", headers=auth_headers).get_json()
        assert isinstance(data["payload"], dict)


# ---------------------------------------------------------------------------
# PATCH /api/v1/events/<event_id>/process -- mark processed
# ---------------------------------------------------------------------------

class TestMarkEventProcessed:
    def test_returns_200(self, client, sample_event, auth_headers):
        resp = client.patch(
            f"/api/v1/events/{sample_event.id}/process",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_is_processed_set_to_true(self, client, sample_event, auth_headers):
        data = client.patch(
            f"/api/v1/events/{sample_event.id}/process",
            headers=auth_headers,
        ).get_json()
        assert data["is_processed"] is True

    def test_idempotent(self, client, sample_event, auth_headers):
        """Calling process twice should still return 200."""
        client.patch(f"/api/v1/events/{sample_event.id}/process", headers=auth_headers)
        resp = client.patch(f"/api/v1/events/{sample_event.id}/process", headers=auth_headers)
        assert resp.status_code == 200

    def test_returns_404_for_unknown_event(self, client, auth_headers):
        resp = client.patch(
            "/api/v1/events/00000000-0000-0000-0000-000000000000/process",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_returns_401_without_api_key(self, client, sample_event):
        resp = client.patch(f"/api/v1/events/{sample_event.id}/process")
        assert resp.status_code == 401
