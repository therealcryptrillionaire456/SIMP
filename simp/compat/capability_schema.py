"""
SIMP Structured Capability Schema — Sprint 3

Provides a StructuredCapability dataclass with A2A AgentSkill alignment,
normalisation from various input formats, and well-known capability enrichment.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union


# ---------------------------------------------------------------------------
# Well-known capability enrichment registry
# ---------------------------------------------------------------------------

_WELL_KNOWN: Dict[str, Dict[str, str]] = {
    "planning": {"name": "Task Planning", "description": "Break down goals into structured execution plans."},
    "research": {"name": "Research & Analysis", "description": "Investigate topics and produce structured findings."},
    "code_task": {"name": "Code Task", "description": "Read, write, or refactor code artifacts."},
    "status_check": {"name": "Status Check", "description": "Return current operational or task status."},
    "capability_query": {"name": "Capability Query", "description": "List available capabilities of an agent."},
    "ping": {"name": "Ping / Heartbeat", "description": "Simple availability probe."},
    "native_agent_health_check": {"name": "Health Check", "description": "Run a lightweight health probe on the target system."},
    "native_agent_task_audit": {"name": "Task Audit", "description": "Audit recent task history for anomalies."},
    "native_agent_security_audit": {"name": "Security Audit", "description": "Scan for common security misconfigurations."},
    "native_agent_repo_scan": {"name": "Repository Scan", "description": "Scan repository for code-health issues."},
    "native_agent_code_maintenance": {"name": "Code Maintenance", "description": "Apply safe, automated code maintenance patches."},
    "native_agent_provider_repair": {"name": "Provider Repair", "description": "Attempt automated repair of a failed provider."},
    "projectx_query": {"name": "ProjectX Query", "description": "Query the ProjectX management system."},
    "small_purchase": {"name": "Small Purchase (Simulated)", "description": "Simulate a small purchase operation."},
    "subscription_management": {"name": "Subscription Management (Simulated)", "description": "Simulate subscription lifecycle management."},
    "license_renewal": {"name": "License Renewal (Simulated)", "description": "Simulate license renewal operation."},
    "trade": {"name": "Trade Execution", "description": "Execute a trading operation."},
    "validate_trade": {"name": "Trade Validation", "description": "Validate trade parameters without executing."},
}


@dataclass
class StructuredCapability:
    """A single structured capability aligned with A2A AgentSkill."""

    id: str
    name: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Enrich from well-known registry if name/description missing
        if self.id in _WELL_KNOWN:
            wk = _WELL_KNOWN[self.id]
            if not self.name:
                self.name = wk["name"]
            if not self.description:
                self.description = wk["description"]
        if not self.name:
            self.name = self.id.replace("_", " ").title()
        if not self.description:
            self.description = f"SIMP capability: {self.id}"

    def to_a2a_skill(self) -> Dict[str, Any]:
        """Convert to A2A AgentSkill dict."""
        skill: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
        if self.tags:
            skill["tags"] = list(self.tags)
        if self.examples:
            skill["examples"] = list(self.examples)
        return skill

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredCapability":
        """Create from a dict (round-trip friendly)."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            tags=list(data.get("tags", [])),
            examples=list(data.get("examples", [])),
        )


def normalise_capabilities(
    raw: Optional[Union[str, List[Any]]]
) -> List[StructuredCapability]:
    """
    Accept various capability input formats and return a deduplicated list
    of StructuredCapability instances.

    Accepts: None, [], "a,b,c", ["a","b"], [{"id":"a","name":"A"}], or mixed.
    """
    if raw is None or raw == []:
        return []

    items: List[Any] = []
    if isinstance(raw, str):
        items = [s.strip() for s in raw.split(",") if s.strip()]
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    result: List[StructuredCapability] = []
    seen: set = set()

    for item in items:
        if isinstance(item, str):
            if item not in seen:
                seen.add(item)
                result.append(StructuredCapability(id=item))
        elif isinstance(item, dict):
            cap_id = item.get("id", "")
            if cap_id and cap_id not in seen:
                seen.add(cap_id)
                result.append(StructuredCapability.from_dict(item))
        # skip other types silently

    return result


def capabilities_to_a2a_skills(
    raw: Optional[Union[str, List[Any]]]
) -> List[Dict[str, Any]]:
    """Convenience: normalise then convert to A2A skill dicts."""
    return [cap.to_a2a_skill() for cap in normalise_capabilities(raw)]
