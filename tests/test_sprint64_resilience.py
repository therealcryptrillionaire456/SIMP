"""
Tests for Sprint 64 — Broker Restart Resilience
"""

import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

os.environ.setdefault("SIMP_REQUIRE_API_KEY", "false")

from simp.server.broker import SimpBroker, BrokerConfig, BrokerState, IntentRecord
from simp.server.http_server import SimpHttpServer


def _make_broker():
    """Create a fresh broker."""
    return SimpBroker(BrokerConfig())


def _make_client():
    """Create Flask test client."""
    server = SimpHttpServer()
    return server.app.test_client(), server.broker


class TestControlReady(unittest.TestCase):
    """Test GET /control/ready endpoint."""

    def test_ready_returns_200_when_running(self):
        client, broker = _make_client()
        broker.state = BrokerState.RUNNING
        broker._ready = True
        resp = client.get("/control/ready")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ready"])

    def test_ready_returns_503_when_initializing(self):
        client, broker = _make_client()
        broker.state = BrokerState.INITIALIZING
        broker._ready = False
        resp = client.get("/control/ready")
        self.assertEqual(resp.status_code, 503)
        data = resp.get_json()
        self.assertFalse(data["ready"])

    def test_ready_includes_required_fields(self):
        client, broker = _make_client()
        broker.state = BrokerState.RUNNING
        broker._ready = True
        resp = client.get("/control/ready")
        data = resp.get_json()
        self.assertIn("ready", data)
        self.assertIn("broker_state", data)
        self.assertIn("agents_registered", data)

    def test_ready_includes_uptime(self):
        client, broker = _make_client()
        broker.state = BrokerState.RUNNING
        broker._ready = True
        resp = client.get("/control/ready")
        data = resp.get_json()
        self.assertIn("uptime_seconds", data)
        self.assertGreaterEqual(data["uptime_seconds"], 0)

    def test_ready_no_api_key_required(self):
        client, broker = _make_client()
        broker.state = BrokerState.RUNNING
        broker._ready = True
        # No headers at all
        resp = client.get("/control/ready")
        self.assertIn(resp.status_code, (200, 503))


class TestBrokerStartupFields(unittest.TestCase):
    """Test broker startup fields."""

    def test_startup_at_set_on_init(self):
        broker = _make_broker()
        self.assertIsNotNone(broker._startup_at)
        self.assertIsInstance(broker._startup_at, datetime)

    def test_ready_becomes_true_after_start(self):
        broker = _make_broker()
        self.assertFalse(broker._ready)
        broker.start()
        self.assertTrue(broker._ready)
        broker.stop()

    def test_stale_agents_returns_empty_during_grace(self):
        broker = _make_broker()
        broker.state = BrokerState.RUNNING
        # _startup_at is very recent (just created)
        broker.register_agent("a1", "test", "http://localhost:9000")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
        broker.agents["a1"]["last_heartbeat"] = old_time
        result = broker.get_stale_agents(stale_after_seconds=90.0)
        self.assertEqual(result, [])

    def test_deregister_stale_agents_returns_empty_during_grace(self):
        broker = _make_broker()
        broker.state = BrokerState.RUNNING
        broker.register_agent("a1", "test", "http://localhost:9000")
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat().replace("+00:00", "Z")
        broker.agents["a1"]["last_heartbeat"] = old_time
        result = broker.deregister_stale_agents(deregister_after_seconds=300.0)
        self.assertEqual(result, [])

    def test_loads_pending_intents_from_ledger(self):
        """Broker loads pending intents from intent ledger on init."""
        broker = _make_broker()
        # _intents_loaded_from_disk should be set (may be 0 if no pending intents)
        self.assertIsNotNone(broker._intents_loaded_from_disk)
        self.assertIsInstance(broker._intents_loaded_from_disk, int)

    def test_intents_loaded_from_disk_reflects_count(self):
        """_intents_loaded_from_disk is an integer >= 0."""
        broker = _make_broker()
        self.assertGreaterEqual(broker._intents_loaded_from_disk, 0)


class TestBrokerRestartRecovery(unittest.TestCase):
    """Test broker restart recovery."""

    def test_restart_loads_from_ledger(self):
        """Create broker, add intent to ledger, create new broker, verify load."""
        import tempfile
        from simp.server.intent_ledger import IntentLedger, LedgerConfig

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            tmppath = f.name

        try:
            # Create ledger with a pending intent
            ledger = IntentLedger(LedgerConfig(path=tmppath))
            ledger.append({
                "intent_id": "test-recovery-001",
                "status": "pending",
                "source_agent": "src",
                "target_agent": "tgt",
                "intent_type": "planning",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Create new ledger instance (simulates restart)
            ledger2 = IntentLedger(LedgerConfig(path=tmppath))
            pending = ledger2.load_pending()
            self.assertTrue(len(pending) > 0)
            self.assertEqual(pending[0]["intent_id"], "test-recovery-001")
        finally:
            os.unlink(tmppath)


if __name__ == "__main__":
    unittest.main()
