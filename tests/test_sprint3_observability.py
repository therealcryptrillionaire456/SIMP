"""Tests for Sprint 3: structured logging and event ring buffer."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.broker import SimpBroker, BrokerConfig


class TestStructuredEventLog:
    @pytest.fixture
    def broker(self):
        config = BrokerConfig(max_agents=10)
        broker = SimpBroker(config)
        broker.start()
        return broker

    def test_empty_logs(self, broker):
        # Only the start event should be there (if we logged it)
        logs = broker.get_logs(10)
        assert isinstance(logs, list)

    def test_register_agent_logged(self, broker):
        broker.register_agent("test:001", "test", "")
        logs = broker.get_logs(10)
        events = [e for e in logs if e["event_type"] == "agent_registered"]
        assert len(events) >= 1
        assert events[0]["agent_id"] == "test:001"

    def test_deregister_agent_logged(self, broker):
        broker.register_agent("test:002", "test", "")
        broker.deregister_agent("test:002")
        logs = broker.get_logs(10)
        events = [e for e in logs if e["event_type"] == "agent_deregistered"]
        assert len(events) >= 1

    def test_route_intent_logged(self, broker):
        broker.register_agent("target:001", "test", "")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(broker.route_intent({
                "intent_id": "test-intent-001",
                "source_agent": "src",
                "target_agent": "target:001",
                "intent_type": "test",
                "params": {},
            }))
        finally:
            loop.close()
        logs = broker.get_logs(10)
        events = [e for e in logs if e["event_type"] == "intent_routed"]
        assert len(events) >= 1
        assert events[0]["intent_id"] == "test-intent-001"

    def test_intent_failed_logged(self, broker):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(broker.route_intent({
                "intent_id": "fail-intent-001",
                "source_agent": "src",
                "target_agent": "nonexistent:999",
                "intent_type": "test",
                "params": {},
            }))
        finally:
            loop.close()
        logs = broker.get_logs(10)
        events = [e for e in logs if e["event_type"] == "intent_failed"]
        assert len(events) >= 1

    def test_response_recorded_logged(self, broker):
        broker.register_agent("target:002", "test", "")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(broker.route_intent({
                "intent_id": "resp-intent-001",
                "source_agent": "src",
                "target_agent": "target:002",
                "intent_type": "test",
                "params": {},
            }))
        finally:
            loop.close()
        broker.record_response("resp-intent-001", {"ok": True}, 5.0)
        logs = broker.get_logs(10)
        events = [e for e in logs if e["event_type"] == "response_recorded"]
        assert len(events) >= 1

    def test_get_logs_limit(self, broker):
        # Register several agents to generate events
        for i in range(10):
            broker.register_agent(f"bulk:{i:03d}", "test", "")
        logs = broker.get_logs(3)
        assert len(logs) <= 3

    def test_get_logs_most_recent_first(self, broker):
        broker.register_agent("first:001", "test", "")
        broker.register_agent("second:002", "test", "")
        logs = broker.get_logs(10)
        reg_events = [e for e in logs if e["event_type"] == "agent_registered"]
        assert len(reg_events) >= 2
        # Most recent first
        assert reg_events[0]["agent_id"] == "second:002"
        assert reg_events[1]["agent_id"] == "first:001"

    def test_event_structure(self, broker):
        broker.register_agent("struct:001", "test", "")
        logs = broker.get_logs(1)
        event = logs[0]
        assert "timestamp" in event
        assert "event_type" in event
        assert "level" in event
        assert "message" in event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
