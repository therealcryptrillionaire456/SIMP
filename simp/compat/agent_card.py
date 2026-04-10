"""
SIMP A2A Agent Card Generator — Sprints 1-6, S1

Generates A2A-compatible Agent Card JSON for SIMP agents and the broker.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from simp.compat.auth_map import build_security_schemes, map_simp_auth_to_a2a
from simp.compat.capability_map import capabilities_to_skills

_SIMP_VERSION = "0.7.0"

# File-based agent endpoints that are NOT HTTP-reachable
_FILE_BASED_ENDPOINTS = {"(file-based)"}


class AgentCardGenerator:
    """
    Builds A2A-compatible Agent Card JSON for individual SIMP agents
    and for the SIMP broker itself.
    """

    def __init__(self, broker_base_url: str = "http://127.0.0.1:5555"):
        self.broker_base_url = broker_base_url.rstrip("/")
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = 60  # seconds

    # ------------------------------------------------------------------
    # Agent card
    # ------------------------------------------------------------------

    def build_agent_card(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build an A2A Agent Card for a single registered SIMP agent.

        Skips file-based agents (endpoint == "(file-based)").
        """
        from simp.compat.policy_map import (
            get_agent_policy,
            get_agent_security_schemes,
            get_agent_security_requirements,
        )

        agent_id = agent.get("agent_id", "unknown")
        agent_type = agent.get("agent_type") or agent.get("type", "unknown")
        endpoint = agent.get("endpoint", "")

        if endpoint in _FILE_BASED_ENDPOINTS:
            return {}

        caps = agent.get("capabilities") or agent.get("metadata", {}).get("capabilities", [])
        if isinstance(caps, str):
            caps = [c.strip() for c in caps.split(",") if c.strip()]

        skills = capabilities_to_skills(caps)

        # Policy enrichment (Sprint S1)
        policy = get_agent_policy(agent)
        scheme_names = get_agent_security_schemes(agent)
        security_reqs = get_agent_security_requirements(agent)

        # Build securitySchemes dict filtered to relevant schemes
        all_schemes = build_security_schemes()
        # Map scheme names to A2A scheme keys
        _name_to_key = {"api_key": "ApiKeyAuth", "oauth2": "BearerAuth", "mtls": "MutualTLS"}
        filtered_schemes = {}
        for name in scheme_names:
            key = _name_to_key.get(name)
            if key and key in all_schemes:
                filtered_schemes[key] = all_schemes[key]

        card: Dict[str, Any] = {
            "name": agent_id,
            "description": f"SIMP agent: {agent_type}",
            "version": _SIMP_VERSION,
            "url": f"{self.broker_base_url}/agents/{agent_id}",
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
            },
            "skills": skills,
            "securitySchemes": filtered_schemes,
            "security": security_reqs,
            "safetyPolicies": policy.get("safetyPolicies", {}),
            "resourceLimits": policy.get("resourceLimits", {}),
            "x-simp": {
                "agent_type": agent_type,
                "protocol": "simp/1.0",
                "version": _SIMP_VERSION,
                "environment": "development",
            },
        }

        # Financial ops annotation
        if agent_type == "financial_ops":
            card["x-simp"]["status"] = "planned"
            card["x-simp"]["mode"] = "simulate_only"
            card["description"] += " [SIMULATED ONLY — status: planned]"

        return card

    # ------------------------------------------------------------------
    # Broker card (well-known)
    # ------------------------------------------------------------------

    def build_broker_card(
        self,
        agent_registry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the broker-level /.well-known/agent-card.json."""
        child_cards: List[Dict[str, Any]] = []
        if agent_registry:
            for _aid, info in agent_registry.items():
                card = self.build_agent_card(info)
                if card:
                    child_cards.append(card)

        return {
            "name": "SIMP Broker",
            "description": "Structured Intent Messaging Protocol — multi-agent broker.",
            "version": _SIMP_VERSION,
            "url": self.broker_base_url,
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": True,
            },
            "skills": [],
            "securitySchemes": build_security_schemes(),
            "agents": child_cards,
            "x-simp": {
                "protocol": "simp/1.0",
                "version": _SIMP_VERSION,
                "environment": "development",
                "transportSecurity": {
                    "tls_versions": ["TLSv1.2", "TLSv1.3"],
                    "local_http_allowed": True,
                    "note": "All A2A-facing endpoints must be exposed via HTTPS/TLS in production.",
                },
                "autonomousOperationsPolicy": {
                    "default_mode": "recommendation_only",
                },
            },
        }

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def invalidate_agent(self, agent_id: str) -> None:
        self._cache.pop(agent_id, None)
        self._cache_ts.pop(agent_id, None)

    def cache_stats(self) -> Dict[str, Any]:
        return {"entries": len(self._cache), "ttl_seconds": self._cache_ttl}
