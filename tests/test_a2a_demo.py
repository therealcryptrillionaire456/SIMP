"""
SIMP A2A Demo — Sprint S9 (Sprint 39) tests.
"""

import os
import py_compile
import pytest


class TestDemoCompiles:
    def test_a2a_demo_compiles(self):
        path = os.path.join(os.path.dirname(__file__), "..", "examples", "a2a_demo.py")
        py_compile.compile(path, doraise=True)


class TestDemoClient:
    def test_class_has_required_methods(self):
        from examples.a2a_demo import A2ADemoClient
        client = A2ADemoClient("http://127.0.0.1:9999")
        assert hasattr(client, "discover")
        assert hasattr(client, "submit_planning_task")
        assert hasattr(client, "run_maintenance_check")
        assert hasattr(client, "simulate_financial_op")
        assert hasattr(client, "fetch_events")

    def test_run_demo_raises_connection_error(self):
        from examples.a2a_demo import run_demo
        with pytest.raises(ConnectionError):
            run_demo("http://127.0.0.1:9999", "test-key")


class TestDemoDocs:
    def test_a2a_demo_md_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "A2A_DEMO.md")
        assert os.path.exists(path)

    def test_a2a_demo_md_sections(self):
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "A2A_DEMO.md")
        with open(path) as f:
            content = f.read()
        assert "Overview" in content
        assert "Prerequisites" in content
        assert "Running the Demo" in content
        assert "Flow Diagram" in content
        assert "Security Posture" in content
        assert "Architecture" in content
        assert "adapter surface" in content.lower() or "A2A is an adapter" in content
