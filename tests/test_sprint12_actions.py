"""Tests for Sprint 12: GUI actions and shell execution."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.projectx.computer import ProjectXComputer


class TestResultFormat:
    """All action methods should return the standard result dict."""

    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_make_result_success(self, pc):
        import time
        start = time.time()
        r = pc._make_result(True, data={"x": 1}, start_time=start)
        assert r["success"] is True
        assert r["data"] == {"x": 1}
        assert r["error"] is None
        assert isinstance(r["duration_ms"], int)

    def test_make_result_failure(self, pc):
        r = pc._make_result(False, error="boom")
        assert r["success"] is False
        assert r["error"] == "boom"


class TestGUIActions:
    """GUI actions should return result dicts (may fail gracefully in CI)."""

    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_click_returns_result(self, pc):
        r = pc.click(100, 200)
        assert isinstance(r, dict)
        assert "success" in r
        assert "duration_ms" in r

    def test_click_with_button(self, pc):
        r = pc.click(50, 50, button="right")
        assert isinstance(r, dict)

    def test_double_click_returns_result(self, pc):
        r = pc.double_click(100, 200)
        assert isinstance(r, dict)
        assert "success" in r

    def test_type_text_returns_result(self, pc):
        r = pc.type_text("hello")
        assert isinstance(r, dict)
        assert "success" in r

    def test_press_single_key(self, pc):
        r = pc.press("enter")
        assert isinstance(r, dict)

    def test_press_combo(self, pc):
        r = pc.press("command+c")
        assert isinstance(r, dict)

    def test_scroll_returns_result(self, pc):
        r = pc.scroll(0, 3)
        assert isinstance(r, dict)

    def test_focus_app_returns_result(self, pc):
        r = pc.focus_app("Finder")
        assert isinstance(r, dict)
        assert "success" in r


class TestShellExecution:
    """Shell execution should work in any environment."""

    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_run_shell_echo(self, pc):
        r = pc.run_shell("echo hello")
        assert r["success"] is True
        assert "hello" in r["data"]["stdout"]
        assert r["data"]["return_code"] == 0

    def test_run_shell_failure(self, pc):
        r = pc.run_shell("exit 1")
        assert r["success"] is False
        assert r["data"]["return_code"] == 1

    def test_run_shell_timeout(self, pc):
        r = pc.run_shell("sleep 10", timeout=1)
        assert r["success"] is False
        assert "timed out" in r["error"]

    def test_run_shell_captures_stderr(self, pc):
        r = pc.run_shell("echo err >&2")
        assert "err" in r["data"]["stderr"]

    def test_run_shell_returns_duration(self, pc):
        r = pc.run_shell("echo fast")
        assert r["duration_ms"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
