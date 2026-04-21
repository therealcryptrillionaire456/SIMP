"""Tests for Sprint 29: derived dashboard fallbacks for bullbear-missing routes."""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import dashboard.server as ds


def test_tasks_endpoint_derives_rows_from_failed_intents(monkeypatch):
    async def fake_broker_get(path):
        return None

    async def fake_failed(limit=25, failed_only=False):
        return [
            {
                "id": "intent-1",
                "timestamp": "2026-04-06T20:00:00+00:00",
                "source_agent": "dashboard_ui",
                "target_agent": "projectx_native",
                "intent_type": "native_agent_task_audit",
                "delivery_status": "connection_refused",
                "failure_reason": "Connection refused by target endpoint",
            }
        ]

    async def fake_snapshot(*, force_refresh=False):
        return {"dashboard": None, "health": None}

    monkeypatch.setattr(ds, "_broker_get", fake_broker_get)
    monkeypatch.setattr(ds, "_broker_list_intents", fake_failed)
    monkeypatch.setattr(ds, "_broker_snapshot", fake_snapshot)

    with TestClient(ds.app) as client:
        response = client.get("/api/tasks")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["source"] == "derived_intents"
    assert body["tasks"][0]["status"] == "failed"
    assert body["failure_stats"]["Connection refused by target endpoint"] == 1


def test_routing_endpoint_derives_capability_map_from_agents(monkeypatch):
    async def fake_broker_get(path):
        return None

    async def fake_agents():
        return [
            {
                "agent_id": "gemma4_local",
                "capabilities": ["planning", "docs"],
                "stale": False,
            },
            {
                "agent_id": "claude_cowork",
                "capabilities": ["planning", "code_task"],
                "stale": True,
            },
        ]

    monkeypatch.setattr(ds, "_broker_get", fake_broker_get)
    monkeypatch.setattr(ds, "_broker_registry_agents", fake_agents)

    with TestClient(ds.app) as client:
        response = client.get("/api/routing")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["source"] == "derived_capabilities"
    assert body["policy"]["task_routing"]["planning"] == ["claude_cowork", "gemma4_local"]
    assert body["pool_status"]["stale_count"] == 1


def test_memory_conversations_endpoint_derives_rows_from_operator_events(monkeypatch):
    async def fake_broker_get(path):
        return None

    monkeypatch.setattr(ds, "_broker_get", fake_broker_get)
    monkeypatch.setattr(
        ds,
        "_tail_operator_events",
        lambda limit=60: [
            {
                "request_id": "req-1",
                "summary": "What is SIMP?",
                "source_agent": "dashboard_ui",
                "target_agent": "projectx_native",
                "timestamp": "2026-04-06T20:01:00+00:00",
            }
        ],
    )

    with TestClient(ds.app) as client:
        response = client.get("/api/memory/conversations")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["source"] == "derived_operator_events"
    assert body["conversations"][0]["id"] == "req-1"


def test_dashboard_health_alias_uses_api_health(monkeypatch):
    async def fake_snapshot(*, force_refresh=False):
        return {
            "dashboard": {"broker": {"status": "running", "agents_online": 3}},
            "health": {"agents_online": 3, "paused": False},
        }

    monkeypatch.setattr(ds, "_broker_snapshot", fake_snapshot)

    with TestClient(ds.app) as client:
        response = client.get("/health")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "healthy"
    assert body["broker_reachable"] is True


def test_memory_conversations_endpoint_preserves_explicit_broker_capability_gap(monkeypatch):
    async def fake_broker_get(path):
        assert path == "/memory/conversations"
        return {
            "status": "not_supported",
            "supported": False,
            "reason": "Bullbear does not persist conversation transcripts.",
            "conversations": [],
            "count": 0,
        }

    monkeypatch.setattr(ds, "_broker_get", fake_broker_get)

    with TestClient(ds.app) as client:
        response = client.get("/api/memory/conversations")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "not_supported"
    assert body["supported"] is False
    assert "conversation transcripts" in body["reason"]
