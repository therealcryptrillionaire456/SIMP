"""
Tests for Sprint 63 — Planner Telemetry Enhancement
"""

import os
import time
import unittest
from datetime import datetime, timezone

os.environ.setdefault("SIMP_REQUIRE_API_KEY", "false")

from simp.server.broker import SimpBroker, BrokerConfig, BrokerState, IntentRecord
from simp.server.http_server import SimpHttpServer


def _make_broker():
    """Create a broker in RUNNING state for testing."""
    b = SimpBroker(BrokerConfig())
    b.state = BrokerState.RUNNING
    if hasattr(b, "_startup_at"):
        b._startup_at = None
    return b


def _make_client():
    """Create Flask test client with broker running."""
    server = SimpHttpServer()
    server.broker.state = BrokerState.RUNNING
    if hasattr(server.broker, "_startup_at"):
        server.broker._startup_at = None
    return server.app.test_client(), server.broker


class TestIntentRecordFields(unittest.TestCase):
    """Test that IntentRecord has the new telemetry fields."""

    def test_intent_record_has_planned_at(self):
        r = IntentRecord(
            intent_id="i1", source_agent="a", target_agent="b",
            intent_type="test", timestamp="2026-01-01T00:00:00Z",
            status="pending",
        )
        self.assertIsNone(r.planned_at)
        r.planned_at = "2026-01-01T00:00:00Z"
        self.assertEqual(r.planned_at, "2026-01-01T00:00:00Z")

    def test_intent_record_has_dispatched_at(self):
        r = IntentRecord(
            intent_id="i1", source_agent="a", target_agent="b",
            intent_type="test", timestamp="now", status="pending",
        )
        self.assertIsNone(r.dispatched_at)

    def test_intent_record_has_completed_at(self):
        r = IntentRecord(
            intent_id="i1", source_agent="a", target_agent="b",
            intent_type="test", timestamp="now", status="pending",
        )
        self.assertIsNone(r.completed_at)

    def test_intent_record_has_retry_count(self):
        r = IntentRecord(
            intent_id="i1", source_agent="a", target_agent="b",
            intent_type="test", timestamp="now", status="pending",
        )
        self.assertEqual(r.retry_count, 0)


class TestRoutingTelemetry(unittest.TestCase):
    """Test that route_intent sets timing fields."""

    def test_route_intent_sets_planned_at(self):
        client, broker = _make_client()
        broker.register_agent("tgt", "test", "(file-based)", {"capabilities": ["ping"]})
        resp = client.post("/intents/route", json={
            "intent_type": "planning", "source_agent": "test",
            "target_agent": "tgt", "params": {},
        }, headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        intent_id = resp.get_json().get("intent_id")
        self.assertIsNotNone(intent_id)
        record = broker.intent_records.get(intent_id)
        self.assertIsNotNone(record)
        self.assertIsNotNone(record.planned_at)

    def test_route_intent_sets_dispatched_at(self):
        client, broker = _make_client()
        broker.register_agent("tgt", "test", "(file-based)", {"capabilities": ["ping"]})
        resp = client.post("/intents/route", json={
            "intent_type": "planning", "source_agent": "test",
            "target_agent": "tgt", "params": {},
        }, headers={"X-API-Key": "test"})
        intent_id = resp.get_json().get("intent_id")
        record = broker.intent_records.get(intent_id)
        self.assertIsNotNone(record.dispatched_at)


class TestRecordSetsCompleted(unittest.TestCase):
    """Test that record_response/record_error sets completed_at."""

    def test_record_response_sets_completed_at(self):
        broker = _make_broker()
        broker.register_agent("tgt", "test", "(file-based)")
        broker.intent_records["i1"] = IntentRecord(
            intent_id="i1", source_agent="src", target_agent="tgt",
            intent_type="test", timestamp="2026-01-01T00:00:00Z",
            status="pending", planned_at="2026-01-01T00:00:00Z",
        )
        broker.record_response("i1", {"result": "ok"})
        self.assertIsNotNone(broker.intent_records["i1"].completed_at)

    def test_record_error_sets_completed_at(self):
        broker = _make_broker()
        broker.intent_records["i2"] = IntentRecord(
            intent_id="i2", source_agent="src", target_agent="tgt",
            intent_type="test", timestamp="2026-01-01T00:00:00Z",
            status="pending",
        )
        broker.record_error("i2", "some error")
        self.assertIsNotNone(broker.intent_records["i2"].completed_at)


class TestFlowsEndpoint(unittest.TestCase):
    """Test GET /intents/flows response."""

    def _setup_flow(self, client, broker):
        broker.register_agent("fa", "test", "(file-based)", {"capabilities": ["ping"]})
        resp = client.post("/intents/route", json={
            "intent_type": "planning", "source_agent": "flow_test",
            "target_agent": "fa", "params": {},
        }, headers={"X-API-Key": "test"})
        intent_id = resp.get_json().get("intent_id")
        # Record response to set completed_at
        client.post(f"/intents/{intent_id}/response",
            json={"response": {"ok": True}, "execution_time_ms": 50.0},
            headers={"X-API-Key": "test"})
        return intent_id

    def test_flows_returns_list(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("flows", data)
        self.assertIsInstance(data["flows"], list)

    def test_flows_step_includes_planned_at(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        found = False
        for flow in flows:
            for step in flow.get("steps", []):
                if step.get("planned_at") is not None:
                    found = True
                    break
        self.assertTrue(found, "No step with planned_at found")

    def test_flows_step_includes_total_elapsed_ms(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        for flow in flows:
            for step in flow.get("steps", []):
                self.assertIn("total_elapsed_ms", step)

    def test_flows_step_includes_gantt(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        for flow in flows:
            for step in flow.get("steps", []):
                self.assertIn("gantt", step)

    def test_flows_flow_level_total_elapsed_ms(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        self.assertTrue(len(flows) > 0)
        for flow in flows:
            self.assertIn("total_elapsed_ms", flow)
            self.assertIn("step_count", flow)
            self.assertIn("failed_steps", flow)
            self.assertIn("retry_total", flow)

    def test_gantt_bar_pct_in_range(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        for flow in flows:
            for step in flow.get("steps", []):
                gantt = step.get("gantt")
                if gantt:
                    self.assertGreaterEqual(gantt["bar_pct_start"], 0.0)
                    self.assertLessEqual(gantt["bar_pct_start"], 1.0)
                    self.assertGreaterEqual(gantt["bar_pct_width"], 0.0)
                    self.assertLessEqual(gantt["bar_pct_width"], 1.0)

    def test_planned_to_dispatched_ms_non_negative(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        for flow in flows:
            for step in flow.get("steps", []):
                if step.get("planned_to_dispatched_ms") is not None:
                    self.assertGreaterEqual(step["planned_to_dispatched_ms"], 0)

    def test_dispatched_to_completed_ms_non_negative(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        for flow in flows:
            for step in flow.get("steps", []):
                if step.get("dispatched_to_completed_ms") is not None:
                    self.assertGreaterEqual(step["dispatched_to_completed_ms"], 0)

    def test_flow_detail_by_id(self):
        client, broker = _make_client()
        self._setup_flow(client, broker)
        resp = client.get("/intents/flows", headers={"X-API-Key": "test"})
        flows = resp.get_json()["flows"]
        if flows:
            flow_id = flows[0]["flow_id"]
            resp2 = client.get(f"/intents/flows/{flow_id}", headers={"X-API-Key": "test"})
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.get_json()["flow"]["flow_id"], flow_id)

    def test_flow_detail_404_for_unknown(self):
        client, broker = _make_client()
        resp = client.get("/intents/flows/nonexistent_flow_id", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
