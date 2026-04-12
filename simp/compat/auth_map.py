"""
SIMP A2A Authentication Mapping — Sprint 1

Maps SIMP authentication mechanisms to A2A-compatible security scheme
declarations.  These are *declarative* — they describe what SIMP supports,
not enforce it at this layer.
"""

from typing import Dict, List, Any


# ---------------------------------------------------------------------------
# Scheme declarations (no actual secrets — only metadata)
# ---------------------------------------------------------------------------

_SECURITY_SCHEMES: Dict[str, Dict[str, Any]] = {
    "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": (
            "Static API key for internal agents and low-privilege A2A calls."
        ),
    },
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "OAuth2/OIDC bearer token for user- or tenant-scoped A2A calls. "
            "Required claims: sub, aud, scope, exp."
        ),
    },
    "MutualTLS": {
        "type": "mutualTLS",
        "description": (
            "Mutual TLS for high-trust agent-to-agent channels. "
            "Enforced at gateway layer. "
            "Required for projectx_native and financial_ops."
        ),
    },
}

# Per-agent-type recommended scopes
_RECOMMENDED_SCOPES: Dict[str, List[str]] = {
    "projectx_native": ["maintenance.read", "maintenance.execute"],
    "financial_ops": ["payments.simulate", "payments.execute.small"],
    "kashclaw_gemma": ["agents.read", "plan.write"],
    "__default__": ["agents.read"],
}


def build_security_schemes() -> Dict[str, Dict[str, Any]]:
    """Return A2A-compatible securitySchemes block (no secrets)."""
    return dict(_SECURITY_SCHEMES)


def get_recommended_scopes_for_agent(agent_type: str) -> List[str]:
    """Return recommended OAuth2 scopes for a given agent type."""
    return list(_RECOMMENDED_SCOPES.get(agent_type, _RECOMMENDED_SCOPES["__default__"]))


def map_simp_auth_to_a2a(agent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return an A2A-compatible ``authentication`` block for *agent*.

    Looks up the agent's ``agent_type`` (or ``type``), then returns the
    matching security scheme declarations plus a ``security`` requirements
    array.
    """
    agent_type = agent.get("agent_type") or agent.get("type", "unknown")
    schemes = build_security_schemes()
    scopes = get_recommended_scopes_for_agent(agent_type)
    return {
        "securitySchemes": schemes,
        "security": [{"scheme": "oauth2", "scopes": scopes}],
    }
