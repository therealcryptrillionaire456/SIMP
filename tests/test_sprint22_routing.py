"""Tests for Sprint 22: Smart routing, load balancing, circuit breaker, priority dispatch."""

import os
import sys
import json
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDynamicRoutingReload:
    def test_builder_pool_has_check_reload(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        assert hasattr(bp, 'check_reload')
        assert callable(bp.check_reload)

    def test_builder_pool_loads_policy(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        assert hasattr(bp, '_policy_mtime')
        assert bp._policy_mtime > 0

    def test_check_reload_returns_false_when_unchanged(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        # No change since init — should return False
        assert bp.check_reload() is False

    def test_check_reload_detects_change(self):
        from simp.routing.builder_pool import BuilderPool
        # Create a temp policy file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "builder_pool": {"primary": "a", "secondary": "b", "support": []},
                "task_routing": {"test": ["a"]},
                "fallback_rules": {}
            }, f)
            tmp_path = f.name

        try:
            bp = BuilderPool(policy_path=tmp_path)
            assert bp._task_routing == {"test": ["a"]}

            # Write updated policy
            time.sleep(0.05)
            with open(tmp_path, 'w') as f:
                json.dump({
                    "builder_pool": {"primary": "a", "secondary": "b", "support": []},
                    "task_routing": {"test": ["a", "c"]},
                    "fallback_rules": {}
                }, f)

            # Force mtime change (some filesystems have 1s resolution)
            new_mtime = bp._policy_mtime + 1
            os.utime(tmp_path, (new_mtime, new_mtime))

            result = bp.check_reload()
            assert result is True
            assert bp._task_routing == {"test": ["a", "c"]}
        finally:
            os.unlink(tmp_path)


class TestLoadBalancing:
    def test_get_builder_returns_agent(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        builder = bp.get_builder("code_task")
        # Should return one of the agents in the routing table
        assert builder is not None

    def test_get_builder_with_exclude(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        builder1 = bp.get_builder("code_task")
        if builder1:
            builder2 = bp.get_builder("code_task", exclude={builder1})
            # Should return a different agent or None
            assert builder2 != builder1 or builder2 is None

    def test_compute_agent_score(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        score = bp._compute_agent_score("claude_cowork")
        assert isinstance(score, float)
        assert score > 0

    def test_busy_agent_gets_lower_score(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        score_available = bp._compute_agent_score("test_agent_a")
        bp.report_capacity("test_agent_b", "busy")
        score_busy = bp._compute_agent_score("test_agent_b")
        assert score_busy < score_available

    def test_report_task_assigned_and_completed(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        assert bp._active_task_count.get("agent_x", 0) == 0
        bp.report_task_assigned("agent_x")
        assert bp._active_task_count["agent_x"] == 1
        bp.report_task_assigned("agent_x")
        assert bp._active_task_count["agent_x"] == 2
        bp.report_task_completed("agent_x")
        assert bp._active_task_count["agent_x"] == 1
        bp.report_task_completed("agent_x")
        assert bp._active_task_count["agent_x"] == 0
        # Should not go below 0
        bp.report_task_completed("agent_x")
        assert bp._active_task_count["agent_x"] == 0

    def test_gemma4_local_in_routing(self):
        from simp.routing.builder_pool import BuilderPool
        bp = BuilderPool()
        routing = bp._task_routing
        assert "gemma4_local" in routing.get("research", [])
        assert "gemma4_local" in routing.get("planning", [])
        assert "gemma4_local" in routing.get("code_task", [])


class TestCircuitBreaker:
    def test_broker_has_circuit_breaker(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        assert hasattr(broker, '_circuit_failures')
        assert hasattr(broker, '_is_circuit_open')

    def test_circuit_initially_closed(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        assert broker._is_circuit_open("nonexistent_agent") is False

    def test_circuit_opens_after_failures(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        for i in range(5):
            broker._record_circuit_failure("flaky_agent")
        assert broker._is_circuit_open("flaky_agent") is True

    def test_circuit_stays_closed_under_threshold(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        for i in range(4):
            broker._record_circuit_failure("almost_flaky")
        assert broker._is_circuit_open("almost_flaky") is False

    def test_circuit_success_resets(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        for i in range(5):
            broker._record_circuit_failure("recovered_agent")
        assert broker._is_circuit_open("recovered_agent") is True
        broker._record_circuit_success("recovered_agent")
        assert broker._is_circuit_open("recovered_agent") is False

    def test_deliver_with_retry_exists(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        assert hasattr(broker, '_deliver_with_retry')
        assert callable(broker._deliver_with_retry)


class TestPriorityDispatch:
    def test_get_queue_sorted_by_priority(self):
        from simp.task_ledger import TaskLedger
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            tmp_path = f.name
        try:
            tl = TaskLedger(ledger_path=tmp_path)
            tl.create_task(title="Low task", task_type="implementation", priority="low")
            tl.create_task(title="Critical task", task_type="implementation", priority="critical")
            tl.create_task(title="High task", task_type="implementation", priority="high")
            tl.create_task(title="Medium task", task_type="implementation", priority="medium")
            queue = tl.get_queue()
            priorities = [t.get("priority", "medium") for t in queue]
            assert priorities[0] == "critical"
            assert priorities[1] == "high"
            assert priorities[2] == "medium"
            assert priorities[3] == "low"
        finally:
            os.unlink(tmp_path)

    def test_critical_before_low(self):
        from simp.task_ledger import TaskLedger
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            tmp_path = f.name
        try:
            tl = TaskLedger(ledger_path=tmp_path)
            tl.create_task(title="Low first", task_type="implementation", priority="low")
            tl.create_task(title="Critical second", task_type="implementation", priority="critical")
            queue = tl.get_queue()
            assert queue[0]["priority"] == "critical"
            assert queue[1]["priority"] == "low"
        finally:
            os.unlink(tmp_path)


class TestModulesCompile:
    def test_builder_pool_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "routing", "builder_pool.py"),
            doraise=True
        )

    def test_broker_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "server", "broker.py"),
            doraise=True
        )

    def test_orchestration_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "orchestration", "orchestration_loop.py"),
            doraise=True
        )

    def test_task_ledger_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "simp", "task_ledger.py"),
            doraise=True
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
