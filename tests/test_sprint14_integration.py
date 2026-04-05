"""Tests for Sprint 14: ProjectX SIMP integration."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.server.broker import SimpBroker, BrokerConfig
from simp.projectx.computer import ProjectXComputer, ACTION_TIERS


class TestBrokerProjectXIntegration:
    @pytest.fixture
    def broker(self, tmp_path):
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        return SimpBroker(config)

    def test_broker_has_projectx_attribute(self, broker):
        assert hasattr(broker, "_projectx")
        assert broker.projectx is None  # Not initialized yet

    def test_init_projectx(self, broker, tmp_path):
        broker.init_projectx(log_dir=str(tmp_path / "px_logs"))
        assert broker.projectx is not None
        assert isinstance(broker.projectx, ProjectXComputer)

    def test_projectx_logged_on_init(self, broker, tmp_path):
        broker.start()
        broker.init_projectx(log_dir=str(tmp_path / "px_logs"))
        logs = broker.get_logs(10)
        events = [e["event_type"] for e in logs]
        assert "projectx_initialized" in events
        broker.stop()

    def test_projectx_safe_execute_via_broker(self, broker, tmp_path):
        broker.init_projectx(log_dir=str(tmp_path / "px_logs"))
        result = broker.projectx.safe_execute({
            "action": "run_shell",
            "params": {"command": "echo integration"}
        })
        assert result["success"] is True
        assert "integration" in result["data"]["stdout"]

    def test_broker_rejects_unknown_action_via_projectx(self, broker, tmp_path):
        broker.init_projectx(log_dir=str(tmp_path / "px_logs"))
        result = broker.projectx.safe_execute({
            "action": "destroy_everything",
            "params": {}
        })
        assert result["success"] is False
        assert "Unknown action" in result["error"]


class TestComputerUseIntentType:
    def test_action_tiers_importable(self):
        assert "get_screenshot" in ACTION_TIERS
        assert "run_shell" in ACTION_TIERS

    def test_all_tiers_assigned(self):
        for action, tier in ACTION_TIERS.items():
            assert isinstance(tier, int)
            assert tier >= -1 and tier <= 3


class TestDashboardEndpoint:
    def test_dashboard_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        py_compile.compile(path, doraise=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
