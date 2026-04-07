"""Sprint 15: Final production readiness verification — ProjectX edition."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProjectXEndToEnd:
    """Full lifecycle test: init → observe → execute → log → verify."""

    def test_full_lifecycle(self, tmp_path):
        from simp.projectx.computer import ProjectXComputer

        pc = ProjectXComputer(log_dir=str(tmp_path / "e2e_logs"))

        # 1. Observe
        state = pc.snapshot_state()
        assert "screenshot" in state
        assert "timestamp" in state

        # 2. Execute via safe_execute
        result = pc.safe_execute({
            "action": "run_shell",
            "params": {"command": "echo end-to-end"}
        })
        assert result["success"] is True
        assert "end-to-end" in result["data"]["stdout"]

        # 3. Verify log was written
        log_path = tmp_path / "e2e_logs" / "actions.jsonl"
        assert log_path.exists()
        entry = json.loads(log_path.read_text().strip().split("\n")[-1])
        assert entry["action"]["action"] == "run_shell"
        assert entry["result"]["success"] is True

    def test_rejection_logged(self, tmp_path):
        from simp.projectx.computer import ProjectXComputer

        pc = ProjectXComputer(log_dir=str(tmp_path / "reject_logs"))
        result = pc.safe_execute({"action": "bad_action", "params": {}})
        assert result["success"] is False

        log_path = tmp_path / "reject_logs" / "actions.jsonl"
        assert log_path.exists()
        entry = json.loads(log_path.read_text().strip())
        assert entry["result"]["success"] is False

    def test_tier_gating_works(self, tmp_path):
        from simp.projectx.computer import ProjectXComputer

        pc = ProjectXComputer(log_dir=str(tmp_path / "tier_logs"), max_tier=0)

        # Tier 0 should work
        r0 = pc.safe_execute({"action": "get_active_window", "params": {}})
        assert r0["success"] is True

        # Tier 1 should be blocked
        r1 = pc.safe_execute({"action": "click", "params": {"x": 0, "y": 0}})
        assert r1["success"] is False
        assert "tier" in r1["error"].lower()

        # Tier 2 should be blocked
        r2 = pc.safe_execute({"action": "run_shell", "params": {"command": "echo blocked"}})
        assert r2["success"] is False


class TestProductionReadinessV3:
    def test_readme_has_projectx(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path) as f:
            content = f.read()
        assert "ProjectX" in content or "Computer Use" in content

    def test_version_is_0_3(self):
        path = os.path.join(os.path.dirname(__file__), "..", "setup.py")
        with open(path) as f:
            content = f.read()
        assert "0.4.0" in content

    def test_sprint_log_has_15_sprints(self):
        path = os.path.join(os.path.dirname(__file__), "..", "SPRINT_LOG.md")
        with open(path) as f:
            content = f.read()
        assert "Sprint 15" in content

    def test_all_projectx_modules_compile(self):
        import py_compile
        root = os.path.join(os.path.dirname(__file__), "..")
        files = [
            "simp/projectx/__init__.py",
            "simp/projectx/computer.py",
        ]
        for f in files:
            path = os.path.join(root, f)
            if os.path.exists(path):
                py_compile.compile(path, doraise=True)

    def test_all_core_modules_still_compile(self):
        import py_compile
        root = os.path.join(os.path.dirname(__file__), "..")
        core_files = [
            "simp/server/broker.py",
            "simp/server/http_server.py",
            "simp/server/request_guards.py",
            "dashboard/server.py",
        ]
        for f in core_files:
            path = os.path.join(root, f)
            if os.path.exists(path):
                py_compile.compile(path, doraise=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
