"""
SIMP A2A Capability Mapping — Sprint 2

Maps SIMP agent capabilities to A2A AgentSkill declarations.
"""

from typing import Dict, List, Any, Optional


# ---------------------------------------------------------------------------
# Well-known SIMP capability → A2A skill mapping
# ---------------------------------------------------------------------------

_CAPABILITY_MAP: Dict[str, Dict[str, Any]] = {
    "planning": {
        "id": "planning",
        "name": "Task Planning",
        "description": "Break down goals into structured execution plans.",
    },
    "research": {
        "id": "research",
        "name": "Research & Analysis",
        "description": "Investigate topics and produce structured findings.",
    },
    "code_task": {
        "id": "code_task",
        "name": "Code Task",
        "description": "Read, write, or refactor code artifacts.",
    },
    "status_check": {
        "id": "status_check",
        "name": "Status Check",
        "description": "Return current operational or task status.",
    },
    "capability_query": {
        "id": "capability_query",
        "name": "Capability Query",
        "description": "List available capabilities of an agent.",
    },
    "ping": {
        "id": "ping",
        "name": "Ping / Heartbeat",
        "description": "Simple availability probe.",
    },
    "native_agent_health_check": {
        "id": "maintenance.health_check",
        "name": "Health Check",
        "description": "Run a lightweight health probe on the target system.",
    },
    "native_agent_task_audit": {
        "id": "maintenance.audit",
        "name": "Task Audit",
        "description": "Audit recent task history for anomalies.",
    },
    "native_agent_security_audit": {
        "id": "maintenance.security_audit",
        "name": "Security Audit",
        "description": "Scan for common security misconfigurations.",
    },
    "native_agent_repo_scan": {
        "id": "maintenance.repo_scan",
        "name": "Repository Scan",
        "description": "Scan repository for code-health issues.",
    },
    "native_agent_code_maintenance": {
        "id": "maintenance.code_maintenance",
        "name": "Code Maintenance",
        "description": "Apply safe, automated code maintenance patches.",
    },
    "native_agent_provider_repair": {
        "id": "maintenance.provider_repair",
        "name": "Provider Repair",
        "description": "Attempt automated repair of a failed provider.",
    },
    "projectx_query": {
        "id": "projectx_query",
        "name": "ProjectX Query",
        "description": "Query the ProjectX management system.",
    },
    "small_purchase": {
        "id": "financial.small_purchase",
        "name": "Small Purchase (Simulated)",
        "description": "Simulate a small purchase operation.",
    },
    "subscription_management": {
        "id": "financial.subscription_management",
        "name": "Subscription Management (Simulated)",
        "description": "Simulate subscription lifecycle management.",
    },
    "license_renewal": {
        "id": "financial.license_renewal",
        "name": "License Renewal (Simulated)",
        "description": "Simulate license renewal operation.",
    },
}


def capabilities_to_skills(capabilities: Optional[List[str]]) -> List[Dict[str, Any]]:
    """
    Convert a list of SIMP capability strings to A2A AgentSkill dicts.

    Unknown capabilities are passed through with minimal metadata.
    """
    if not capabilities:
        return []
    skills: List[Dict[str, Any]] = []
    seen: set = set()
    for cap in capabilities:
        if cap in seen:
            continue
        seen.add(cap)
        if cap in _CAPABILITY_MAP:
            skills.append(dict(_CAPABILITY_MAP[cap]))
        else:
            skills.append({
                "id": cap,
                "name": cap.replace("_", " ").title(),
                "description": f"SIMP capability: {cap}",
            })
    return skills


def get_capability_map() -> Dict[str, Dict[str, Any]]:
    """Return a copy of the full capability map."""
    return dict(_CAPABILITY_MAP)
