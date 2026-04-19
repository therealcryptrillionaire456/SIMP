"""
Tests for Sprint 65 — End-to-End Smoke Automation

15 test flows using the Flask test client covering agent lifecycle,
file-based routing, auto-routing, response recording, A2A, orchestration,
routing policy, stats accuracy, heartbeat, and more.
"""

import os
import unittest

os.environ.setdefault("SIMP_REQUIRE_API_KEY", "false")

from simp.server.broker import BrokerState
from simp.server.http_server import SimpHttpServer


def _make_client():
    """Create Flask test client with broker running."""
    server = SimpHttpServer()
    server.broker.state = BrokerState.RUNNING
    server.broker._ready = True
    if hasattr(server.broker, "_startup_at"):
        server.broker._startup_at = None
    return server.app.test_client(), server.broker


class TestSprint65E2ESmoke(unittest.TestCase):
    """End-to-end smoke tests."""

    # ----- Flow 1: Full agent lifecycle -----
    def test_agent_full_lifecycle(self):
        client, broker = _make_client()
        # Register
        resp = client.post("/agents/register", json={
            "agent_id": "smoke_test_agent", "agent_type": "test",
            "endpoint": "http://127.0.0.1:9999", "capabilities": ["planning", "test"],
        }, headers={"X-API-Key": "test"})
        self.assertIn(resp.status_code, (200, 201))

        # Verify appears in list
        resp = client.get("/agents", headers={"X-API-Key": "test"})
        self.assertIn("smoke_test_agent", resp.get_json().get("agents", {}))

        # Heartbeat
        resp = client.post("/agents/smoke_test_agent/heartbeat")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["agent_id"], "smoke_test_agent")

        # Get heartbeat status
        resp = client.get("/agents/smoke_test_agent/heartbeat", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["stale"])

        # Deregister
        resp = client.delete("/agents/smoke_test_agent", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)

        # Verify gone
        resp = client.get("/agents/smoke_test_agent", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 404)

    # ----- Flow 2: Route intent with file-based agent -----
    def test_route_to_file_based_agent(self):
        client, broker = _make_client()
        client.post("/agents/register", json={
            "agent_id": "test_file_agent", "agent_type": "file_agent",
            "endpoint": "(file-based)", "capabilities": ["planning"],
        }, headers={"X-API-Key": "test"})

        resp = client.post("/intents/route", json={
            "intent_type": "planning",
            "source_agent": "test",
            "target_agent": "test_file_agent",
            "params": {"goal": "test"},
        }, headers={"X-API-Key": "test"})

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn(data.get("status"), ("routed", "ok"))

    # ----- Flow 3: Auto-routing -----
    def test_auto_routing(self):
        client, broker = _make_client()
        # Register directly on broker to bypass HTTP validation quirks
        broker.register_agent("analysis_agent", "analysis", "(file-based)",
                              {"capabilities": ["research"]})

        resp = client.post("/intents/route", json={
            "intent_type": "research",
            "source_agent": "test",
            "target_agent": "auto",
            "params": {},
        }, headers={"X-API-Key": "test"})

        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.get_json().get("error_code"), "AGENT_NOT_FOUND")

    # ----- Flow 4: Record response + check status -----
    def test_intent_lifecycle_record_response(self):
        client, broker = _make_client()
        broker.register_agent("resp_agent", "test", "(file-based)")

        resp = client.post("/intents/route", json={
            "intent_type": "planning", "source_agent": "test",
            "target_agent": "resp_agent", "params": {},
        }, headers={"X-API-Key": "test"})
        intent_id = resp.get_json().get("intent_id")
        self.assertIsNotNone(intent_id)

        # Record response
        resp = client.post(f"/intents/{intent_id}/response",
            json={"response": {"result": "pong"}, "execution_time_ms": 10.0},
            headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)

        # Check status
        resp = client.get(f"/intents/{intent_id}", headers={"X-API-Key": "test"})
        self.assertEqual(resp.get_json().get("intent", {}).get("status"), "completed")

    # ----- Flow 5: Broker readiness -----
    def test_broker_ready_endpoint(self):
        client, broker = _make_client()
        resp = client.get("/control/ready")
        self.assertIn(resp.status_code, (200, 503))
        data = resp.get_json()
        self.assertIn("ready", data)
        self.assertIn("broker_state", data)

    # ----- Flow 6: Stats accuracy -----
    def test_stats_after_routing(self):
        client, broker = _make_client()
        broker.register_agent("stats_agent", "test", "(file-based)")

        before = client.get("/stats", headers={"X-API-Key": "test"}).get_json()
        received_before = before.get("stats", {}).get("intents_received", 0)

        # Route one intent
        client.post("/intents/route", json={
            "intent_type": "planning", "source_agent": "stats_test",
            "target_agent": "stats_agent", "params": {},
        }, headers={"X-API-Key": "test"})

        after = client.get("/stats", headers={"X-API-Key": "test"}).get_json()
        self.assertEqual(
            after.get("stats", {}).get("intents_received", 0),
            received_before + 1
        )

    # ----- Flow 7: A2A task submission -----
    def test_a2a_task_full_flow(self):
        client, broker = _make_client()
        resp = client.post("/a2a/tasks", json={
            "task_type": "research",
            "input": {"text": "What is SIMP?"},
            "metadata": {},
        }, headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("x-simp", data)
        task_id = data.get("taskId") or data.get("task_id") or data.get("id")
        self.assertIsNotNone(task_id)

    # ----- Flow 8: Orchestration maintenance plan -----
    def test_orchestration_maintenance_plan(self):
        client, broker = _make_client()
        resp = client.post("/orchestration/plans/maintenance",
            headers={"X-API-Key": "test"})
        self.assertIn(resp.status_code, (200, 201))
        data = resp.get_json()
        plan = data.get("plan", data)
        self.assertIn(plan.get("status"), ("completed", "failed", "running", "pending", "created"))
        self.assertEqual(len(plan.get("steps", [])), 3)

    # ----- Flow 9: Routing policy -----
    def test_routing_policy_covers_known_types(self):
        client, broker = _make_client()
        resp = client.get("/routing-policy", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        rp = resp.get_json().get("routing_policy", {})
        rules = rp.get("rules", [])
        types = [r.get("intent_type") for r in rules]
        for expected in ["planning", "research"]:
            self.assertIn(expected, types)

    # ----- Flow 10: Sweep stale -----
    def test_sweep_stale_valid_response(self):
        client, broker = _make_client()
        resp = client.post("/agents/sweep-stale", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("deregistered", data)
        self.assertIn("count", data)

    # ----- Flow 11: GET /agents includes heartbeat fields -----
    def test_agents_includes_heartbeat_fields(self):
        client, broker = _make_client()
        broker.register_agent("hb_agent", "test", "http://localhost:9000")
        resp = client.get("/agents", headers={"X-API-Key": "test"})
        data = resp.get_json()
        agent = data["agents"]["hb_agent"]
        self.assertIn("last_heartbeat", agent)
        self.assertIn("heartbeat_count", agent)
        self.assertIn("stale", agent)
        self.assertIn("file_based", agent)

    # ----- Flow 12: GET /stats includes stale_agents -----
    def test_stats_includes_stale_agents(self):
        client, broker = _make_client()
        resp = client.get("/stats", headers={"X-API-Key": "test"})
        data = resp.get_json()
        self.assertIn("stale_agents", data.get("stats", {}))

    # ----- Flow 13: GET /intents/flows returns list -----
    def test_intents_flows_returns_list(self):
        client, broker = _make_client()
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("flows", data)
        self.assertIsInstance(data["flows"], list)

    # ----- Flow 14: POST /reload-routing-policy -----
    def test_reload_routing_policy(self):
        client, broker = _make_client()
        resp = client.post("/reload-routing-policy", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("rule_count", data)

    # ----- Flow 15: A2A events -----
    def test_a2a_events_list(self):
        client, broker = _make_client()
        resp = client.get("/a2a/events", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("events", data)
        self.assertIsInstance(data["events"], list)


if __name__ == "__main__":
    unittest.main()
