"""
SIMP Routing Engine — Sprint 53

Policy-based intent routing: explicit target → policy primary → fallback chain
→ capability match → None.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SIMP.RoutingEngine")

# ---------------------------------------------------------------------------
# Default policy path
# ---------------------------------------------------------------------------

_DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "routing_policy.json"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RoutingPolicy:
    """A single routing rule for an intent type."""
    intent_type: str
    primary_agent: str = ""
    fallback_chain: List[str] = field(default_factory=list)
    required_capability: str = ""
    description: str = ""


@dataclass
class RoutingDecision:
    """Result of a routing resolution."""
    target_agent: Optional[str]
    reason: str  # explicit, policy_primary, fallback, capability_match, no_route
    intent_type: str = ""
    policy_matched: bool = False


# ---------------------------------------------------------------------------
# RoutingEngine
# ---------------------------------------------------------------------------

class RoutingEngine:
    """
    Resolves which agent should receive an intent.

    Resolution order:
    1. **explicit** — caller provided a target_agent (non-empty, non-"auto")
    2. **policy primary** — routing_policy.json maps intent_type → primary_agent
    3. **fallback chain** — iterate policy fallbacks, pick first registered
    4. **capability match** — scan registered agents for required_capability
    5. **None** — no route found
    """

    def __init__(self, policy_path: Optional[str] = None):
        self._policy_path = Path(policy_path) if policy_path else _DEFAULT_POLICY_PATH
        self._policies: Dict[str, RoutingPolicy] = {}
        self.load_policy()

    # ------------------------------------------------------------------
    # policy loading
    # ------------------------------------------------------------------

    def load_policy(self) -> None:
        """Load routing policy from JSON file."""
        self._policies = {}
        if not self._policy_path.exists():
            logger.warning("Routing policy file not found: %s", self._policy_path)
            return
        try:
            with open(self._policy_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            rules = data if isinstance(data, list) else data.get("rules", [])
            for entry in rules:
                it = entry.get("intent_type", "")
                if not it:
                    continue
                self._policies[it] = RoutingPolicy(
                    intent_type=it,
                    primary_agent=entry.get("primary_agent", ""),
                    fallback_chain=entry.get("fallback_chain", []),
                    required_capability=entry.get("required_capability", ""),
                    description=entry.get("description", ""),
                )
            logger.info("Loaded %d routing rules from %s", len(self._policies), self._policy_path)
        except Exception as exc:
            logger.error("Failed to load routing policy: %s", exc)

    def reload_policy(self) -> int:
        """Reload policy from disk.  Returns number of rules loaded."""
        self.load_policy()
        return len(self._policies)

    # ------------------------------------------------------------------
    # resolve
    # ------------------------------------------------------------------

    def resolve(
        self,
        intent_type: str,
        explicit_target: Optional[str],
        registered_agents: Dict[str, Dict[str, Any]],
    ) -> RoutingDecision:
        """
        Determine which agent should handle the intent.
        """
        # 1. Explicit target
        if explicit_target and explicit_target != "auto":
            return RoutingDecision(
                target_agent=explicit_target,
                reason="explicit",
                intent_type=intent_type,
                policy_matched=False,
            )

        policy = self._policies.get(intent_type)

        # 2. Policy primary
        if policy and policy.primary_agent:
            if policy.primary_agent in registered_agents:
                return RoutingDecision(
                    target_agent=policy.primary_agent,
                    reason="policy_primary",
                    intent_type=intent_type,
                    policy_matched=True,
                )

        # 3. Fallback chain
        if policy and policy.fallback_chain:
            for fallback in policy.fallback_chain:
                if fallback in registered_agents:
                    return RoutingDecision(
                        target_agent=fallback,
                        reason="fallback",
                        intent_type=intent_type,
                        policy_matched=True,
                    )

        # 4. Capability match
        req_cap = policy.required_capability if policy else ""
        if req_cap:
            for agent_id, agent_info in registered_agents.items():
                caps = agent_info.get("metadata", {}).get("capabilities", [])
                if req_cap in caps:
                    return RoutingDecision(
                        target_agent=agent_id,
                        reason="capability_match",
                        intent_type=intent_type,
                        policy_matched=True,
                    )

        # 5. No route
        return RoutingDecision(
            target_agent=None,
            reason="no_route",
            intent_type=intent_type,
            policy_matched=False,
        )

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------

    def get_policy_summary(self) -> Dict[str, Any]:
        """Return a JSON-serialisable summary of all loaded policies."""
        rules = []
        for p in self._policies.values():
            rules.append({
                "intent_type": p.intent_type,
                "primary_agent": p.primary_agent,
                "fallback_chain": p.fallback_chain,
                "required_capability": p.required_capability,
                "description": p.description,
            })
        return {
            "rule_count": len(rules),
            "policy_path": str(self._policy_path),
            "rules": rules,
        }
