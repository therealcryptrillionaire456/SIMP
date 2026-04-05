"""Tests for Sprint 11: ProjectX skeleton and observation layer."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.projectx.computer import (
    ProjectXComputer,
    TaskAbortError,
    ACTION_TIERS,
    DEFAULT_MAX_TIER,
)


class TestProjectXSkeleton:
    def test_class_importable(self):
        pc = ProjectXComputer()
        assert pc is not None

    def test_init_defaults(self, tmp_path):
        pc = ProjectXComputer(log_dir=str(tmp_path / "logs"))
        assert pc.max_tier == DEFAULT_MAX_TIER
        assert pc.log_dir.exists()

    def test_action_tiers_complete(self):
        """All 14 methods should have tier assignments."""
        expected = {
            "get_screenshot", "get_active_window", "ocr_screen", "snapshot_state",
            "click", "double_click", "type_text", "press", "scroll", "focus_app",
            "run_shell", "log_action", "safe_execute", "abort",
        }
        assert set(ACTION_TIERS.keys()) == expected

    def test_tier_values(self):
        assert ACTION_TIERS["get_screenshot"] == 0
        assert ACTION_TIERS["click"] == 1
        assert ACTION_TIERS["run_shell"] == 2

    def test_task_abort_error(self):
        with pytest.raises(TaskAbortError, match="test reason"):
            raise TaskAbortError("test reason")


class TestObservationMethods:
    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_get_screenshot_returns_bytes(self, pc):
        result = pc.get_screenshot()
        assert isinstance(result, bytes)
        # Should be valid PNG (starts with PNG signature)
        assert result[:4] == b"\x89PNG"

    def test_get_active_window_returns_string(self, pc):
        result = pc.get_active_window()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ocr_screen_returns_list(self, pc):
        result = pc.ocr_screen()
        assert isinstance(result, list)

    def test_snapshot_state_structure(self, pc):
        state = pc.snapshot_state()
        assert "screenshot" in state
        assert "active_window" in state
        assert "ocr_text" in state
        assert "timestamp" in state
        assert "screen_resolution" in state
        assert isinstance(state["screenshot"], bytes)
        assert isinstance(state["active_window"], str)
        assert isinstance(state["ocr_text"], list)
        assert isinstance(state["screen_resolution"], tuple)

    def test_fallback_png_valid(self, pc):
        png = pc._fallback_png()
        assert png[:4] == b"\x89PNG"
        assert len(png) > 20


class TestStubsRaiseCorrectly:
    """Sprint 12-13 methods should raise NotImplementedError with sprint info."""

    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_click_implemented(self, pc):
        r = pc.click(0, 0)
        assert isinstance(r, dict) and "success" in r

    def test_type_text_implemented(self, pc):
        r = pc.type_text("test")
        assert isinstance(r, dict) and "success" in r

    def test_run_shell_implemented(self, pc):
        r = pc.run_shell("echo hi")
        assert isinstance(r, dict) and "success" in r

    def test_safe_execute_implemented(self, pc):
        r = pc.safe_execute({"action": "get_active_window", "params": {}})
        assert isinstance(r, dict) and "success" in r

    def test_abort_implemented(self, pc):
        with pytest.raises(TaskAbortError):
            pc.abort("test")

    def test_log_action_implemented(self, pc):
        pc.log_action({}, {"success": True})
        assert pc._action_log_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
