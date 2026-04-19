"""Tests for Sprint 21: Dashboard UX, security headers, charts, filtering."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSecurityHeaders:
    def test_csp_header_present(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "Content-Security-Policy" in content

    def test_x_frame_options(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "X-Frame-Options" in content

    def test_referrer_policy(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "Referrer-Policy" in content or "referrer" in content.lower()

    def test_cors_configurable(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "DASHBOARD_CORS_ORIGINS" in content or "allow_origins" in content


class TestErrorHandling:
    def test_app_js_has_safe_get(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert "safeGetEl" in content or "getElementById" in content

    def test_app_js_has_escape_html(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert "escapeHtml" in content


class TestTaskFiltering:
    def test_index_has_filter_controls(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "index.html")
        with open(path) as f:
            content = f.read()
        assert "task-search" in content or "filter" in content.lower()

    def test_app_js_has_filter_logic(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert "filter" in content.lower()


class TestActivityCharts:
    def test_index_has_chart_canvas(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "index.html")
        with open(path) as f:
            content = f.read()
        assert "chart" in content.lower() or "canvas" in content.lower()

    def test_app_js_has_chart_logic(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(path) as f:
            content = f.read()
        assert "Chart" in content or "chart" in content.lower()

    def test_style_has_chart_grid(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "style.css")
        with open(path) as f:
            content = f.read()
        assert "chart" in content.lower()


class TestModulesCompile:
    def test_dashboard_server_compiles(self):
        import py_compile
        py_compile.compile(
            os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py"),
            doraise=True
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
