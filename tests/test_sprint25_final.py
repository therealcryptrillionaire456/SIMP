"""Sprint 25: Final verification — protocol versioning, documentation, v0.4.0 release."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProtocolVersioning:
    def test_broker_stats_include_version(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        broker.start()
        stats = broker.get_statistics()
        broker.stop()
        assert isinstance(stats, dict)
        assert "protocol_versions" in stats
        assert "1.0" in stats["protocol_versions"]
        assert stats["simp_version"] == "0.4.0"

    def test_init_version_is_0_4(self):
        import simp
        assert hasattr(simp, '__version__')
        assert simp.__version__ == "0.4.0"

    def test_setup_version_is_0_4(self):
        path = os.path.join(os.path.dirname(__file__), "..", "setup.py")
        with open(path) as f:
            content = f.read()
        assert "0.4.0" in content

    def test_dashboard_version_is_1_4(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert '1.4.1' in content

    def test_agent_registration_stores_simp_versions(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        broker.start()
        broker.register_agent("test_v", "test", "http://localhost:9999",
                              metadata={"simp_versions": ["1.0"]})
        agent = broker.agents.get("test_v", {})
        broker.stop()
        assert agent.get("simp_versions") == ["1.0"]


class TestProtocolSpec:
    def test_protocol_spec_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "PROTOCOL_SPEC.md")
        assert os.path.exists(path)

    def test_protocol_spec_has_sections(self):
        path = os.path.join(os.path.dirname(__file__), "..", "PROTOCOL_SPEC.md")
        with open(path) as f:
            content = f.read()
        assert "Intent" in content
        assert "Agent" in content
        assert "Routing" in content
        assert "Security" in content

    def test_protocol_spec_substantial(self):
        path = os.path.join(os.path.dirname(__file__), "..", "PROTOCOL_SPEC.md")
        with open(path) as f:
            content = f.read()
        assert len(content) > 2000  # At least 2KB

    def test_protocol_spec_has_intent_types(self):
        path = os.path.join(os.path.dirname(__file__), "..", "PROTOCOL_SPEC.md")
        with open(path) as f:
            content = f.read()
        assert "code_task" in content
        assert "research" in content
        assert "orchestration" in content

    def test_protocol_spec_has_error_taxonomy(self):
        path = os.path.join(os.path.dirname(__file__), "..", "PROTOCOL_SPEC.md")
        with open(path) as f:
            content = f.read()
        assert "rate_limited" in content
        assert "schema_invalid" in content
        assert "agent_unavailable" in content


class TestREADME:
    def test_readme_has_quickstart(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path) as f:
            content = f.read()
        assert "quickstart" in content.lower() or "getting started" in content.lower() or "quick start" in content.lower()

    def test_readme_has_projectx(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path) as f:
            content = f.read()
        assert "ProjectX" in content

    def test_readme_has_sprint_25(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path) as f:
            content = f.read()
        assert "25" in content

    def test_readme_has_architecture(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path) as f:
            content = f.read()
        assert "Architecture" in content or "architecture" in content

    def test_readme_has_api_reference(self):
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(path) as f:
            content = f.read()
        assert "API" in content


class TestSprintLog:
    def test_sprint_log_has_25_sprints(self):
        path = os.path.join(os.path.dirname(__file__), "..", "SPRINT_LOG.md")
        with open(path) as f:
            content = f.read()
        assert "Sprint 25" in content
        assert "COMPLETE" in content

    def test_sprint_log_has_all_phases(self):
        path = os.path.join(os.path.dirname(__file__), "..", "SPRINT_LOG.md")
        with open(path) as f:
            content = f.read()
        assert "25-Sprint Plan: COMPLETE" in content


class TestAllModulesCompile:
    def test_all_core_modules(self):
        import py_compile
        root = os.path.join(os.path.dirname(__file__), "..")
        modules = [
            "simp/__init__.py",
            "simp/server/broker.py",
            "simp/server/http_server.py",
            "simp/server/request_guards.py",
            "simp/server/rate_limit.py",
            "simp/server/control_auth.py",
            "simp/models/canonical_intent.py",
            "simp/projectx/computer.py",
            "simp/agents/gemma4_agent.py",
            "simp/agents/kloutbot_agent.py",
            "simp/agents/q_intent_compiler.py",
            "simp/memory/knowledge_index.py",
            "simp/routing/builder_pool.py",
            "simp/orchestration/orchestration_loop.py",
            "simp/task_ledger.py",
            "dashboard/server.py",
        ]
        for mod in modules:
            path = os.path.join(root, mod)
            if os.path.exists(path):
                py_compile.compile(path, doraise=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
