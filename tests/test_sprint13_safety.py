"""Tests for Sprint 13: Logging, safety gate, and abort."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.projectx.computer import (
    ProjectXComputer,
    TaskAbortError,
    ACTION_TIERS,
)


class TestLogAction:
    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_log_creates_jsonl_file(self, pc):
        pc.log_action({"action": "click", "params": {}}, {"success": True})
        assert pc._action_log_path.exists()

    def test_log_appends_valid_json(self, pc):
        pc.log_action({"action": "click"}, {"success": True})
        pc.log_action({"action": "type_text"}, {"success": False, "error": "fail"})
        lines = pc._action_log_path.read_text().strip().split("\n")
        assert len(lines) == 2
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        assert entry1["action_index"] == 1
        assert entry2["action_index"] == 2

    def test_log_has_timestamp(self, pc):
        pc.log_action({"action": "test"}, {"success": True})
        line = json.loads(pc._action_log_path.read_text().strip())
        assert "timestamp" in line
        assert "T" in line["timestamp"]  # ISO format

    def test_log_includes_pre_post_state_summaries(self, pc):
        result = {
            "success": True,
            "pre_state": {
                "active_window": "Finder",
                "timestamp": "2026-01-01T00:00:00",
                "screen_resolution": (1920, 1080),
                "ocr_text": [{"text": "hello"}],
            },
            "post_state": {
                "active_window": "Terminal",
                "timestamp": "2026-01-01T00:00:01",
                "screen_resolution": (1920, 1080),
                "ocr_text": [],
            },
        }
        pc.log_action({"action": "click"}, result)
        entry = json.loads(pc._action_log_path.read_text().strip())
        assert entry["pre_state"]["active_window"] == "Finder"
        assert entry["pre_state"]["ocr_summary"] == 1
        assert entry["post_state"]["active_window"] == "Terminal"
        assert entry["post_state"]["ocr_summary"] == 0


class TestSafeExecute:
    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_rejects_unknown_action(self, pc):
        r = pc.safe_execute({"action": "hack_mainframe", "params": {}})
        assert r["success"] is False
        assert "Unknown action" in r["error"]

    def test_rejects_above_max_tier(self, pc):
        pc_restricted = ProjectXComputer(
            log_dir=str(pc.log_dir / "restricted"), max_tier=0
        )
        r = pc_restricted.safe_execute({"action": "click", "params": {"x": 1, "y": 1}})
        assert r["success"] is False
        assert "tier" in r["error"].lower()

    def test_executes_tier0_action(self, pc):
        r = pc.safe_execute({"action": "get_active_window", "params": {}})
        assert r["success"] is True
        assert isinstance(r["data"], str)

    def test_executes_shell_action(self, pc):
        r = pc.safe_execute({"action": "run_shell", "params": {"command": "echo safe"}})
        assert r["success"] is True
        assert "safe" in r["data"]["stdout"]

    def test_logs_every_execution(self, pc):
        pc.safe_execute({"action": "run_shell", "params": {"command": "echo test"}})
        assert pc._action_log_path.exists()
        lines = pc._action_log_path.read_text().strip().split("\n")
        assert len(lines) >= 1

    def test_logs_failed_validations(self, pc):
        pc.safe_execute({"action": "nonexistent", "params": {}})
        lines = pc._action_log_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["result"]["success"] is False

    def test_returns_duration(self, pc):
        r = pc.safe_execute({"action": "run_shell", "params": {"command": "echo x"}})
        assert "duration_ms" in r
        assert r["duration_ms"] >= 0


class TestAbort:
    @pytest.fixture
    def pc(self, tmp_path):
        return ProjectXComputer(log_dir=str(tmp_path / "logs"))

    def test_abort_raises_error(self, pc):
        with pytest.raises(TaskAbortError, match="test reason"):
            pc.abort("test reason")

    def test_abort_logs_before_raising(self, pc):
        try:
            pc.abort("logged abort")
        except TaskAbortError:
            pass
        assert pc._action_log_path.exists()
        entry = json.loads(pc._action_log_path.read_text().strip())
        assert entry["action"]["action"] == "abort"
        assert "logged abort" in entry["action"]["params"]["reason"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
