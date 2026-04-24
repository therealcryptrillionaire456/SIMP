"""
SIMP BRP Enforcement Engine — Tranche 5

Broadens BRP enforcement from "restricted actions only" to policy-driven
deny/elevate rules with operator-configurable modes: shadow, advisory, enforced.

Enforcement decisions are logged to a JSONL audit log (append-only).
"""

from __future__ import annotations

import json
import os
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("SIMP.BRP.Enforcement")


# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)


def _ensure_data_dir() -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    return _DATA_DIR


# ---------------------------------------------------------------------------
# EnforcementMode
# ---------------------------------------------------------------------------

class EnforcementMode(str, Enum):
    """Operator-configurable enforcement mode."""

    SHADOW = "shadow"        # Log only, never block
    ADVISORY = "advisory"    # Log + notify, no block
    ENFORCED = "enforced"    # Block/elevate as configured


# ---------------------------------------------------------------------------
# EnforcementRule
# ---------------------------------------------------------------------------

@dataclass
class EnforcementRule:
    """A single enforcement rule keyed by attack_type."""

    attack_type: str
    mode: EnforcementMode
    min_confidence: float
    action: str                    # "deny", "elevate", or "log"
    reason_code: str               # e.g. "BRP-CODE-001"
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_type": self.attack_type,
            "mode": self.mode.value if isinstance(self.mode, EnforcementMode) else self.mode,
            "min_confidence": self.min_confidence,
            "action": self.action,
            "reason_code": self.reason_code,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnforcementRule":
        return cls(
            attack_type=d["attack_type"],
            mode=EnforcementMode(d["mode"]),
            min_confidence=d["min_confidence"],
            action=d["action"],
            reason_code=d["reason_code"],
            description=d.get("description", ""),
        )


# ---------------------------------------------------------------------------
# EnforcementConfig
# ---------------------------------------------------------------------------

@dataclass
class EnforcementConfig:
    """Complete enforcement policy configuration."""

    default_mode: EnforcementMode = EnforcementMode.SHADOW
    rules: Dict[str, EnforcementRule] = field(default_factory=dict)
    allowlist: Set[str] = field(default_factory=set)
    denylist: Set[str] = field(default_factory=set)
    audit_log_path: str = ""

    def __post_init__(self) -> None:
        if not self.audit_log_path:
            self.audit_log_path = os.path.join(_DATA_DIR, "brp_enforcement_log.jsonl")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_mode": self.default_mode.value,
            "rules": {k: v.to_dict() for k, v in self.rules.items()},
            "allowlist": sorted(self.allowlist),
            "denylist": sorted(self.denylist),
            "audit_log_path": self.audit_log_path,
        }

    @classmethod
    def default_config(cls) -> "EnforcementConfig":
        """Return a sensible default enforcement configuration."""
        return cls(
            default_mode=EnforcementMode.SHADOW,
            rules={
                "code_exploit": EnforcementRule(
                    attack_type="code_exploit",
                    mode=EnforcementMode.ENFORCED,
                    min_confidence=0.85,
                    action="deny",
                    reason_code="BRP-CODE-001",
                    description="Block detected code exploit attempts at ≥85% confidence",
                ),
                "privilege_escalation": EnforcementRule(
                    attack_type="privilege_escalation",
                    mode=EnforcementMode.ENFORCED,
                    min_confidence=0.75,
                    action="deny",
                    reason_code="BRP-PRIV-002",
                    description="Block privilege escalation at ≥75% confidence",
                ),
                "data_exfiltration": EnforcementRule(
                    attack_type="data_exfiltration",
                    mode=EnforcementMode.ENFORCED,
                    min_confidence=0.80,
                    action="deny",
                    reason_code="BRP-DATA-003",
                    description="Block data exfiltration at ≥80% confidence",
                ),
                "text_injection": EnforcementRule(
                    attack_type="text_injection",
                    mode=EnforcementMode.ADVISORY,
                    min_confidence=0.70,
                    action="elevate",
                    reason_code="BRP-TEXT-004",
                    description="Elevate text injection for review at ≥70% confidence",
                ),
                "rapid_probe": EnforcementRule(
                    attack_type="rapid_probe",
                    mode=EnforcementMode.ADVISORY,
                    min_confidence=0.60,
                    action="log",
                    reason_code="BRP-PROBE-005",
                    description="Log rapid probe activity at ≥60% confidence",
                ),
            },
            allowlist={"projectx_native", "financial_ops"},
            denylist=set(),
            audit_log_path="",
        )


# ---------------------------------------------------------------------------
# EnforcementDecision
# ---------------------------------------------------------------------------

@dataclass
class EnforcementDecision:
    """Complete record of a single enforcement decision."""

    attack_type: str
    agent_id: str
    confidence: float
    mode: EnforcementMode
    action_taken: str          # "allowed", "denied", "elevated", "logged"
    reason_code: str
    explanation: str
    timestamp: str = ""
    audit_id: str = ""

    def __post_init__(self) -> None:
        if not self.audit_id:
            self.audit_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_type": self.attack_type,
            "agent_id": self.agent_id,
            "confidence": self.confidence,
            "mode": self.mode.value if isinstance(self.mode, EnforcementMode) else self.mode,
            "action_taken": self.action_taken,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
            "audit_id": self.audit_id,
        }


# ---------------------------------------------------------------------------
# EnforcementEngine
# ---------------------------------------------------------------------------

class EnforcementEngine:
    """
    Policy-driven enforcement engine for BRP.

    Evaluates detection events against operator-configurable rules and
    produces EnforcementDecisions. Supports shadow/advisory/enforced modes,
    allowlist/denylist overrides, per-attack-type mode changes, and
    JSONL audit logging.
    """

    def __init__(self, config: Optional[EnforcementConfig] = None) -> None:
        self._config = config or EnforcementConfig.default_config()
        self._lock = threading.Lock()
        self._decisions: List[EnforcementDecision] = []
        self._rebuild_from_log()

    # ── Public API ───────────────────────────────────────────────────────

    def evaluate(
        self, attack_type: str, agent_id: str, confidence: float
    ) -> EnforcementDecision:
        """
        Evaluate a detection event and produce an enforcement decision.

        Steps:
        1. Check allowlist/denylist for agent overrides.
        2. Select the matching rule for the attack_type.
        3. Apply the rule to produce the decision.
        4. Log the decision to the JSONL audit log.
        5. Append to in-memory recent decisions buffer.
        """
        with self._lock:
            # Step 1: allowlist/denylist
            override = self._check_allowlist_denylist(agent_id)

            # Step 2: select rule
            rule = self._select_rule(attack_type)

            # Step 3: apply rule with overrides
            decision = self._apply_rule(rule, agent_id, confidence, override)

            # Step 4: log to JSONL
            self._log_decision(decision)

            # Step 5: buffer for recent decisions
            self._decisions.append(decision)

        return decision

    def set_mode(self, attack_type: str, mode: EnforcementMode) -> None:
        """
        Operator override: change enforcement mode for a specific attack type.
        Creates or updates the in-config rule for that type.
        """
        with self._lock:
            if attack_type in self._config.rules:
                rule = self._config.rules[attack_type]
                rule.mode = mode
            else:
                # Create a default rule for this attack type with the given mode
                self._config.rules[attack_type] = EnforcementRule(
                    attack_type=attack_type,
                    mode=mode,
                    min_confidence=0.0,
                    action="log",
                    reason_code=f"BRP-{attack_type.upper()[:8]}",
                    description=f"Operator-set mode for {attack_type}",
                )

        logger.info(
            "Enforcement mode for attack_type=%s set to %s", attack_type, mode.value
        )

    def get_config_snapshot(self) -> Dict[str, Any]:
        """Return a serializable snapshot of the current enforcement config."""
        with self._lock:
            return self._config.to_dict()

    def get_recent_decisions(self, n: int = 50) -> List[EnforcementDecision]:
        """Return the most recent enforcement decisions (up to n)."""
        with self._lock:
            return list(reversed(self._decisions[-n:]))

    # ── Internal methods ─────────────────────────────────────────────────

    def _check_allowlist_denylist(self, agent_id: str) -> Optional[str]:
        """
        Check if the agent is allowlisted or denylisted.

        Returns:
            "allow" if agent is on the allowlist,
            "deny" if agent is on the denylist,
            None if neither.
        """
        if agent_id in self._config.denylist:
            return "deny"
        if agent_id in self._config.allowlist:
            return "allow"
        return None

    def _select_rule(self, attack_type: str) -> EnforcementRule:
        """Select the enforcement rule for the given attack type."""
        rule = self._config.rules.get(attack_type)
        if rule is not None:
            return rule
        # No specific rule — create a default using the config's default_mode
        return EnforcementRule(
            attack_type=attack_type,
            mode=self._config.default_mode,
            min_confidence=0.0,
            action="log",
            reason_code="BRP-DEFAULT",
            description=f"Default rule for {attack_type} (no explicit rule configured)",
        )

    def _apply_rule(
        self,
        rule: EnforcementRule,
        agent_id: str,
        confidence: float,
        override: Optional[str] = None,
    ) -> EnforcementDecision:
        """
        Apply a rule to produce an EnforcementDecision.

        Overrides:
        - "allow": always allowed, regardless of confidence
        - "deny":   always denied, regardless of confidence

        Mode behavior:
        - SHADOW:   log only, never block
        - ADVISORY: log + elevate for review, no block
        - ENFORCED: block/elevate if confidence >= min_confidence
        """
        effective_mode = rule.mode

        # ── Allowlist/denylist override ──────────────────────────────
        if override == "allow":
            return EnforcementDecision(
                attack_type=rule.attack_type,
                agent_id=agent_id,
                confidence=confidence,
                mode=effective_mode,
                action_taken="allowed",
                reason_code="BRP-ALLOWLIST",
                explanation=(
                    f"Agent '{agent_id}' is on the allowlist. "
                    f"Detection for {rule.attack_type} at {confidence:.2f} "
                    f"confidence overridden to 'allowed'."
                ),
            )

        if override == "deny":
            return EnforcementDecision(
                attack_type=rule.attack_type,
                agent_id=agent_id,
                confidence=confidence,
                mode=effective_mode,
                action_taken="denied",
                reason_code="BRP-DENYLIST",
                explanation=(
                    f"Agent '{agent_id}' is on the denylist. "
                    f"Activity for {rule.attack_type} at {confidence:.2f} "
                    f"confidence overridden to 'denied'."
                ),
            )

        # ── Confidence check ─────────────────────────────────────────
        if confidence < rule.min_confidence:
            return EnforcementDecision(
                attack_type=rule.attack_type,
                agent_id=agent_id,
                confidence=confidence,
                mode=effective_mode,
                action_taken="logged",
                reason_code=rule.reason_code,
                explanation=(
                    f"Confidence {confidence:.2f} is below threshold "
                    f"{rule.min_confidence:.2f} for {rule.attack_type}. "
                    f"Logged only. ({rule.description})"
                ),
            )

        # ── Mode-based enforcement ───────────────────────────────────
        if effective_mode == EnforcementMode.SHADOW:
            return EnforcementDecision(
                attack_type=rule.attack_type,
                agent_id=agent_id,
                confidence=confidence,
                mode=effective_mode,
                action_taken="logged",
                reason_code=rule.reason_code,
                explanation=(
                    f"SHADOW mode: {rule.attack_type} detected at "
                    f"{confidence:.2f} confidence. Logged only, no action taken. "
                    f"({rule.description})"
                ),
            )

        if effective_mode == EnforcementMode.ADVISORY:
            return EnforcementDecision(
                attack_type=rule.attack_type,
                agent_id=agent_id,
                confidence=confidence,
                mode=effective_mode,
                action_taken="elevated",
                reason_code=rule.reason_code,
                explanation=(
                    f"ADVISORY mode: {rule.attack_type} detected at "
                    f"{confidence:.2f} confidence. Elevating for review. "
                    f"({rule.description})"
                ),
            )

        # ENFORCED mode — take the rule's action
        if effective_mode == EnforcementMode.ENFORCED:
            if rule.action == "deny":
                return EnforcementDecision(
                    attack_type=rule.attack_type,
                    agent_id=agent_id,
                    confidence=confidence,
                    mode=effective_mode,
                    action_taken="denied",
                    reason_code=rule.reason_code,
                    explanation=(
                        f"ENFORCED mode: {rule.attack_type} detected at "
                        f"{confidence:.2f} confidence. Action: deny. "
                        f"({rule.description})"
                    ),
                )
            elif rule.action == "elevate":
                return EnforcementDecision(
                    attack_type=rule.attack_type,
                    agent_id=agent_id,
                    confidence=confidence,
                    mode=effective_mode,
                    action_taken="elevated",
                    reason_code=rule.reason_code,
                    explanation=(
                        f"ENFORCED mode: {rule.attack_type} detected at "
                        f"{confidence:.2f} confidence. Action: elevate. "
                        f"({rule.description})"
                    ),
                )
            else:
                return EnforcementDecision(
                    attack_type=rule.attack_type,
                    agent_id=agent_id,
                    confidence=confidence,
                    mode=effective_mode,
                    action_taken="logged",
                    reason_code=rule.reason_code,
                    explanation=(
                        f"ENFORCED mode: {rule.attack_type} detected at "
                        f"{confidence:.2f} confidence. Action: log (no-op). "
                        f"({rule.description})"
                    ),
                )

        # Fallback (should not reach)
        return EnforcementDecision(
            attack_type=rule.attack_type,
            agent_id=agent_id,
            confidence=confidence,
            mode=effective_mode,
            action_taken="logged",
            reason_code=rule.reason_code,
            explanation=f"Fallback: logged for {rule.attack_type}.",
        )

    def _log_decision(self, decision: EnforcementDecision) -> None:
        """Append an enforcement decision to the JSONL audit log (append-only)."""
        log_path = self._config.audit_log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(decision.to_dict(), default=str) + "\n")

    def _rebuild_from_log(self) -> None:
        """Rebuild the in-memory decisions buffer from the existing audit log."""
        log_path = self._config.audit_log_path
        if not os.path.exists(log_path):
            return
        try:
            with open(log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        decision = EnforcementDecision(
                            attack_type=event.get("attack_type", "unknown"),
                            agent_id=event.get("agent_id", "unknown"),
                            confidence=event.get("confidence", 0.0),
                            mode=EnforcementMode(event.get("mode", "shadow")),
                            action_taken=event.get("action_taken", "logged"),
                            reason_code=event.get("reason_code", "BRP-UNKNOWN"),
                            explanation=event.get("explanation", ""),
                            timestamp=event.get("timestamp", ""),
                            audit_id=event.get("audit_id", ""),
                        )
                        self._decisions.append(decision)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

ENFORCEMENT_ENGINE = EnforcementEngine()
