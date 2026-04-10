"""Tests for Sprint 20: Dashboard WebSocket, live data, topology fix."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestWebSocketEndpoint:
    def test_dashboard_server_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        py_compile.compile(path, doraise=True)

    def test_dashboard_has_websocket_route(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "websocket" in content.lower(), "Dashboard should have WebSocket endpoint"

    def test_dashboard_has_broadcast_function(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "_broadcast_ws" in content


class TestLiveDataEndpoints:
    def test_health_endpoint_no_hardcoded_metadata(self):
        """Health endpoint should not contain hardcoded sprint counts."""
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "hardening_sprints_completed" not in content
        assert "security_findings_closed" not in content

    def test_orchestration_endpoint_queries_real_data(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "queue_depth" in content or "intents_routed" in content

    def test_computer_use_queries_broker(self):
        """Computer-use endpoint should query projectx info from broker."""
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "projectx_info" in content or 'stats.get("projectx"' in content


class TestFrontendWebSocket:
    def test_app_js_has_websocket(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert "WebSocket" in content or "websocket" in content.lower()

    def test_app_js_has_escape_html(self):
        """XSS protection from Sprint 16 still present."""
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert "escapeHtml" in content

    def test_app_js_has_connection_status(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert "ws-status" in content or "connectionStatus" in content.lower()

    def test_app_js_handles_stale_agent_status(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert '"stale"' in content


class TestTopologyFix:
    def test_topology_uses_connection_mode(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "connection_mode" in content

    def test_index_html_has_ws_indicator(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "index.html")
        with open(path) as f:
            content = f.read()
        assert "ws-status" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
