"""
SIMP A2A Policy-Rich Cards — Sprint S1 (Sprint 31) tests.
"""

import pytest
from simp.compat.policy_map import (
    get_agent_policy,
    get_agent_security_schemes,
    get_agent_security_requirements,
    AGENT_SAFETY_POLICIES,
    AGENT_SECURITY_SCHEMES,
)
from simp.compat.agent_card import AgentCardGenerator


class TestPolicyMap:
    def test_projectx_policy(self):
        p = get_agent_policy({"agent_type": "projectx_native"})
        assert p["safetyPolicies"]["readOnlyByDefault"] is True
        assert p["safetyPolicies"]["allowShell"] is False

    def test_financial_ops_policy(self):
        p = get_agent_policy({"agent_type": "financial_ops"})
        assert p["safetyPolicies"]["requiresManualApproval"] is True
        assert p["resourceLimits"]["mode"] == "simulate_only"

    def test_kashclaw_policy(self):
        p = get_agent_policy({"agent_type": "kashclaw_gemma"})
        assert p["safetyPolicies"]["readOnlyMode"] is True

    def test_default_policy(self):
        p = get_agent_policy({"agent_type": "unknown_thing"})
        assert "safetyPolicies" in p

    def test_no_file_paths_in_policy(self):
        for at in ("projectx_native", "financial_ops", "kashclaw_gemma", "__default__"):
            p = AGENT_SAFETY_POLICIES[at]
            raw = str(p)
            assert "boundedScanRoots" not in raw
            assert "/Users/" not in raw
            assert "/home/" not in raw

    def test_no_secrets_in_policy(self):
        for at in AGENT_SAFETY_POLICIES:
            raw = str(AGENT_SAFETY_POLICIES[at])
            assert "sk-" not in raw
            assert "password" not in raw.lower()

    def test_security_schemes_projectx(self):
        s = get_agent_security_schemes({"agent_type": "projectx_native"})
        assert "api_key" in s
        assert "oauth2" in s
        assert "mtls" in s

    def test_security_schemes_financial(self):
        s = get_agent_security_schemes({"agent_type": "financial_ops"})
        assert "oauth2" in s
        assert "mtls" in s

    def test_security_requirements_projectx(self):
        r = get_agent_security_requirements({"agent_type": "projectx_native"})
        assert len(r) >= 1
        assert r[0]["scheme"] == "oauth2"
        assert "maintenance.read" in r[0]["scopes"]


class TestPolicyRichCards:
    @pytest.fixture
    def gen(self):
        return AgentCardGenerator("http://test:5555")

    def test_projectx_card_has_security(self, gen):
        card = gen.build_agent_card({
            "agent_id": "px:001",
            "agent_type": "projectx_native",
            "endpoint": "http://localhost:6000",
        })
        assert "securitySchemes" in card
        assert "security" in card
        assert "safetyPolicies" in card
        assert "resourceLimits" in card

    def test_financial_ops_simulate_note(self, gen):
        card = gen.build_agent_card({
            "agent_id": "fin:001",
            "agent_type": "financial_ops",
            "endpoint": "http://localhost:7000",
        })
        assert "SIMULATED" in card["description"]
        assert card["x-simp"]["status"] == "planned"

    def test_card_no_file_paths(self, gen):
        card = gen.build_agent_card({
            "agent_id": "px:001",
            "agent_type": "projectx_native",
            "endpoint": "http://localhost:6000",
        })
        raw = str(card)
        assert "boundedScanRoots" not in raw
        assert "/Users/" not in raw

    def test_required_a2a_fields(self, gen):
        card = gen.build_agent_card({
            "agent_id": "px:001",
            "agent_type": "projectx_native",
            "endpoint": "http://localhost:6000",
        })
        assert "name" in card
        assert "version" in card
        assert "url" in card
        assert "capabilities" in card
        assert "skills" in card
