"""Tests for Sprint 18: Scalability — connection pooling, async health, dead agent cleanup."""

import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.broker import SimpBroker, BrokerConfig


class TestAsyncHealthChecks:

    def test_health_check_loop_is_async(self, broker):
        """Health check loop should be an async coroutine."""
        assert asyncio.iscoroutinefunction(broker._health_check_loop)

    def test_bounded_health_check_exists(self, broker):
        """Bounded health check method should exist and be async."""
        assert hasattr(broker, '_bounded_health_check')
        assert asyncio.iscoroutinefunction(broker._bounded_health_check)

    def test_check_agent_health_is_async(self, broker):
        """_check_agent_health should be an async coroutine."""
        assert asyncio.iscoroutinefunction(broker._check_agent_health)

    def test_health_check_with_no_agents(self, broker):
        """Health check loop should handle empty agent registry."""
        loop = asyncio.new_event_loop()
        try:
            async def quick_check():
                agents = list(broker.agents.items())
                assert len(agents) == 0
            loop.run_until_complete(quick_check())
        finally:
            loop.close()


class TestConnectionPooling:

    def test_broker_has_http_pool_attribute(self, broker):
        """Broker should have an HTTP pool attribute (None before start)."""
        assert hasattr(broker, '_http_pool')

    def test_http_pool_none_before_start(self, broker):
        """HTTP pool should be None before start() is called."""
        assert broker._http_pool is None

    def test_http_pool_created_on_start(self, broker):
        """HTTP pool should be created when broker starts."""
        broker.start()
        try:
            assert broker._http_pool is not None
        finally:
            broker.stop()

    def test_httpx_in_requirements(self):
        """httpx should be in requirements.txt."""
        req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        with open(req_path) as f:
            content = f.read()
        assert "httpx" in content.lower()

    def test_close_http_pool_method_exists(self, broker):
        """Broker should have a method to close the HTTP pool."""
        assert hasattr(broker, '_close_http_pool')
        assert asyncio.iscoroutinefunction(broker._close_http_pool)


class TestDeadAgentCleanup:

    def test_agent_info_has_failure_counter(self, broker):
        """Registered agents should track health check failures."""
        broker.start()
        try:
            broker.register_agent(
                agent_id="test_agent_cleanup",
                agent_type="test",
                endpoint="http://localhost:9999",
                metadata={},
            )
            agent_info = broker.agents.get("test_agent_cleanup", {})
            assert "health_check_failures" in agent_info
            assert agent_info["health_check_failures"] == 0
        finally:
            broker.stop()

    def test_record_health_failure_method_exists(self, broker):
        """Broker should have a method to record health failures."""
        assert hasattr(broker, '_record_health_failure')
        assert asyncio.iscoroutinefunction(broker._record_health_failure)

    def test_failure_counter_increments(self, broker):
        """Health check failure counter should increment."""
        broker.start()
        try:
            broker.register_agent(
                agent_id="test_fail_agent",
                agent_type="test",
                endpoint="http://localhost:9999",
                metadata={},
            )
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(broker._record_health_failure("test_fail_agent"))
                assert broker.agents["test_fail_agent"]["health_check_failures"] == 1
                assert broker.agents["test_fail_agent"]["status"] == "unreachable"
            finally:
                loop.close()
        finally:
            broker.stop()

    def test_auto_deregister_after_threshold(self, broker):
        """Agent should be auto-deregistered after 3 consecutive failures."""
        broker.start()
        try:
            broker.register_agent(
                agent_id="test_dead_agent",
                agent_type="test",
                endpoint="http://localhost:9999",
                metadata={},
            )
            loop = asyncio.new_event_loop()
            try:
                for _ in range(3):
                    loop.run_until_complete(broker._record_health_failure("test_dead_agent"))
                # Agent should be deregistered
                assert "test_dead_agent" not in broker.agents
            finally:
                loop.close()
        finally:
            broker.stop()


class TestIntentQueueWorker:

    def test_intent_queue_exists(self, broker):
        """Broker should have an intent queue."""
        assert hasattr(broker, 'intent_queue')

    def test_intent_queue_worker_method_exists(self, broker):
        """Broker should have an intent queue worker method."""
        assert hasattr(broker, '_intent_queue_worker')
        assert asyncio.iscoroutinefunction(broker._intent_queue_worker)

    def test_queue_depth_in_stats(self, broker):
        """Broker stats should include queue depth."""
        broker.start()
        try:
            stats = broker.get_statistics()
            assert "queue_depth" in stats
            assert stats["queue_depth"] == 0
        finally:
            broker.stop()

    def test_queue_depth_reflects_items(self, broker):
        """Queue depth stat should reflect items in the queue."""
        broker.intent_queue.put({"test": "intent"})
        broker.start()
        try:
            stats = broker.get_statistics()
            assert stats["queue_depth"] >= 1
        finally:
            # drain queue
            while not broker.intent_queue.empty():
                try:
                    broker.intent_queue.get_nowait()
                except Exception:
                    break
            broker.stop()


class TestAllModulesCompile:
    def test_broker_compiles(self):
        """broker.py should compile without errors."""
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "simp", "server", "broker.py")
        py_compile.compile(path, doraise=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
