"""
SIMP A2A Events — Sprint S3 (Sprint 33) tests.
"""

import json
import os
import pytest

from simp.compat.event_stream import build_a2a_event, build_a2a_events_list


class TestBuildA2AEvent:
    def test_completed_record(self):
        rec = {"intent_id": "i1", "status": "completed", "intent_type": "ping", "timestamp": "2026-01-01T00:00:00Z"}
        ev = build_a2a_event(rec)
        assert ev["taskId"] == "i1"
        assert ev["state"] == "completed"
        assert ev["terminal"] is True
        assert ev["eventKind"] == "completed"

    def test_failed_record(self):
        rec = {"intent_id": "i2", "status": "failed", "error": "oops", "timestamp": "2026-01-01T00:00:00Z"}
        ev = build_a2a_event(rec)
        assert ev["state"] == "failed"
        assert ev["eventKind"] == "error"

    def test_in_progress_record(self):
        rec = {"intent_id": "i3", "status": "executing", "timestamp": "2026-01-01T00:00:00Z"}
        ev = build_a2a_event(rec)
        assert ev["state"] == "working"
        assert ev["eventKind"] == "status_change"

    def test_redacts_sensitive_fields(self):
        rec = {"intent_id": "i4", "status": "pending", "api_key": "secret_val"}
        ev = build_a2a_event(rec)
        # api_key should not appear in x-simp
        x = ev.get("x-simp", {})
        assert "secret_val" not in str(x)

    def test_truncates_long_error(self):
        rec = {"intent_id": "i5", "status": "failed", "error": "E" * 500}
        ev = build_a2a_event(rec)
        assert len(ev["error"]) < 250


class TestBuildA2AEventsList:
    def test_caps_at_limit(self):
        records = [{"intent_id": f"i{i}", "status": "pending", "timestamp": f"2026-01-{i+1:02d}T00:00:00Z"} for i in range(20)]
        result = build_a2a_events_list(records, limit=5)
        assert result["count"] == 5

    def test_sort_descending(self):
        records = [
            {"intent_id": "i1", "status": "pending", "timestamp": "2026-01-01T00:00:00Z"},
            {"intent_id": "i2", "status": "pending", "timestamp": "2026-01-02T00:00:00Z"},
        ]
        result = build_a2a_events_list(records)
        assert result["events"][0]["taskId"] == "i2"

    def test_skip_no_intent_id(self):
        records = [
            {"status": "pending", "timestamp": "2026-01-01T00:00:00Z"},
            {"intent_id": "i1", "status": "pending", "timestamp": "2026-01-01T00:00:00Z"},
        ]
        result = build_a2a_events_list(records)
        assert result["count"] == 1

    def test_limit_max_100(self):
        records = [{"intent_id": f"i{i}", "status": "pending", "timestamp": f"2026-01-01T00:00:00Z"} for i in range(200)]
        result = build_a2a_events_list(records, limit=200)
        assert result["count"] <= 100


class TestEventRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_get_events_returns_json(self, client):
        resp = client.get("/a2a/events")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "events" in data

    def test_get_events_limit(self, client):
        resp = client.get("/a2a/events?limit=5")
        assert resp.status_code == 200

    def test_get_events_intent_filter_404(self, client):
        resp = client.get("/a2a/events/nonexistent_id")
        assert resp.status_code == 404
