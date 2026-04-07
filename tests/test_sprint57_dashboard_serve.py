"""Sprint 57 — Dashboard served on broker port (5555) tests.

Verifies /dashboard, /dashboard/ui, and /dashboard/static/* routes on the
Flask broker HTTP server.
"""

import os
import pytest
from simp.server.http_server import SimpHttpServer
from simp.server.dashboard_ui import build_dashboard_html, get_dashboard_js, get_dashboard_css


@pytest.fixture()
def client():
    os.environ["SIMP_REQUIRE_API_KEY"] = "false"
    server = SimpHttpServer(debug=False)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


class TestDashboardUI:
    """Tests for build_dashboard_html / JS / CSS helpers."""

    def test_build_dashboard_html_contains_broker_url(self):
        html = build_dashboard_html("http://127.0.0.1:5555")
        assert "window.SIMP_BROKER_URL" in html
        assert "http://127.0.0.1:5555" in html

    def test_build_dashboard_html_is_valid(self):
        html = build_dashboard_html()
        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_get_dashboard_js_returns_string(self):
        js = get_dashboard_js()
        assert isinstance(js, str)
        assert len(js) > 0

    def test_get_dashboard_css_returns_string(self):
        css = get_dashboard_css()
        assert isinstance(css, str)
        assert len(css) > 0


class TestDashboardRoutes:
    """Tests for /dashboard and /dashboard/ui Flask routes."""

    def test_dashboard_returns_html(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"text/html" in resp.content_type.encode()

    def test_dashboard_ui_returns_html(self, client):
        resp = client.get("/dashboard/ui")
        assert resp.status_code == 200
        assert b"SIMP" in resp.data

    def test_dashboard_static_js(self, client):
        resp = client.get("/dashboard/static/app.js")
        assert resp.status_code == 200
        assert "javascript" in resp.content_type

    def test_dashboard_static_css(self, client):
        resp = client.get("/dashboard/static/style.css")
        assert resp.status_code == 200
        assert "css" in resp.content_type

    def test_dashboard_html_injects_broker_url(self, client):
        resp = client.get("/dashboard")
        assert b"SIMP_BROKER_URL" in resp.data

    def test_health_still_works(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
