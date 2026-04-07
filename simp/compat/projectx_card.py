"""
SIMP ProjectX A2A Agent Card — Sprint S2 (Sprint 32)

Builds a standalone A2A-compatible Agent Card specifically for the
ProjectX native maintenance agent.
"""

from typing import Dict, Any, List

from simp.compat.policy_map import (
    get_agent_policy,
    get_agent_security_schemes,
    get_agent_security_requirements,
)
from simp.compat.a2a_security import build_a2a_security_schemes_block


# ---------------------------------------------------------------------------
# ProjectX skill definitions (read-only maintenance only)
# ---------------------------------------------------------------------------

_PROJECTX_SKILLS: List[Dict[str, Any]] = [
    {
        "id": "maintenance.health_check",
        "name": "Health Check",
        "description": "Run a lightweight health probe on the target system.",
    },
    {
        "id": "maintenance.audit",
        "name": "Task Audit",
        "description": "Audit recent task history for anomalies.",
    },
    {
        "id": "maintenance.security_audit",
        "name": "Security Audit",
        "description": "Scan for common security misconfigurations.",
    },
    {
        "id": "maintenance.repo_scan",
        "name": "Repository Scan",
        "description": "Scan repository for code-health issues.",
    },
]

# Skill IDs allowed for task submission (read-only only)
ALLOWED_SKILL_IDS = {s["id"] for s in _PROJECTX_SKILLS}

# Skill ID → SIMP intent type
SKILL_TO_INTENT: Dict[str, str] = {
    "maintenance.health_check": "native_agent_health_check",
    "maintenance.audit": "native_agent_task_audit",
    "maintenance.security_audit": "native_agent_security_audit",
    "maintenance.repo_scan": "native_agent_repo_scan",
}

# Write skills that must NEVER be accepted
_WRITE_SKILLS = {"maintenance.code_maintenance", "maintenance.provider_repair"}


def build_projectx_a2a_card(broker_base_url: str = "http://127.0.0.1:5555") -> Dict[str, Any]:
    """
    Build an A2A-compatible Agent Card for the ProjectX native agent.

    Never includes file paths or secrets.
    """
    base = broker_base_url.rstrip("/")
    agent_stub = {"agent_type": "projectx_native"}
    policy = get_agent_policy(agent_stub)

    # Build securitySchemes block (filtered to projectx)
    all_schemes = build_a2a_security_schemes_block()

    return {
        "name": "SIMP ProjectX Native Agent",
        "description": "Native maintenance and audit agent for SIMP and ProjectX infrastructure.",
        "version": "1.0",
        "url": f"{base}/a2a/agents/projectx",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": list(_PROJECTX_SKILLS),
        "securitySchemes": all_schemes,
        "security": get_agent_security_requirements(agent_stub),
        "safetyPolicies": policy.get("safetyPolicies", {}),
        "resourceLimits": policy.get("resourceLimits", {}),
        "x-simp": {
            "agent_type": "projectx_native",
            "environment": "development",
            "protocol": "simp/1.0",
        },
    }


def validate_projectx_task(payload: Dict[str, Any]) -> tuple:
    """
    Validate a ProjectX A2A task request.

    Returns (True, skill_id, intent_type) or (False, error_msg, None).
    """
    skill_id = payload.get("skill_id", "")

    if skill_id in _WRITE_SKILLS:
        return False, f"Write operation '{skill_id}' is not allowed via A2A", None

    if skill_id not in ALLOWED_SKILL_IDS:
        return False, f"Unknown or disallowed skill_id: {skill_id}", None

    intent_type = SKILL_TO_INTENT.get(skill_id)
    return True, skill_id, intent_type
