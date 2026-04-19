"""
Tests for Sprint 62 — Agent Heartbeat System
"""

import os
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

os.environ.setdefault("SIMP_REQUIRE_API_KEY", "false")

from simp.server.broker import SimpBroker, BrokerConfig, BrokerState
from simp.server.http_server import SimpHttpServer


def _make_broker():
    """Create a broker in RUNNING state for testing."""
    b = SimpBroker(BrokerConfig())
    b.state = BrokerState.RUNNING
    # Clear startup_at to avoid grace period interference
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


class TestBrokerHeartbeat(unittest.TestCase):
    """Broker-level heartbeat tests."""

    def test_record_heartbeat_updates_timestamp(self):
        broker = _make_broker()
        broker.register_agent("a1", "test", "http://localhost:9000")
        # Set to a known old time
        broker.agents["a1"]["last_heartbeat"] = "2020-01-01T00:00:00Z"
        result = broker.record_heartbeat("a1")
        self.assertTrue(result)
        self.assertNotEqual(broker.agents["a1"]["last_heartbeat"], "2020-01-01T00:00:00Z")

    def test_record_heartbeat_returns_false_for_unknown(self):
        broker = _make_broker()
        self.assertFalse(broker.record_heartbeat("nonexistent"))

    def test_record_heartbeat_increments_count(self):
        broker = _make_broker()
        broker.register_agent("a1", "test", "http://localhost:9000")
        self.assertEqual(broker.agents["a1"]["heartbeat_count"], 0)
        broker.record_heartbeat("a1")
        self.assertEqual(broker.agents["a1"]["heartbeat_count"], 1)
        broker.record_heartbeat("a1")
        self.assertEqual(broker.agents["a1"]["heartbeat_count"], 2)

    def test_get_stale_agents_returns_stale(self):
        broker = _make_broker()
        broker.register_agent("a1", "test", "http://localhost:9000")
        # Set heartbeat to 2 minutes ago
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
        broker.agents["a1"]["last_heartbeat"] = old_time
        stale = broker.get_stale_agents(stale_after_seconds=90.0)
        self.assertIn("a1", stale)

    def test_get_stale_agents_excludes_file_based(self):
        broker = _make_broker()
        broker.register_agent("fb1", "file_agent", "(file-based)")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
        broker.agents["fb1"]["last_heartbeat"] = old_time
        stale = broker.get_stale_agents(stale_after_seconds=90.0)
        self.assertNotIn("fb1", stale)

    def test_deregister_stale_agents_removes_stale(self):
        broker = _make_broker()
        broker.register_agent("a1", "test", "http://localhost:9000")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat().replace("+00:00", "Z")
        broker.agents["a1"]["last_heartbeat"] = old_time
        removed = broker.deregister_stale_agents(deregister_after_seconds=300.0)
        self.assertIn("a1", removed)
        self.assertNotIn("a1", broker.agents)

    def test_deregister_stale_agents_does_not_remove_file_based(self):
        broker = _make_broker()
        broker.register_agent("fb1", "file_agent", "(file-based)")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat().replace("+00:00", "Z")
        broker.agents["fb1"]["last_heartbeat"] = old_time
        removed = broker.deregister_stale_agents(deregister_after_seconds=300.0)
        self.assertNotIn("fb1", removed)
        self.assertIn("fb1", broker.agents)

    def test_deregister_stale_agents_returns_list(self):
        broker = _make_broker()
        broker.register_agent("a1", "test", "http://localhost:9000")
        broker.register_agent("a2", "test", "http://localhost:9001")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat().replace("+00:00", "Z")
        broker.agents["a1"]["last_heartbeat"] = old_time
        broker.agents["a2"]["last_heartbeat"] = old_time
        removed = broker.deregister_stale_agents(deregister_after_seconds=300.0)
        self.assertEqual(len(removed), 2)
        self.assertIsInstance(removed, list)


class TestHeartbeatHTTP(unittest.TestCase):
    """HTTP route tests for heartbeat."""

    def test_post_heartbeat_200(self):
        client, broker = _make_client()
        broker.register_agent("a1", "test", "http://localhost:9000")
        resp = client.post("/agents/a1/heartbeat")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["agent_id"], "a1")
        self.assertIn("heartbeat_at", data)

    def test_post_heartbeat_404_unknown(self):
        client, broker = _make_client()
        resp = client.post("/agents/unknown_agent/heartbeat")
        self.assertEqual(resp.status_code, 404)

    def test_post_heartbeat_no_auth_required(self):
        client, broker = _make_client()
        broker.register_agent("a1", "test", "http://localhost:9000")
        # No API key header — should still work
        resp = client.post("/agents/a1/heartbeat")
        self.assertEqual(resp.status_code, 200)

    def test_get_heartbeat_stale_false_for_fresh(self):
        client, broker = _make_client()
        broker.register_agent("a1", "test", "http://localhost:9000")
        broker.record_heartbeat("a1")
        resp = client.get("/agents/a1/heartbeat", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["stale"])

    def test_get_heartbeat_stale_true_for_old(self):
        client, broker = _make_client()
        broker.register_agent("a1", "test", "http://localhost:9000")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
        broker.agents["a1"]["last_heartbeat"] = old_time
        broker.agents["a1"]["stale"] = True
        resp = client.get("/agents/a1/heartbeat", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["stale"])

    def test_get_agents_includes_heartbeat_fields(self):
        client, broker = _make_client()
        broker.register_agent("a1", "test", "http://localhost:9000")
        resp = client.get("/agents", headers={"X-API-Key": "test"})
        data = resp.get_json()
        agent_data = data["agents"]["a1"]
        self.assertIn("last_heartbeat", agent_data)
        self.assertIn("heartbeat_count", agent_data)
        self.assertIn("stale", agent_data)
        self.assertIn("file_based", agent_data)

    def test_get_agents_file_based_true(self):
        client, broker = _make_client()
        broker.register_agent("fb1", "file_agent", "(file-based)")
        resp = client.get("/agents", headers={"X-API-Key": "test"})
        data = resp.get_json()
        self.assertTrue(data["agents"]["fb1"]["file_based"])

    def test_sweep_stale_returns_deregistered(self):
        client, broker = _make_client()
        broker.register_agent("a1", "test", "http://localhost:9000")
        # Make it very stale
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat().replace("+00:00", "Z")
        broker.agents["a1"]["last_heartbeat"] = old_time
        resp = client.post("/agents/sweep-stale", headers={"X-API-Key": "test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("deregistered", data)
        self.assertIn("count", data)

    def test_get_stats_includes_stale_agents(self):
        client, broker = _make_client()
        resp = client.get("/stats", headers={"X-API-Key": "test"})
        data = resp.get_json()
        self.assertIn("stale_agents", data.get("stats", {}))


if __name__ == "__main__":
    unittest.main()
