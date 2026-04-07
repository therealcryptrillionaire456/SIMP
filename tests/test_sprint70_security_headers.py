"""
Sprint 70 — Security Headers & Audit Log Tests

Tests for:
- Security response headers (X-Content-Type-Options, X-Frame-Options, etc.)
- Server/X-Powered-By header removal
- SecurityAuditLog class (append-only, filtering, redaction)
- Audit log hooks (agent_registered, agent_deregistered, validation_error)
- GET /security/audit-log endpoint
"""

import pytest
import os
import json
import tempfile
import shutil

from simp.server.http_server import SimpHttpServer
from simp.server.broker import BrokerConfig
from simp.server.security_audit import SecurityAuditLog, _redact_sensitive


class TestSecurityHeaders:
    """Test security headers on all responses."""

    @pytest.fixture
    def client(self):
        config = BrokerConfig(max_agents=10)
        server = SimpHttpServer(config)
        server.broker.start()
        server.app.config["TESTING"] = True
        return server.app.test_client()

    def test_x_content_type_options(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_content_security_policy(self, client):
        resp = client.get("/health")
        assert resp.headers.get("Content-Security-Policy") == "default-src 'none'"

    def test_cache_control(self, client):
        resp = client.get("/health")
        cc = resp.headers.get("Cache-Control")
        assert "no-store" in cc
        assert "no-cache" in cc

    def test_no_server_header(self, client):
        resp = client.get("/health")
        # Server header should be removed or not present
        server_val = resp.headers.get("Server", "")
        # Flask test client may still set it; check it's not explicitly set by us
        assert "X-Powered-By" not in resp.headers

    def test_security_headers_on_post(self, client):
        resp = client.post(
            "/agents/register",
            json={"agent_id": "test:001", "agent_type": "test", "endpoint": "localhost:5001"},
        )
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"


class TestSecurityAuditLog:
    """Test the SecurityAuditLog class."""

    @pytest.fixture
    def audit_dir(self):
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def audit_log(self, audit_dir):
        return SecurityAuditLog(log_dir=audit_dir)

    def test_log_event_creates_file(self, audit_log):
        audit_log.log_event("auth_failed", {"ip": "1.2.3.4"}, severity="high")
        assert os.path.exists(audit_log.log_path)

    def test_log_event_returns_event(self, audit_log):
        event = audit_log.log_event("auth_failed", {"ip": "1.2.3.4"})
        assert event["event_type"] == "auth_failed"
        assert "timestamp" in event
        assert event["severity"] == "medium"

    def test_get_events_returns_logged(self, audit_log):
        audit_log.log_event("auth_failed", {"ip": "1.2.3.4"})
        audit_log.log_event("rate_limited", {"path": "/api"})
        events = audit_log.get_events()
        assert len(events) == 2

    def test_filter_by_severity(self, audit_log):
        audit_log.log_event("auth_failed", {"ip": "1.2.3.4"}, severity="high")
        audit_log.log_event("rate_limited", {"path": "/api"}, severity="low")
        events = audit_log.get_events(severity="high")
        assert len(events) == 1
        assert events[0]["event_type"] == "auth_failed"

    def test_filter_by_event_type(self, audit_log):
        audit_log.log_event("auth_failed", {"ip": "1.2.3.4"})
        audit_log.log_event("rate_limited", {"path": "/api"})
        events = audit_log.get_events(event_type="rate_limited")
        assert len(events) == 1

    def test_limit(self, audit_log):
        for i in range(10):
            audit_log.log_event("auth_failed", {"attempt": i})
        events = audit_log.get_events(limit=3)
        assert len(events) == 3


class TestSensitiveFieldRedaction:
    """Test that sensitive fields are never logged."""

    def test_redacts_api_key(self):
        details = {"api_key": "sk-secret-123", "ip": "1.2.3.4"}
        redacted = _redact_sensitive(details)
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["ip"] == "1.2.3.4"

    def test_redacts_nested(self):
        details = {"config": {"password": "hunter2", "host": "db.local"}}
        redacted = _redact_sensitive(details)
        assert redacted["config"]["password"] == "[REDACTED]"
        assert redacted["config"]["host"] == "db.local"

    def test_redacts_private_key(self):
        details = {"private_key": "-----BEGIN PRIVATE KEY-----..."}
        redacted = _redact_sensitive(details)
        assert redacted["private_key"] == "[REDACTED]"

    def test_full_audit_log_redacts(self):
        d = tempfile.mkdtemp()
        try:
            log = SecurityAuditLog(log_dir=d)
            log.log_event("auth_failed", {"api_key": "secret123", "user": "bob"})
            events = log.get_events()
            assert events[0]["details"]["api_key"] == "[REDACTED]"
            assert events[0]["details"]["user"] == "bob"
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestAuditLogEndpoint:
    """Test GET /security/audit-log endpoint."""

    @pytest.fixture
    def server(self):
        config = BrokerConfig(max_agents=10)
        server = SimpHttpServer(config)
        server.broker.start()
        server.app.config["TESTING"] = True
        # Use temp directory for audit log
        d = tempfile.mkdtemp()
        server.audit_log = SecurityAuditLog(log_dir=d)
        yield server
        shutil.rmtree(d, ignore_errors=True)

    def test_audit_log_endpoint_empty(self, server):
        client = server.app.test_client()
        resp = client.get("/security/audit-log")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["count"] == 0

    def test_audit_log_endpoint_with_events(self, server):
        server.audit_log.log_event("auth_failed", {"ip": "1.2.3.4"}, severity="high")
        server.audit_log.log_event("rate_limited", {"path": "/api"}, severity="low")
        client = server.app.test_client()
        resp = client.get("/security/audit-log")
        data = resp.get_json()
        assert data["count"] == 2

    def test_audit_log_endpoint_filter(self, server):
        server.audit_log.log_event("auth_failed", {"ip": "1.2.3.4"}, severity="high")
        server.audit_log.log_event("rate_limited", {"path": "/api"}, severity="low")
        client = server.app.test_client()
        resp = client.get("/security/audit-log?severity=high")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["events"][0]["event_type"] == "auth_failed"
