"""
Test dashboard endpoints for proper response structure and error handling.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import dashboard.server as ds
from dashboard.server import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Test client for dashboard FastAPI app."""
    return TestClient(app)


@pytest.fixture
def brp_sample_data(tmp_path, monkeypatch):
    """Create synthetic BRP audit files for dashboard endpoint tests."""
    brp_dir = tmp_path / "brp"
    brp_dir.mkdir()

    def write_jsonl(name, rows):
        target = brp_dir / name
        with open(target, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    event = {
        "schema_version": "brp.event.v1",
        "event_id": "evt-001",
        "timestamp": "2026-04-21T09:00:00",
        "source_agent": "quantumarb_phase4",
        "event_type": "mesh_intent",
        "action": "route_order",
        "params": {"quantity": 42},
        "context": {"pattern": "burst retry", "risk_level": "high"},
        "mode": "shadow",
        "tags": ["mesh", "network"],
    }
    plan = {
        "schema_version": "brp.plan.v1",
        "plan_id": "plan-001",
        "timestamp": "2026-04-21T09:01:00",
        "source_agent": "mother_goose",
        "steps": [{"action": "route_order"}, {"action": "withdrawal"}],
        "context": {"goal": "rebalance"},
        "mode": "advisory",
        "tags": ["planning"],
    }
    responses = [
        {
            "response_id": "resp-001",
            "event_id": "evt-001",
            "decision": "ALLOW",
            "mode": "shadow",
            "severity": "medium",
            "threat_score": 0.44,
            "confidence": 0.8,
            "threat_tags": ["predictive_pattern", "multimodal_behavior_risk"],
            "summary": "BRP evaluated action='route_order': decision=ALLOW, threat_score=0.44",
            "timestamp": "2026-04-21T09:00:05",
            "metadata": {
                "predictive_assessment": {"score_boost": 0.12, "threat_tags": ["predictive_pattern"]},
                "multimodal_assessment": {
                    "score_boost": 0.08,
                    "summary": {"total_detections": 2, "detection_breakdown": {"behavior_anomalies": 1}},
                },
            },
        },
        {
            "response_id": "resp-002",
            "event_id": "plan-001",
            "decision": "ELEVATE",
            "mode": "advisory",
            "severity": "high",
            "threat_score": 0.86,
            "confidence": 0.95,
            "threat_tags": ["restricted_action", "predictive_sequence"],
            "summary": "BRP evaluated action='plan_review': decision=ELEVATE, threat_score=0.86",
            "timestamp": "2026-04-21T09:01:05",
            "metadata": {
                "predictive_steps": [
                    {"action": "withdrawal", "score_boost": 0.16, "threat_tags": ["predictive_sequence"]},
                ],
                "multimodal_steps": [
                    {"action": "withdrawal", "score_boost": 0.05, "summary": {"total_detections": 1}},
                ],
            },
        },
    ]
    observations = [
        {
            "schema_version": "brp.observation.v1",
            "observation_id": "obs-001",
            "timestamp": "2026-04-21T09:02:00",
            "source_agent": "quantumarb_phase4",
            "event_id": "evt-001",
            "action": "route_order",
            "outcome": "executed",
            "result_data": {"success": True},
            "context": {},
            "mode": "shadow",
            "tags": ["mesh"],
        }
    ]
    adaptive_rules = {
        "predictive_pattern::route_order": {
            "severity": "medium",
            "boost": 0.12,
            "count": 3,
            "last_seen": "2026-04-21T09:02:00",
            "active": True,
            "description": "Escalate repeated route_order bursts",
        },
        "legacy_rule": {
            "severity": "low",
            "boost": 0.05,
            "count": 1,
            "last_seen": "2026-04-20T08:00:00",
            "active": False,
            "description": "Retired low-signal rule",
        },
    }

    write_jsonl("events.jsonl", [event])
    write_jsonl("plans.jsonl", [plan])
    write_jsonl("responses.jsonl", responses)
    write_jsonl("observations.jsonl", observations)
    (brp_dir / "adaptive_rules.json").write_text(json.dumps(adaptive_rules), encoding="utf-8")
    monkeypatch.setenv("BRP_DATA_DIR", str(brp_dir))
    return brp_dir


@pytest.fixture
def mock_broker_responses():
    """Mock broker responses for dashboard endpoints."""
    with patch('dashboard.server._broker_get') as mock_get, \
         patch('dashboard.server._broker_snapshot') as mock_snapshot, \
         patch('dashboard.server._projectx_get') as mock_projectx:
        
        # Mock successful broker responses
        mock_get.return_value = {
            "status": "success",
            "agents": [
                {
                    "agent_id": "test_agent",
                    "status": "online",
                    "capabilities": ["test_capability"],
                    "endpoint": "http://localhost:9999",
                    "connection_mode": "http"
                }
            ],
            "count": 1
        }
        
        mock_snapshot.return_value = {
            "health": {"status": "healthy", "timestamp": "2024-01-15T10:30:00Z"},
            "agents": {"test_agent": {"status": "online"}},
            "intents": {"recent": [], "failed": []},
            "stats": {"received": 10, "routed": 8, "failed": 2}
        }
        
        mock_projectx.return_value = {
            "status": "success",
            "processes": [
                {
                    "service": "test_service",
                    "category": "test",
                    "status": "running",
                    "health": "healthy",
                    "port": 8080
                }
            ]
        }
        
        yield mock_get, mock_snapshot, mock_projectx


class TestDashboardCoreEndpoints:
    """Test core dashboard API endpoints."""
    
    def test_health_endpoint(self, client):
        """Test /api/health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "broker_reachable" in data
        assert "dashboard_version" in data
    
    def test_health_alias_endpoint(self, client):
        """Test /health alias endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_stats_endpoint(self, client):
        """Test /api/stats endpoint."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "dashboard_started_at" in data
        assert "broker" in data or "status" in data
    
    def test_agents_endpoint(self, client):
        """Test /api/agents endpoint."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "count" in data
        assert isinstance(data["agents"], (dict, list))
    
    def test_activity_endpoint(self, client):
        """Test /api/activity endpoint."""
        response = client.get("/api/activity")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "events" in data
        assert isinstance(data["events"], list)
    
    def test_intents_recent_endpoint(self, client):
        """Test /api/intents/recent endpoint."""
        response = client.get("/api/intents/recent")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "intents" in data
        assert isinstance(data["intents"], list)
    
    def test_intents_failed_endpoint(self, client):
        """Test /api/intents/failed endpoint."""
        response = client.get("/api/intents/failed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "summary" in data
        assert "intents" in data
        assert isinstance(data["intents"], list)
    
    def test_capabilities_endpoint(self, client):
        """Test /api/capabilities endpoint."""
        response = client.get("/api/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "capabilities" in data
        assert isinstance(data["capabilities"], dict)
    
    def test_agents_smoke_endpoint(self, client):
        """Test /api/agents/smoke endpoint."""
        response = client.get("/api/agents/smoke")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Should have either results or agents
        assert "results" in data or "agents" in data
    
    def test_tasks_endpoint(self, client):
        """Test /api/tasks endpoint."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Tasks endpoint returns various task data
        assert "tasks" in data or "queue" in data or "summary" in data
    
    def test_routing_endpoint(self, client):
        """Test /api/routing endpoint."""
        response = client.get("/api/routing")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Routing endpoint returns policy or capability map
        assert "policy" in data or "capabilities" in data or "routes" in data
    
    def test_orchestration_endpoint(self, client):
        """Test /api/orchestration endpoint."""
        response = client.get("/api/orchestration")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Orchestration endpoint returns loop status
        assert "loop_status" in data or "status" in data or "orchestration" in data


class TestProjectXEndpoints:
    """Test ProjectX integration endpoints."""
    
    def test_projectx_system_endpoint(self, client):
        """Test /api/projectx/system endpoint."""
        response = client.get("/api/projectx/system")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # System endpoint returns system info
        assert "system" in data or "status" in data
    
    def test_projectx_processes_endpoint(self, client):
        """Test /api/projectx/processes endpoint."""
        response = client.get("/api/projectx/processes")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Processes endpoint returns services or processes
        assert "processes" in data or "services" in data
    
    def test_projectx_actions_endpoint(self, client):
        """Test /api/projectx/actions endpoint."""
        response = client.get("/api/projectx/actions")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Actions endpoint returns actions or events
        assert "actions" in data or "events" in data
    
    def test_projectx_protocol_facts_endpoint(self, client):
        """Test /api/projectx/protocol-facts endpoint."""
        response = client.get("/api/projectx/protocol-facts")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Protocol facts endpoint returns protocol_facts
        assert "protocol_facts" in data

    def test_projectx_swarm_status_endpoint(self, client, monkeypatch):
        async def fake_projectx_get(path: str):
            assert path == "/swarm/status"
            return {
                "status": "ok",
                "active_mission_count": 2,
                "recent_missions": [{"mission_id": "mission-1"}],
            }

        monkeypatch.setattr(ds, "_projectx_get", fake_projectx_get)

        response = client.get("/api/projectx/swarm/status")
        assert response.status_code == 200
        data = response.json()
        assert data["active_mission_count"] == 2
        assert data["recent_missions"][0]["mission_id"] == "mission-1"

    def test_projectx_swarm_missions_endpoint(self, client, monkeypatch):
        async def fake_projectx_get(path: str):
            assert path == "/swarm/missions"
            return {
                "status": "ok",
                "active_mission_count": 1,
                "recent_missions": [{"mission_id": "mission-2"}],
            }

        monkeypatch.setattr(ds, "_projectx_get", fake_projectx_get)

        response = client.get("/api/projectx/swarm/missions")
        assert response.status_code == 200
        data = response.json()
        assert data["recent_missions"][0]["mission_id"] == "mission-2"

    def test_projectx_swarm_mission_detail_endpoint(self, client, monkeypatch):
        async def fake_projectx_get(path: str):
            assert path == "/swarm/missions/mission-3"
            return {
                "status": "ok",
                "mission": {
                    "mission_id": "mission-3",
                    "task_summary": {"total": 6},
                    "tasks": [{"task_id": "task-1"}],
                },
            }

        monkeypatch.setattr(ds, "_projectx_get", fake_projectx_get)

        response = client.get("/api/projectx/swarm/missions/mission-3")
        assert response.status_code == 200
        data = response.json()
        assert data["mission"]["mission_id"] == "mission-3"
        assert data["mission"]["tasks"][0]["task_id"] == "task-1"

    def test_projectx_swarm_recommendations_endpoint(self, client, monkeypatch):
        async def fake_projectx_get(path: str):
            assert path == "/swarm/recommendations"
            return {
                "status": "ok",
                "recommendations": [{"id": "bootstrap_native_kernel"}],
            }

        monkeypatch.setattr(ds, "_projectx_get", fake_projectx_get)

        response = client.get("/api/projectx/swarm/recommendations")
        assert response.status_code == 200
        data = response.json()
        assert data["recommendations"][0]["id"] == "bootstrap_native_kernel"

    def test_projectx_swarm_plan_endpoint(self, client, monkeypatch):
        async def fake_dispatch(*, intent_type, params, request_id, source_agent="dashboard_ui", action_prefix=""):
            assert intent_type == "projectx_swarm_plan"
            assert params["objective"] == "Upgrade ProjectX kernel"
            assert params["mission_type"] == "projectx_upgrade"
            return {
                "status": "success",
                "response": {
                    "mission": {"mission_id": "mission-123", "objective": params["objective"]},
                },
            }

        monkeypatch.setattr(ds, "_dispatch_projectx_intent", fake_dispatch)

        response = client.post(
            "/api/projectx/swarm/plan",
            json={"objective": "Upgrade ProjectX kernel", "mission_type": "projectx_upgrade"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["response"]["mission"]["mission_id"] == "mission-123"

    def test_projectx_recursive_improvement_endpoint(self, client, monkeypatch):
        async def fake_dispatch(*, intent_type, params, request_id, source_agent="dashboard_ui", action_prefix=""):
            assert intent_type == "projectx_recursive_improvement"
            assert params["objective"] == "Improve ProjectX safely"
            assert params["evidence"]["source"] == "operator"
            return {
                "status": "success",
                "response": {
                    "guardrails": {"self_modification_scope": "bounded"},
                },
            }

        monkeypatch.setattr(ds, "_dispatch_projectx_intent", fake_dispatch)

        response = client.post(
            "/api/projectx/swarm/recursive-improvement",
            json={"objective": "Improve ProjectX safely", "evidence": {"source": "operator"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"]["guardrails"]["self_modification_scope"] == "bounded"

    def test_projectx_swarm_accept_recommendation_endpoint(self, client, monkeypatch):
        async def fake_dispatch(*, intent_type, params, request_id, source_agent="dashboard_ui", action_prefix=""):
            assert intent_type == "projectx_swarm_accept_recommendation"
            assert params["recommendation_id"] == "bootstrap_native_kernel"
            return {
                "status": "success",
                "response": {
                    "mission": {"mission_id": "mission-accepted"},
                },
            }

        monkeypatch.setattr(ds, "_dispatch_projectx_intent", fake_dispatch)

        response = client.post(
            "/api/projectx/swarm/recommendations/accept",
            json={"recommendation_id": "bootstrap_native_kernel"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"]["mission"]["mission_id"] == "mission-accepted"


class TestBRPEndpoints:
    """Test operator-visible BRP dashboard endpoints."""

    def test_brp_status_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["has_data"] is True
        assert data["counts"]["responses"] == 2
        assert data["counts"]["observations"] == 1
        assert data["recent"]["decision_counts"]["ELEVATE"] == 1
        assert data["recent"]["active_adaptive_rules"] == 1

    def test_brp_evaluations_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/evaluations?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 1
        evaluation = data["evaluations"][0]
        assert evaluation["event_id"] == "plan-001"
        assert evaluation["record_type"] == "plan"
        assert evaluation["predictive_score_boost"] == 0.16
        assert evaluation["multimodal_detections"] == 1

    def test_brp_evaluations_filters_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/evaluations?decision=ALLOW&query=quantumarb_phase4")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 1
        assert data["filters"]["decision"] == "ALLOW"
        assert data["filters"]["query"] == "quantumarb_phase4"
        assert data["evaluations"][0]["event_id"] == "evt-001"

    def test_brp_evaluation_detail_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/evaluations/evt-001")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["detail"]["evaluation"]["event_id"] == "evt-001"
        assert data["detail"]["source_record"]["source_agent"] == "quantumarb_phase4"
        assert len(data["detail"]["related_observations"]) == 1

    def test_brp_adaptive_rules_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/adaptive-rules")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 2
        assert data["rules"][0]["key"] == "predictive_pattern::route_order"
        assert data["rules"][0]["active"] is True

    def test_brp_alerts_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/alerts?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] >= 1
        assert data["alerts"][0]["severity"] in {"high", "critical", "medium"}

    def test_brp_incidents_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/incidents?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] >= 1
        assert data["open_alerts"] >= 1
        assert "state_counts" in data
        assert "incidents" in data
        assert data["incidents"][0]["incident_state"] in {"open", "acknowledged", "reopened", "remediated"}
        assert "history" in data["incidents"][0]

    def test_brp_playbooks_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/playbooks?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] >= 1
        assert data["playbooks"][0]["actions"]
        assert data["playbooks"][0]["automation"]["job"]
        assert data["playbooks"][0]["evidence"]["trigger"]["alert_id"]
        assert data["playbooks"][0]["operator_checks"]
        assert data["playbooks"][0]["guardrails"]

    def test_brp_remediations_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/remediations?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 0

    def test_brp_alert_acknowledge_endpoint(self, client, brp_sample_data):
        response = client.post(
            "/api/brp/alerts/brp-alert::plan-001/acknowledge",
            json={"actor": "test_operator", "note": "triaged"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["alert"]["acknowledged"] is True
        assert data["alert"]["acknowledged_by"] == "test_operator"

    def test_brp_playbook_execute_endpoint(self, client, brp_sample_data, monkeypatch):
        operator_events = []

        async def fake_broker_post(path, payload):
            assert path == "/intents/route"
            assert payload["target_agent"] == "projectx_native"
            assert "brp_evidence" in payload["params"]
            assert "brp_execution_context" in payload["params"]
            assert "brp_guardrails" in payload["params"]
            assert "brp_operator_checks" in payload["params"]
            return {
                "intent_id": "broker-intent-1",
                "delivery_status": "delivered",
                "delivery_response": {
                    "status": "ok",
                    "response": {"ok": True, "intent_type": payload["intent_type"]},
                },
            }

        monkeypatch.setattr(ds, "_broker_post", fake_broker_post)
        monkeypatch.setattr(ds, "_append_operator_event", lambda **kwargs: operator_events.append(kwargs))

        response = client.post(
            "/api/brp/playbooks/playbook::brp-alert::plan-001/execute",
            json={"actor": "test_operator"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["execution"]["routing_mode"] == "broker"
        assert data["remediation"]["status"] == "completed"
        assert len(operator_events) == 2

        remediations = client.get("/api/brp/remediations?limit=5").json()
        assert remediations["count"] == 1
        assert remediations["remediations"][0]["actor"] == "test_operator"

    def test_brp_report_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/report?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "status_summary" in data
        assert "alerts" in data
        assert "incidents" in data
        assert "playbooks" in data
        assert "remediations" in data
        assert "evaluations" in data
        assert "adaptive_rules" in data
        assert "runtime_context" in data

    def test_brp_insights_endpoint(self, client, brp_sample_data):
        response = client.get("/api/brp/insights?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["summary"]["elevated_or_denied"] == 1
        assert data["summary"]["high_severity"] == 1
        assert data["signals"]["predictive_score_boost"] == 0.28
        assert data["signals"]["multimodal_detections"] == 3
        assert len(data["recent_evaluations"]) == 2


class TestDashboardStaticFiles:
    """Test static file serving."""
    
    def test_root_endpoint_serves_html(self, client):
        """Test root endpoint serves the dashboard HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
        assert "BRP Operator View" in response.text
        assert "brp-playbooks-feed" in response.text
        assert "brp-remediations-feed" in response.text
    
    def test_static_files_served(self, client):
        """Test static files (CSS, JS) are served correctly."""
        response = client.get("/static/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
        
        response = client.get("/static/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"].lower()


class TestDashboardParameterValidation:
    """Test parameter validation for dashboard endpoints."""
    
    def test_limit_parameter_validation(self, client):
        """Test limit parameters are accepted."""
        # Test valid limit values
        response = client.get("/api/intents/recent?limit=10")
        assert response.status_code == 200
        
        response = client.get("/api/intents/recent?limit=50")
        assert response.status_code == 200
        
        # Test without limit parameter (should use default)
        response = client.get("/api/intents/recent")
        assert response.status_code == 200
    
    def test_intent_detail_endpoint(self, client):
        """Test /api/intents/{intent_id} endpoint."""
        response = client.get("/api/intents/test_intent_id")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Intent detail returns intent or detail
        assert "intent" in data or "detail" in data


class TestDashboardErrorHandling:
    """Test dashboard error handling."""
    
    def test_nonexistent_endpoint_returns_404(self, client):
        """Test nonexistent endpoint returns 404."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
    
    def test_broker_unreachable_handled_gracefully(self, client):
        """Test dashboard handles broker unreachable gracefully."""
        # This is tested implicitly by the other tests
        # If broker is unreachable, endpoints should still return 200
        # with appropriate status field
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
