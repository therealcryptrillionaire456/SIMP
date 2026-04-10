"""
SIMP A2A Security — Sprint S5 (Sprint 35) tests.
"""

import json
import os
import pytest

from simp.compat.a2a_security import (
    build_a2a_security_schemes_block,
    validate_bearer_claims,
    build_replay_guard_note,
    SUPPORTED_SCHEMES,
)
from simp.compat.auth_map import (
    build_security_schemes,
    get_recommended_scopes_for_agent,
)


class TestA2ASecuritySchemes:
    def test_has_three_schemes(self):
        s = build_a2a_security_schemes_block()
        assert "ApiKeyAuth" in s
        assert "BearerAuth" in s
        assert "MutualTLS" in s

    def test_no_key_values(self):
        s = build_a2a_security_schemes_block()
        raw = str(s)
        assert "sk-" not in raw
        assert "eyJ" not in raw  # no JWT tokens

    def test_api_key_type(self):
        s = build_a2a_security_schemes_block()
        assert s["ApiKeyAuth"]["type"] == "apiKey"

    def test_bearer_type(self):
        s = build_a2a_security_schemes_block()
        assert s["BearerAuth"]["scheme"] == "bearer"


class TestBearerClaims:
    def test_all_claims_present(self):
        ok, err = validate_bearer_claims({"sub": "user", "aud": "simp", "scope": "read", "exp": 9999})
        assert ok is True
        assert err is None

    def test_missing_sub(self):
        ok, err = validate_bearer_claims({"aud": "simp", "scope": "read", "exp": 9999})
        assert ok is False
        assert "sub" in err

    def test_missing_exp(self):
        ok, err = validate_bearer_claims({"sub": "user", "aud": "simp", "scope": "read"})
        assert ok is False
        assert "exp" in err

    def test_missing_all(self):
        ok, err = validate_bearer_claims({})
        assert ok is False


class TestReplayGuard:
    def test_status_planned(self):
        note = build_replay_guard_note()
        assert note["replay_protection"]["status"] == "planned"
        assert "nonces" in note["replay_protection"]["mechanisms"]


class TestSecurityRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_get_security_endpoint(self, client):
        resp = client.get("/a2a/security")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "securitySchemes" in data
        assert "replayProtection" in data
        assert "transportSecurity" in data

    def test_security_no_secrets(self, client):
        resp = client.get("/a2a/security")
        raw = resp.data.decode()
        assert "sk-" not in raw


class TestAuthMapBackwardCompat:
    def test_build_security_schemes_still_works(self):
        s = build_security_schemes()
        assert "ApiKeyAuth" in s

    def test_get_scopes_projectx(self):
        scopes = get_recommended_scopes_for_agent("projectx_native")
        assert "maintenance.read" in scopes

    def test_get_scopes_financial(self):
        scopes = get_recommended_scopes_for_agent("financial_ops")
        assert "payments.simulate" in scopes

    def test_get_scopes_kashclaw(self):
        scopes = get_recommended_scopes_for_agent("kashclaw_gemma")
        assert "agents.read" in scopes
