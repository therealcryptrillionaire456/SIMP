"""Tests for Sprint 27: failed-intent aggregates and drill-down diagnostics."""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import dashboard.server as ds


FAILED_INTENT = {
    "id": "86b62b9d-7743-4c20-b708-87934c3da708",
    "timestamp": "2026-04-06T18:30:00+00:00",
    "delivered_at": "2026-04-06T18:30:01+00:00",
    "source_agent": "dashboard_ui",
    "target_agent": "kashclaw_gemma",
    "intent_type": "planning",
    "delivery_status": "connection_refused",
    "failure_reason": "Connection refused by target endpoint",
    "correlation_ids": {
        "broker_intent_id": "86b62b9d-7743-4c20-b708-87934c3da708",
        "request_id": "req-123",
        "correlation_id": "req-123",
    },
    "fallback_behavior": {
        "mode": "queued_for_polling",
        "queued_for_polling": True,
        "dlq_eligible": True,
        "fallback_agent": None,
    },
    "route_attempts": [
        {
            "attempt": 1,
            "timestamp": "2026-04-06T18:30:00+00:00",
            "transport": "http",
            "endpoint": "http://127.0.0.1:8780",
            "status": "connection_refused",
            "http_status": None,
            "error": "Connection refused by target endpoint",
        }
    ],
    "lifecycle": [
        {"event": "intent_received", "timestamp": "2026-04-06T18:30:00+00:00", "status": "pending"},
        {"event": "fallback_queued_for_polling", "timestamp": "2026-04-06T18:30:01+00:00", "status": "connection_refused"},
        {"event": "delivery_finalized", "timestamp": "2026-04-06T18:30:01+00:00", "status": "connection_refused"},
    ],
}


def test_normalize_intent_detail_produces_bounded_failure_state():
    detail = ds._normalize_intent_detail({"intent_id": "abc"}, lookup_status="not_found")
    assert detail["failure_reason"] == "unknown"
    assert detail["fallback_behavior"]["mode"] == "unknown"
    assert detail["correlation_ids"]["broker_intent_id"] == "abc"


def test_failed_intents_endpoint_returns_summary_and_rows(monkeypatch):
    async def fake_failed(limit=50):
        return {
            "summary": {
                "count": 1,
                "latest_failure_at": FAILED_INTENT["delivered_at"],
                "by_status": {"connection_refused": 1},
                "by_target_agent": {"kashclaw_gemma": 1},
            },
            "intents": [FAILED_INTENT],
        }

    monkeypatch.setattr(ds, "_broker_failed_intents", fake_failed)

    with TestClient(ds.app) as client:
        response = client.get("/api/intents/failed?limit=10")

    body = response.json()
    assert response.status_code == 200
    assert body["summary"]["by_status"]["connection_refused"] == 1
    assert body["intents"][0]["failure_reason"] == "Connection refused by target endpoint"
    assert body["intents"][0]["route_attempts"][0]["status"] == "connection_refused"


def test_intent_detail_endpoint_returns_diagnostic_view(monkeypatch):
    async def fake_lookup(intent_id):
        return (FAILED_INTENT, "success")

    monkeypatch.setattr(ds, "_broker_intent_detail", fake_lookup)

    with TestClient(ds.app) as client:
        response = client.get(f"/api/intents/{FAILED_INTENT['id']}")

    body = response.json()
    assert response.status_code == 200
    assert body["detail"]["correlation_ids"]["request_id"] == "req-123"
    assert body["detail"]["fallback_behavior"]["queued_for_polling"] is True
    assert body["detail"]["lifecycle"][-1]["status"] == "connection_refused"


def test_failed_intents_ui_elements_exist():
    root = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static")
    with open(os.path.join(root, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    with open(os.path.join(root, "app.js"), encoding="utf-8") as fh:
        js = fh.read()

    assert "failed-intents-section" in html
    assert "intent-drawer" in html
    assert "renderFailedIntents" in js
    assert "openIntentDrawer" in js
