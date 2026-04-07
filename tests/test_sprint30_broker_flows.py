"""Tests for Sprint 30: broker-routed ProjectX actions and linked flow surfaces."""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import dashboard.server as ds


def test_agents_smoke_endpoint_returns_broker_payload(monkeypatch):
    async def fake_broker_get(path):
        assert path == "/agents/smoke"
        return {
            "status": "success",
            "results": [
                {"agent_id": "projectx_native", "reachable": True, "health_url": "http://127.0.0.1:8771/health", "error": None}
            ],
            "count": 1,
        }

    monkeypatch.setattr(ds, "_broker_get", fake_broker_get)

    with TestClient(ds.app) as client:
        response = client.get("/api/agents/smoke")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["count"] == 1
    assert body["results"][0]["agent_id"] == "projectx_native"


def test_flows_endpoint_derives_linked_flow_when_broker_route_missing(monkeypatch):
    async def fake_broker_get(path):
        assert path == "/intents/flows?limit=50"
        return None

    async def fake_list(limit=50, failed_only=False):
        return [
            {
                "id": "intent-plan-1",
                "timestamp": "2026-04-07T00:00:00+00:00",
                "source_agent": "dashboard_ui",
                "target_agent": "kashclaw_gemma",
                "intent_type": "planning",
                "delivery_status": "delivered",
                "correlation_ids": {
                    "broker_intent_id": "intent-plan-1",
                    "plan_id": "plan-123",
                    "source_intent_id": None,
                    "correlation_id": "plan-123",
                },
            },
            {
                "id": "intent-exec-1",
                "timestamp": "2026-04-07T00:00:10+00:00",
                "source_agent": "dashboard_ui",
                "target_agent": "projectx_native",
                "intent_type": "native_agent_repo_scan",
                "delivery_status": "delivered",
                "correlation_ids": {
                    "broker_intent_id": "intent-exec-1",
                    "plan_id": "plan-123",
                    "source_intent_id": "intent-plan-1",
                    "correlation_id": "plan-123",
                },
            },
        ]

    monkeypatch.setattr(ds, "_broker_get", fake_broker_get)
    monkeypatch.setattr(ds, "_broker_list_intents", fake_list)

    with TestClient(ds.app) as client:
        response = client.get("/api/flows")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["count"] == 1
    assert body["flows"][0]["flow_id"] == "plan:plan-123"
    assert body["flows"][0]["planner_intent"]["intent_id"] == "intent-plan-1"


def test_projectx_job_prefers_broker_routing(monkeypatch):
    events = []

    async def fake_broker_post(path, payload):
        assert path == "/intents/route"
        assert payload["target_agent"] == "projectx_native"
        assert payload["params"]["source_intent_id"] == "intent-root-1"
        return {
            "intent_id": "broker-intent-1",
            "delivery_status": "delivered",
            "delivery_response": {
                "status": "ok",
                "response": {"ok": True, "intent_type": "native_agent_health_check"},
            },
        }

    async def fail_projectx_post(path, payload):
        raise AssertionError("direct ProjectX fallback should not run when broker routing succeeds")

    monkeypatch.setattr(ds, "_broker_post", fake_broker_post)
    monkeypatch.setattr(ds, "_projectx_post", fail_projectx_post)
    monkeypatch.setattr(ds, "_append_operator_event", lambda **kwargs: events.append(kwargs))

    with TestClient(ds.app) as client:
        response = client.post(
            "/api/projectx/chat",
            json={"job": "native_agent_health_check", "source_intent_id": "intent-root-1"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["routing_mode"] == "broker"
    assert body["broker_intent_id"] == "broker-intent-1"
    assert body["delivery_status"] == "delivered"
    assert len(events) == 2


def test_projectx_query_falls_back_to_direct_guard_when_broker_unavailable(monkeypatch):
    events = []

    async def fake_broker_post(path, payload):
        return None

    async def fake_projectx_post(path, payload):
        assert path == "/intents/handle"
        assert payload["intent_type"] == "projectx_query"
        return {"status": "ok", "response": {"ok": True, "answer": "fallback answer"}}

    monkeypatch.setattr(ds, "_broker_post", fake_broker_post)
    monkeypatch.setattr(ds, "_projectx_post", fake_projectx_post)
    monkeypatch.setattr(ds, "_append_operator_event", lambda **kwargs: events.append(kwargs))

    with TestClient(ds.app) as client:
        response = client.post("/api/projectx/chat", json={"message": "what is simp"})

    body = response.json()
    assert response.status_code == 200
    assert body["routing_mode"] == "direct"
    assert body["broker_intent_id"] is None
    assert body["response"]["response"]["answer"] == "fallback answer"
    assert len(events) == 2
