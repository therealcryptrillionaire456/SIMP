"""
SIMP Agent Policy Map — Sprint S1 (Sprint 31)

Hardcoded, safe-to-export safety policy and security scheme declarations
per agent_type.  No secrets, no file paths in any output.
"""

from typing import Dict, List, Any


# ---------------------------------------------------------------------------
# Safety policies per agent type (NO file paths, NO secrets)
# ---------------------------------------------------------------------------

AGENT_SAFETY_POLICIES: Dict[str, Dict[str, Any]] = {
    "projectx_native": {
        "safetyPolicies": {
            "readOnlyByDefault": True,
            "allowShell": False,
            "allowFileWrites": False,
        },
        "resourceLimits": {
            "maxConcurrentJobs": 2,
            "maxScanDurationSeconds": 900,
            "maxScanFrequencySeconds": 1800,
        },
    },
    "financial_ops": {
        "safetyPolicies": {
            "requiresManualApproval": True,
            "manualApprovalThreshold": 0.00,
            "readOnlyMode": True,
            "noCredentialStorage": True,
            "sandboxMode": True,
        },
        "resourceLimits": {
            "maxSpendPerTask": 20.00,
            "maxSpendPerDay": 50.00,
            "maxSpendPerMonth": 200.00,
            "maxVendors": 5,
            "currency": "USD",
            "mode": "simulate_only",
        },
    },
    "kashclaw_gemma": {
        "safetyPolicies": {
            "readOnlyMode": True,
            "noDirectFileAccess": True,
            "noNetworkOutsideBroker": True,
        },
        "resourceLimits": {
            "maxConcurrentPlans": 3,
            "maxStepsPerPlan": 10,
        },
    },
    "__default__": {
        "safetyPolicies": {},
        "resourceLimits": {},
    },
}

# ---------------------------------------------------------------------------
# Security scheme names per agent type
# ---------------------------------------------------------------------------

AGENT_SECURITY_SCHEMES: Dict[str, List[str]] = {
    "projectx_native": ["api_key", "oauth2", "mtls"],
    "financial_ops": ["oauth2", "mtls"],
    "kashclaw_gemma": ["api_key", "oauth2"],
    "__default__": ["api_key"],
}

# ---------------------------------------------------------------------------
# Security requirements per agent type
# ---------------------------------------------------------------------------

AGENT_SECURITY_REQUIREMENTS: Dict[str, List[Dict[str, Any]]] = {
    "projectx_native": [
        {"scheme": "oauth2", "scopes": ["maintenance.read", "maintenance.execute"]},
    ],
    "financial_ops": [
        {"scheme": "oauth2", "scopes": ["payments.simulate", "payments.execute.small"]},
    ],
    "kashclaw_gemma": [
        {"scheme": "oauth2", "scopes": ["agents.read", "plan.write"]},
    ],
    "__default__": [],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _agent_type_from(agent: Dict[str, Any]) -> str:
    return agent.get("agent_type") or agent.get("type", "__default__")


def get_agent_policy(agent: Dict[str, Any]) -> Dict[str, Any]:
    """Return the safety policy block for *agent*'s type.  No file paths."""
    at = _agent_type_from(agent)
    return dict(AGENT_SAFETY_POLICIES.get(at, AGENT_SAFETY_POLICIES["__default__"]))


def get_agent_security_schemes(agent: Dict[str, Any]) -> List[str]:
    """Return security scheme names for *agent*'s type."""
    at = _agent_type_from(agent)
    return list(AGENT_SECURITY_SCHEMES.get(at, AGENT_SECURITY_SCHEMES["__default__"]))


def get_agent_security_requirements(agent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return security requirements for *agent*'s type."""
    at = _agent_type_from(agent)
    return [dict(r) for r in AGENT_SECURITY_REQUIREMENTS.get(at, AGENT_SECURITY_REQUIREMENTS["__default__"])]
