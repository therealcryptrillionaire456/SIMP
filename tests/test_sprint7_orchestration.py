"""Tests for Sprint 7: Orchestration loop integration."""

import asyncio
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.broker import SimpBroker, BrokerConfig, BrokerState
from simp.orchestration.orchestration_loop import OrchestrationLoop


class TestOrchestrationLoop:
    @pytest.fixture
    def broker(self):
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        return SimpBroker(config)

    def test_orchestration_loop_creation(self, broker):
        loop = OrchestrationLoop(broker=broker, task_ledger=broker.task_ledger)
        assert loop is not None
        assert loop.running is False

    def test_orchestration_loop_stop(self, broker):
        loop = OrchestrationLoop(broker=broker, task_ledger=broker.task_ledger)
        loop.running = True
        loop.stop()
        assert loop.running is False

    def test_broker_start_creates_orchestration(self, broker):
        """Broker.start() should create an orchestration loop."""
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        try:
            broker.start(async_loop=loop)
            assert broker._orchestration_loop is not None
            broker.stop()
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)

    def test_broker_stop_stops_orchestration(self, broker):
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        try:
            broker.start(async_loop=loop)
            assert broker._orchestration_loop is not None
            broker.stop()
            assert broker._orchestration_loop.running is False
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)

    def test_orchestration_started_logged(self, broker):
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        try:
            broker.start(async_loop=loop)
            logs = broker.get_logs(20)
            events = [e["event_type"] for e in logs]
            assert "orchestration_started" in events
            broker.stop()
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)

    def test_orchestration_stopped_logged(self, broker):
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        try:
            broker.start(async_loop=loop)
            broker.stop()
            logs_after = broker.get_logs(20)
            events_after = [e["event_type"] for e in logs_after]
            assert "orchestration_stopped" in events_after
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
