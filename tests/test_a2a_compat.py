"""
SIMP A2A Compatibility — Sprint 1 tests.

Tests for auth_map, capability_map, and agent_card (Sprint 1 core).
"""

import pytest
from simp.compat.auth_map import (
    build_security_schemes,
    get_recommended_scopes_for_agent,
    map_simp_auth_to_a2a,
)
from simp.compat.capability_map import capabilities_to_skills, get_capability_map
from simp.compat.agent_card import AgentCardGenerator


# ---------------------------------------------------------------------------
# auth_map
# ---------------------------------------------------------------------------

class TestAuthMap:
    def test_build_security_schemes_keys(self):
        s = build_security_schemes()
        assert "ApiKeyAuth" in s
        assert "BearerAuth" in s
        assert "MutualTLS" in s

    def test_no_secrets_in_schemes(self):
        s = build_security_schemes()
        raw = str(s)
        assert "sk-" not in raw
        assert "Bearer " not in raw

    def test_recommended_scopes_projectx(self):
        scopes = get_recommended_scopes_for_agent("projectx_native")
        assert "maintenance.read" in scopes

    def test_recommended_scopes_default(self):
        scopes = get_recommended_scopes_for_agent("unknown_type")
        assert "agents.read" in scopes

    def test_map_simp_auth_to_a2a(self):
        result = map_simp_auth_to_a2a({"agent_type": "projectx_native"})
        assert "securitySchemes" in result
        assert "security" in result


# ---------------------------------------------------------------------------
# capability_map
# ---------------------------------------------------------------------------

class TestCapabilityMap:
    def test_known_capability(self):
        skills = capabilities_to_skills(["planning"])
        assert len(skills) == 1
        assert skills[0]["id"] == "planning"

    def test_unknown_capability(self):
        skills = capabilities_to_skills(["zyx_custom"])
        assert len(skills) == 1
        assert skills[0]["id"] == "zyx_custom"

    def test_empty_capabilities(self):
        assert capabilities_to_skills(None) == []
        assert capabilities_to_skills([]) == []

    def test_dedup(self):
        skills = capabilities_to_skills(["ping", "ping"])
        assert len(skills) == 1

    def test_get_capability_map(self):
        m = get_capability_map()
        assert "planning" in m


# ---------------------------------------------------------------------------
# agent_card
# ---------------------------------------------------------------------------

class TestAgentCard:
    @pytest.fixture
    def gen(self):
        return AgentCardGenerator("http://test:5555")

    def test_build_agent_card_basic(self, gen):
        card = gen.build_agent_card({
            "agent_id": "test:001",
            "agent_type": "projectx_native",
            "endpoint": "http://localhost:6000",
        })
        assert card["name"] == "test:001"
        assert "securitySchemes" in card
        assert "security" in card
        assert "safetyPolicies" in card

    def test_file_based_agent_excluded(self, gen):
        card = gen.build_agent_card({
            "agent_id": "kb:001",
            "agent_type": "kashclaw_gemma",
            "endpoint": "(file-based)",
        })
        assert card == {}

    def test_broker_card(self, gen):
        card = gen.build_broker_card()
        assert card["name"] == "SIMP Broker"
        assert "securitySchemes" in card
        assert "x-simp" in card
        assert "transportSecurity" in card["x-simp"]

    def test_broker_card_with_agents(self, gen):
        registry = {
            "a1": {
                "agent_id": "a1",
                "agent_type": "projectx_native",
                "endpoint": "http://localhost:6000",
            },
        }
        card = gen.build_broker_card(registry)
        assert len(card["agents"]) == 1

    def test_financial_ops_card_annotation(self, gen):
        card = gen.build_agent_card({
            "agent_id": "fin:001",
            "agent_type": "financial_ops",
            "endpoint": "http://localhost:7000",
        })
        assert "planned" in card.get("x-simp", {}).get("status", "")
        assert "SIMULATED" in card.get("description", "")
