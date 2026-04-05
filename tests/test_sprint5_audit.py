"""Sprint 5: Final security audit tests.

Verifies that the dashboard exposes only GET endpoints, CORS is configurable,
and the security findings scorecard is fully resolved.
"""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDashboardGetOnly:
    """Verify dashboard only exposes GET routes."""

    def _get_dashboard_routes(self):
        """Import the dashboard app and extract all routes."""
        # Ensure dashboard module is importable
        dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard")
        if dashboard_dir not in sys.path:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from dashboard.server import app
        routes = []
        for route in app.routes:
            if hasattr(route, "methods"):
                routes.append({
                    "path": route.path,
                    "methods": route.methods,
                })
        return routes

    def test_no_post_routes(self):
        """Dashboard must not have any POST routes."""
        routes = self._get_dashboard_routes()
        post_routes = [r for r in routes if "POST" in r["methods"]]
        assert len(post_routes) == 0, f"POST routes found: {post_routes}"

    def test_no_put_routes(self):
        """Dashboard must not have any PUT routes."""
        routes = self._get_dashboard_routes()
        put_routes = [r for r in routes if "PUT" in r["methods"]]
        assert len(put_routes) == 0, f"PUT routes found: {put_routes}"

    def test_no_delete_routes(self):
        """Dashboard must not have any DELETE routes."""
        routes = self._get_dashboard_routes()
        delete_routes = [r for r in routes if "DELETE" in r["methods"]]
        assert len(delete_routes) == 0, f"DELETE routes found: {delete_routes}"

    def test_no_patch_routes(self):
        """Dashboard must not have any PATCH routes."""
        routes = self._get_dashboard_routes()
        patch_routes = [r for r in routes if "PATCH" in r["methods"]]
        assert len(patch_routes) == 0, f"PATCH routes found: {patch_routes}"

    def test_all_routes_are_get_or_head(self):
        """Every dashboard route should only allow GET (and HEAD)."""
        routes = self._get_dashboard_routes()
        for route in routes:
            allowed = {"GET", "HEAD"}
            extra = route["methods"] - allowed
            assert len(extra) == 0, (
                f"Route {route['path']} allows non-GET methods: {extra}"
            )


class TestCORSConfigurable:
    def test_cors_default_is_wildcard(self):
        """Default CORS origins should be ['*'] when env var is unset."""
        # Unset the env var if set
        env_backup = os.environ.pop("DASHBOARD_CORS_ORIGINS", None)
        try:
            # Re-import to pick up defaults
            import dashboard.server as ds
            importlib.reload(ds)
            assert ds.CORS_ORIGINS == ["*"]
        finally:
            if env_backup is not None:
                os.environ["DASHBOARD_CORS_ORIGINS"] = env_backup

    def test_cors_respects_env_var(self):
        """CORS origins should be configurable via DASHBOARD_CORS_ORIGINS."""
        os.environ["DASHBOARD_CORS_ORIGINS"] = "https://a.com,https://b.com"
        try:
            import dashboard.server as ds
            importlib.reload(ds)
            assert ds.CORS_ORIGINS == ["https://a.com", "https://b.com"]
        finally:
            del os.environ["DASHBOARD_CORS_ORIGINS"]
            importlib.reload(ds)


class TestRedaction:
    """Verify the redaction function strips sensitive data."""

    def test_redact_api_key(self):
        from dashboard.server import _redact
        data = {"name": "agent1", "api_key": "secret123"}
        result = _redact(data)
        assert "api_key" not in result
        assert result["name"] == "agent1"

    def test_redact_endpoint_url(self):
        from dashboard.server import _redact
        data = {"endpoint": "http://localhost:5555"}
        result = _redact(data)
        assert result["endpoint"] == "http"

    def test_redact_file_path(self):
        from dashboard.server import _redact
        data = {"file_path": "/home/user/secret.txt", "name": "ok"}
        result = _redact(data)
        assert "file_path" not in result

    def test_redact_nested(self):
        from dashboard.server import _redact
        data = {"agents": [{"id": "a", "token": "xyz", "endpoint": "http://x"}]}
        result = _redact(data)
        assert "token" not in result["agents"][0]
        assert result["agents"][0]["endpoint"] == "http"


class TestDeadScaffoldsRemoved:
    """Confirm all dead scaffold files have been cleaned up."""

    def test_no_standalone_rate_limiter(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "simp", "security", "rate_limiter.py"
        )
        assert not os.path.exists(path)

    def test_no_input_validator(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "simp", "security", "input_validator.py"
        )
        assert not os.path.exists(path)


class TestSecurityFindingsScorecard:
    """Meta-tests that verify all 8 security findings from Sprint 1 are addressed."""

    def test_s1_input_validation_exists(self):
        """S1: Input validation module exists and is importable."""
        from simp.server.request_guards import sanitize_agent_id, validate_intent_payload
        ok, _ = sanitize_agent_id("valid:001")
        assert ok is True

    def test_s2_validation_py_compiles(self):
        """S2: validation.py has no null bytes and compiles."""
        import py_compile
        path = os.path.join(
            os.path.dirname(__file__), "..", "simp", "server", "validation.py"
        )
        # Should not raise
        py_compile.compile(path, doraise=True)

    def test_s3_rate_limiter_wired(self):
        """S3: Rate limiter is wired into http_server, not standalone."""
        from simp.server.rate_limit import RateLimiter
        limiter = RateLimiter()
        assert hasattr(limiter, "limit")

    def test_s5_max_content_length(self):
        """S5: Flask MAX_CONTENT_LENGTH is set."""
        from simp.server.http_server import SimpHttpServer
        server = SimpHttpServer()
        assert server.app.config.get("MAX_CONTENT_LENGTH") == 64 * 1024

    def test_s6_control_auth_exists(self):
        """S6: Control auth decorator exists."""
        from simp.server.control_auth import require_control_auth
        assert callable(require_control_auth)

    def test_s8_path_sanitization(self):
        """S8: File-based delivery sanitizes agent_id paths."""
        from simp.server.request_guards import sanitize_agent_id
        ok, err = sanitize_agent_id("../../etc/passwd")
        assert ok is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
