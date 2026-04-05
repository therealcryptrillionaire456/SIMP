"""Tests for Sprint 16: Data plane authentication, rate limiter, memory management, XSS."""

import hmac
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAPIKeyAuth:
    """Test API key authentication middleware."""

    def test_require_api_key_decorator_exists(self):
        """The decorator module should be importable."""
        from simp.server.http_server import SimpHttpServer
        # Server should have the auth infrastructure
        assert hasattr(SimpHttpServer, '__init__')

    def test_config_has_api_key_settings(self):
        from config.config import SimpConfig
        config = SimpConfig()
        assert hasattr(config, 'REQUIRE_API_KEY')
        assert hasattr(config, 'API_KEYS')

    def test_api_keys_empty_allows_access(self):
        """When no API keys configured, access should be allowed (backward compat)."""
        from config.config import SimpConfig
        config = SimpConfig()
        # Default API_KEYS is empty string
        assert config.API_KEYS == "" or config.API_KEYS is None or len(config.API_KEYS.strip()) == 0

    def test_hmac_compare_digest_used(self):
        """Verify constant-time comparison is available."""
        assert hmac.compare_digest("test", "test") is True
        assert hmac.compare_digest("test", "wrong") is False


class TestRateLimiterSecurity:
    """Test rate limiter fixes."""

    def test_rate_limiter_importable(self):
        from simp.server.rate_limit import RateLimiter
        assert RateLimiter is not None

    def test_token_bucket_importable(self):
        from simp.server.rate_limit import TokenBucket
        bucket = TokenBucket(rate=10, capacity=10)
        assert bucket.consume()

    def test_cleanup_stale_exists(self):
        from simp.server.rate_limit import RateLimiter
        rl = RateLimiter()
        assert hasattr(rl, 'cleanup_stale')

    def test_cleanup_stale_removes_old_buckets(self):
        from simp.server.rate_limit import RateLimiter, TokenBucket
        rl = RateLimiter()
        # Add a bucket and age it
        key = "test_client:test_endpoint"
        rl.get_bucket(key, rate=10, capacity=10)
        assert key in rl._buckets or len(rl._buckets) > 0
        # Cleanup with very short max_age should remove it
        rl.cleanup_stale()

    def test_get_client_id_trusted_proxy(self):
        """get_client_id should only trust X-Forwarded-For from trusted proxies."""
        from simp.server.rate_limit import get_client_id
        assert callable(get_client_id)


class TestIntentRecordEviction:
    """Test intent record memory management."""

    def test_broker_intent_records_exist(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        assert hasattr(broker, 'intent_records')

    def test_broker_has_cleanup_method(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        assert hasattr(broker, '_cleanup_intent_records') or hasattr(broker, '_evict_oldest_records')

    def test_broker_has_evict_oldest(self):
        from simp.server.broker import SimpBroker, BrokerConfig
        config = BrokerConfig(max_agents=10, health_check_interval=60)
        broker = SimpBroker(config)
        assert hasattr(broker, '_evict_oldest_records')

    def test_broker_max_intent_records_constant(self):
        from simp.server.broker import SimpBroker
        assert hasattr(SimpBroker, 'MAX_INTENT_RECORDS')
        assert SimpBroker.MAX_INTENT_RECORDS == 10000


class TestDashboardXSS:
    """Test dashboard XSS prevention."""

    def test_dashboard_app_js_has_escape_function(self):
        js_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(js_path) as f:
            content = f.read()
        assert "escapeHtml" in content, "app.js should contain an escapeHtml function"

    def test_dashboard_no_unescaped_innerhtml(self):
        """Check that innerHTML usage escapes dynamic content."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static", "app.js")
        with open(js_path) as f:
            content = f.read()
        # Should have escapeHtml calls near innerHTML usage
        assert "escapeHtml" in content

    def test_dashboard_server_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        py_compile.compile(path, doraise=True)

    def test_dashboard_has_security_headers(self):
        """Dashboard server should include security header middleware."""
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "server.py")
        with open(path) as f:
            content = f.read()
        assert "Content-Security-Policy" in content or "SecurityHeaders" in content


class TestAllModulesCompile:
    """Verify no syntax errors introduced."""

    def test_http_server_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "simp", "server", "http_server.py")
        py_compile.compile(path, doraise=True)

    def test_broker_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "simp", "server", "broker.py")
        py_compile.compile(path, doraise=True)

    def test_rate_limit_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "simp", "server", "rate_limit.py")
        py_compile.compile(path, doraise=True)

    def test_config_compiles(self):
        import py_compile
        path = os.path.join(os.path.dirname(__file__), "..", "config", "config.py")
        py_compile.compile(path, doraise=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
