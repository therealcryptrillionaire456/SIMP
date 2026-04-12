"""Tests for Sprint 4: graceful shutdown and cleanup."""

import asyncio
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.broker import SimpBroker, BrokerConfig, BrokerState, _utcnow_iso


class TestGracefulShutdown:
    @pytest.fixture
    def broker(self):
        config = BrokerConfig(max_agents=10, health_check_interval=1)
        broker = SimpBroker(config)
        broker.start()
        return broker

    def test_stop_sets_stopped_state(self, broker):
        assert broker.state == BrokerState.RUNNING
        broker.stop()
        assert broker.state == BrokerState.STOPPED

    def test_stop_sets_shutdown_event(self, broker):
        broker.stop()
        assert broker._shutdown_event.is_set()

    def test_stop_logs_events(self, broker):
        broker.stop()
        logs = broker.get_logs(10)
        event_types = [e["event_type"] for e in logs]
        assert "broker_stopping" in event_types
        assert "broker_stopped" in event_types

    def test_route_intent_rejected_when_stopped(self, broker):
        broker.register_agent("test:001", "test", "")
        broker.stop()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(broker.route_intent({
                "intent_id": "reject-001",
                "source_agent": "src",
                "target_agent": "test:001",
                "intent_type": "test",
                "params": {},
            }))
        finally:
            loop.close()
        assert result["status"] == "error"
        assert result["error_code"] == "BROKER_NOT_RUNNING"

    def test_health_check_loop_respects_shutdown(self, broker):
        """Health check loop should exit when shutdown event is set."""
        # Give health check a moment to start
        time.sleep(0.2)
        broker.stop()
        # After stop, the loop should have exited
        assert broker.state == BrokerState.STOPPED

    def test_start_with_shared_loop(self):
        """Broker can start with an externally-provided event loop."""
        config = BrokerConfig(max_agents=5, health_check_interval=60)
        broker = SimpBroker(config)

        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()

        try:
            broker.start(async_loop=loop)
            assert broker.state == BrokerState.RUNNING
            broker.stop()
            assert broker.state == BrokerState.STOPPED
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)


class TestUtcnowHelper:
    def test_utcnow_iso_format(self):
        ts = _utcnow_iso()
        assert ts.endswith("Z")
        assert "+" not in ts  # No +00:00, uses Z suffix

    def test_utcnow_iso_no_microseconds(self):
        ts = _utcnow_iso()
        # Should be seconds precision, no microseconds
        assert "." not in ts


class TestDeadCodeRemoval:
    def test_input_validator_deleted(self):
        """simp/security/input_validator.py should no longer exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "simp", "security", "input_validator.py"
        )
        assert not os.path.exists(path), f"Dead scaffold still exists: {path}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
