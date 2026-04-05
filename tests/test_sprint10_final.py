"""Sprint 10: Final production readiness verification."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProductionReadiness:
    def test_readme_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        assert os.path.exists(path)

    def test_readme_has_architecture(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path) as f:
            content = f.read()
        assert "Architecture" in content
        assert "Quickstart" in content
        assert "Test Suites" in content

    def test_sprint_log_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "SPRINT_LOG.md")
        assert os.path.exists(path)

    def test_sprint_log_has_10_sprints(self):
        path = os.path.join(os.path.dirname(__file__), "..", "SPRINT_LOG.md")
        with open(path) as f:
            content = f.read()
        assert "Sprint 10" in content

    def test_all_core_modules_compile(self):
        import py_compile
        root = os.path.join(os.path.dirname(__file__), "..")
        core_files = [
            "simp/server/broker.py",
            "simp/server/http_server.py",
            "simp/server/request_guards.py",
            "simp/server/rate_limit.py",
            "simp/server/control_auth.py",
            "simp/server/validation.py",
            "simp/task_ledger.py",
            "simp/memory/hooks.py",
            "simp/orchestration/orchestration_loop.py",
            "dashboard/server.py",
        ]
        for f in core_files:
            path = os.path.join(root, f)
            if os.path.exists(path):
                py_compile.compile(path, doraise=True)

    def test_version_is_current(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "setup.py")) as f:
            content = f.read()
        assert '0.3.0' in content

    def test_no_dead_scaffolds(self):
        """No dead scaffold files should remain."""
        root = os.path.join(os.path.dirname(__file__), "..")
        dead = [
            "simp/security/input_validator.py",
            "simp/security/rate_limiter.py",
        ]
        for f in dead:
            assert not os.path.exists(os.path.join(root, f)), f"Dead scaffold: {f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
