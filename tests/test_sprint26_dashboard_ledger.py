"""Tests for Sprint 26: dashboard ledger-backed activity and delivery stats."""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import dashboard.server as ds


SAMPLE_DASHBOARD = {
    "generated_at": "2026-04-06T17:10:00+00:00",
    "broker": {
        "status": "running",
        "agents_online": 4,
        "total_intents": 14,
        "routed": 9,
        "failed": 3,
        "agent_queues": {
            "projectx_native": 2,
            "kashclaw_gemma": 1,
        },
    },
    "recent_intents": [
        {
            "intent_id": "86b62b9d-7743-4c20-b708-87934c3da708",
            "timestamp": "2026-04-06T17:09:58+00:00",
            "source_agent": "dashboard_ui",
            "target_agent": "kashclaw_gemma",
            "intent_type": "planning",
            "delivery_status": "delivered",
        },
        {
            "intent_id": "b7e4d144-6b79-4377-b10f-7a8d12fe1358",
            "timestamp": "2026-04-06T17:09:35+00:00",
            "source_agent": "projectx_native",
            "target_agent": "kashclaw_gemma",
            "intent_type": "native_agent_task_audit",
            "delivery_status": "connection_refused",
        },
        {
            "intent_id": "c9ffcc12-0736-4f29-95d4-4d7b8f495d7c",
            "timestamp": "2026-04-06T17:08:20+00:00",
            "source_agent": "projectx_native",
            "target_agent": "projectx_native",
            "intent_type": "native_agent_security_audit",
            "delivery_status": "queued_no_endpoint",
        },
    ],
}


class TestDashboardLedgerHelpers:
    def test_stats_payload_includes_real_delivery_counts(self):
        payload = ds._dashboard_stats_payload(SAMPLE_DASHBOARD)
        stats = payload["broker"]["stats"]

        assert stats["delivery_counts"]["delivered"] == 9
        assert stats["delivery_counts"]["failed"] == 3
        assert stats["delivery_counts"]["queued"] == 3
        assert stats["delivery_counts"]["connection_refused"] == 1
        assert stats["delivery_counts"]["queued_no_endpoint"] == 1
        assert stats["recent_deliveries"][0]["intent_id"].startswith("86b62b9d")

    def test_recent_activity_is_returned_oldest_first_for_ui_sorting(self):
        events = ds._recent_intent_events(SAMPLE_DASHBOARD)
        assert [event["intent_id"] for event in events] == [
            "c9ffcc12-0736-4f29-95d4-4d7b8f495d7c",
            "b7e4d144-6b79-4377-b10f-7a8d12fe1358",
            "86b62b9d-7743-4c20-b708-87934c3da708",
        ]
        assert events[-1]["result"] == "dashboard_ui -> kashclaw_gemma (86b62b9d-774)"


class TestDashboardLedgerApis:
    def test_recent_intents_endpoint_returns_broker_tail(self, monkeypatch):
        async def fake_snapshot(*, force_refresh=False):
            return {"dashboard": SAMPLE_DASHBOARD, "health": {}}

        monkeypatch.setattr(ds, "_broker_snapshot", fake_snapshot)

        with TestClient(ds.app) as client:
            response = client.get("/api/intents/recent?limit=2")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["count"] == 2
        assert body["intents"][0]["intent_id"] == "86b62b9d-7743-4c20-b708-87934c3da708"

    def test_intent_detail_endpoint_redacts_sensitive_fields(self, monkeypatch):
        async def fake_lookup(intent_id):
            return ({
                "id": intent_id,
                "source_agent": "dashboard_ui",
                "target_agent": "projectx_native",
                "params": {"token": "secret-token", "task": "scan"},
            }, "success")

        monkeypatch.setattr(ds, "_broker_intent_detail", fake_lookup)

        with TestClient(ds.app) as client:
            response = client.get("/api/intents/86b62b9d-7743-4c20-b708-87934c3da708")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["intent"]["id"] == "86b62b9d-7743-4c20-b708-87934c3da708"
        assert body["intent"]["params"]["task"] == "scan"
        assert "token" not in body["intent"]["params"]
