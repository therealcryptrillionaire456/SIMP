"""
SIMP BRP A2A Agent Card.

Mirrors the safe ProjectX A2A surface but for the defensive BRP subsystem.
All exposed skills are read-only / advisory and never grant autonomous write,
network takeover, self-replication, or self-modifying behavior.
"""

from typing import Any, Dict, List

from simp.compat.a2a_security import build_a2a_security_schemes_block
from simp.compat.policy_map import (
    get_agent_policy,
    get_agent_security_requirements,
)


_BRP_SKILLS: List[Dict[str, Any]] = [
    {
        "id": "defense.health_check",
        "name": "Defense Health Check",
        "description": "Return BRP runtime and defensive posture summary.",
    },
    {
        "id": "defense.threat_analysis",
        "name": "Threat Analysis",
        "description": "Analyze a supplied threat payload using BRP defensive logic.",
    },
    {
        "id": "defense.security_audit",
        "name": "Security Audit",
        "description": "Return a read-only BRP audit and incident summary.",
    },
    {
        "id": "defense.pattern_detection",
        "name": "Pattern Detection",
        "description": "Inspect supplied records for suspicious defensive patterns.",
    },
    {
        "id": "defense.quantum_posture",
        "name": "Quantum Defense Posture",
        "description": "Return advisory-only quantum backend and skill posture for BRP.",
    },
]

ALLOWED_BRP_SKILL_IDS = {item["id"] for item in _BRP_SKILLS}
BRP_SKILL_TO_INTENT: Dict[str, str] = {
    "defense.health_check": "ping",
    "defense.threat_analysis": "threat_analysis",
    "defense.security_audit": "security_audit",
    "defense.pattern_detection": "pattern_detection",
    "defense.quantum_posture": "security_audit",
}

_UNSAFE_SKILLS = {
    "defense.autonomous_takeover",
    "defense.self_modify",
    "defense.self_replicate",
    "defense.internet_full_access",
    "defense.hardware_design",
    "defense.training_loop",
}


def build_brp_a2a_card(broker_base_url: str = "http://127.0.0.1:5555") -> Dict[str, Any]:
    """Build a read-only BRP A2A card."""
    base = broker_base_url.rstrip("/")
    agent_stub = {"agent_type": "bill_russell_protocol"}
    policy = get_agent_policy(agent_stub)

    return {
        "name": "SIMP Bill Russell Protocol",
        "description": "Defensive supervision, incident analysis, and bounded quantum-assisted security posture for SIMP.",
        "version": "1.0",
        "url": f"{base}/a2a/agents/brp",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": list(_BRP_SKILLS),
        "securitySchemes": build_a2a_security_schemes_block(),
        "security": get_agent_security_requirements(agent_stub),
        "safetyPolicies": {
            **policy.get("safetyPolicies", {}),
            "readOnlyByDefault": True,
            "autonomousWritesAllowed": False,
            "realHardwareExecutionRequiresSeparateOptIn": True,
        },
        "resourceLimits": policy.get("resourceLimits", {}),
        "x-simp": {
            "agent_type": "bill_russell_protocol",
            "environment": "development",
            "protocol": "simp/1.0",
            "defensive_only": True,
        },
    }


def validate_brp_task(payload: Dict[str, Any]) -> tuple:
    """
    Validate a BRP A2A task request.

    Returns (True, skill_id, intent_type) or (False, error_msg, None).
    """
    skill_id = payload.get("skill_id", "")

    if skill_id in _UNSAFE_SKILLS:
        return False, f"Unsafe BRP skill '{skill_id}' is not allowed", None

    if skill_id not in ALLOWED_BRP_SKILL_IDS:
        return False, f"Unknown or disallowed BRP skill_id: {skill_id}", None

    return True, skill_id, BRP_SKILL_TO_INTENT.get(skill_id)
