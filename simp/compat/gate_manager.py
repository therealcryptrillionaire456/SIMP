"""
SIMP Graduation Gate Manager — Sprint 47

Two-gate graduation system for FinancialOps go-live.
Gate 1: operational readiness (connector health, simulated payments, no errors, ops policy).
Gate 2: go-live readiness (gate1 signed off, workflows tested, ledger validated, etc.).
Appends to data/gate_log.jsonl (append-only).
"""

import json
import os
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SIMP.GateManager")

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _ensure_data_dir() -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    return _DATA_DIR


# ---------------------------------------------------------------------------
# GateStatus
# ---------------------------------------------------------------------------

class GateStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SIGNED_OFF = "signed_off"
    PROMOTED = "promoted"


# ---------------------------------------------------------------------------
# GateCondition
# ---------------------------------------------------------------------------

@dataclass
class GateCondition:
    name: str = ""
    description: str = ""
    automated: bool = True
    met: bool = False
    signed_off_by: Optional[str] = None
    signed_off_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# GateCheckResult
# ---------------------------------------------------------------------------

@dataclass
class GateCheckResult:
    gate: int = 0
    status: str = ""
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    all_automated_met: bool = False
    all_met: bool = False
    signed_off: bool = False
    signed_off_by: Optional[str] = None
    signed_off_at: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# GateManager
# ---------------------------------------------------------------------------

class GateManager:
    """
    Manages the two graduation gates for FinancialOps go-live.
    Appends all events to data/gate_log.jsonl.
    """

    def __init__(self, filepath: Optional[str] = None):
        _ensure_data_dir()
        self._filepath = filepath or os.path.join(_DATA_DIR, "gate_log.jsonl")
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []

        # Gate 1 conditions
        self._gate1_conditions: Dict[str, GateCondition] = {
            "connector_health_7_days": GateCondition(
                name="connector_health_7_days",
                description="Payment connector healthy for 7 consecutive days",
                automated=True,
            ),
            "simulated_payments_20": GateCondition(
                name="simulated_payments_20",
                description="At least 20 simulated payments completed",
                automated=True,
            ),
            "no_connector_errors": GateCondition(
                name="no_connector_errors",
                description="No connector errors in the last 7 days",
                automated=True,
            ),
            "ops_policy_reviewed": GateCondition(
                name="ops_policy_reviewed",
                description="Operations policy reviewed and signed off by operator",
                automated=False,
            ),
        }

        # Gate 2 conditions
        self._gate2_conditions: Dict[str, GateCondition] = {
            "gate1_signed_off": GateCondition(
                name="gate1_signed_off",
                description="Gate 1 is fully signed off",
                automated=True,
            ),
            "approval_workflow_tested": GateCondition(
                name="approval_workflow_tested",
                description="Approval workflow end-to-end tested",
                automated=True,
            ),
            "live_ledger_validated": GateCondition(
                name="live_ledger_validated",
                description="Live ledger integrity validated",
                automated=True,
            ),
            "reconciliation_run": GateCondition(
                name="reconciliation_run",
                description="Reconciliation run completed successfully",
                automated=True,
            ),
            "rollback_system_operational": GateCondition(
                name="rollback_system_operational",
                description="Rollback system tested and operational",
                automated=True,
            ),
            "security_review_signed_off": GateCondition(
                name="security_review_signed_off",
                description="Security review signed off by security team",
                automated=False,
            ),
            "pilot_limits_set": GateCondition(
                name="pilot_limits_set",
                description="Pilot spending limits configured and verified",
                automated=False,
            ),
        }

        # Gate sign-off state
        self._gate1_status = GateStatus.NOT_STARTED
        self._gate1_signed_off_by: Optional[str] = None
        self._gate1_signed_off_at: Optional[str] = None
        self._gate2_status = GateStatus.NOT_STARTED
        self._gate2_signed_off_by: Optional[str] = None
        self._gate2_signed_off_at: Optional[str] = None

        self._rebuild_from_events()

    def _rebuild_from_events(self) -> None:
        if not os.path.exists(self._filepath):
            return
        with open(self._filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    self._apply_event(event)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    def _apply_event(self, event: Dict[str, Any]) -> None:
        etype = event.get("type", "")
        self._history.append(event)

        if etype == "condition_signed_off":
            gate = event.get("gate", 0)
            cond_name = event.get("condition", "")
            operator = event.get("signed_off_by", "")
            ts = event.get("timestamp", "")
            conditions = self._gate1_conditions if gate == 1 else self._gate2_conditions
            if cond_name in conditions:
                conditions[cond_name].met = True
                conditions[cond_name].signed_off_by = operator
                conditions[cond_name].signed_off_at = ts

        elif etype == "condition_auto_met":
            gate = event.get("gate", 0)
            cond_name = event.get("condition", "")
            conditions = self._gate1_conditions if gate == 1 else self._gate2_conditions
            if cond_name in conditions:
                conditions[cond_name].met = True

        elif etype == "gate_signed_off":
            gate = event.get("gate", 0)
            if gate == 1:
                self._gate1_status = GateStatus.SIGNED_OFF
                self._gate1_signed_off_by = event.get("signed_off_by", "")
                self._gate1_signed_off_at = event.get("timestamp", "")
            elif gate == 2:
                self._gate2_status = GateStatus.SIGNED_OFF
                self._gate2_signed_off_by = event.get("signed_off_by", "")
                self._gate2_signed_off_at = event.get("timestamp", "")

        elif etype == "gate_promoted":
            gate = event.get("gate", 0)
            if gate == 1:
                self._gate1_status = GateStatus.PROMOTED
            elif gate == 2:
                self._gate2_status = GateStatus.PROMOTED

    def _append_event(self, event: Dict[str, Any]) -> None:
        with open(self._filepath, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def _get_conditions(self, gate: int) -> Dict[str, GateCondition]:
        if gate == 1:
            return self._gate1_conditions
        elif gate == 2:
            return self._gate2_conditions
        raise ValueError(f"Invalid gate: {gate}. Must be 1 or 2.")

    def _check_gate(self, gate: int) -> GateCheckResult:
        conditions = self._get_conditions(gate)
        cond_list = [c.to_dict() for c in conditions.values()]
        all_automated_met = all(c.met for c in conditions.values() if c.automated)
        all_met = all(c.met for c in conditions.values())

        if gate == 1:
            status = self._gate1_status
            signed_off_by = self._gate1_signed_off_by
            signed_off_at = self._gate1_signed_off_at
        else:
            status = self._gate2_status
            signed_off_by = self._gate2_signed_off_by
            signed_off_at = self._gate2_signed_off_at

        # Update status based on conditions
        if status == GateStatus.NOT_STARTED and any(c.met for c in conditions.values()):
            status = GateStatus.IN_PROGRESS

        return GateCheckResult(
            gate=gate,
            status=status.value,
            conditions=cond_list,
            all_automated_met=all_automated_met,
            all_met=all_met,
            signed_off=status in (GateStatus.SIGNED_OFF, GateStatus.PROMOTED),
            signed_off_by=signed_off_by,
            signed_off_at=signed_off_at,
        )

    def check_gate1(self) -> GateCheckResult:
        """Check Gate 1 status and conditions."""
        return self._check_gate(1)

    def check_gate2(self) -> GateCheckResult:
        """Check Gate 2 status and conditions."""
        return self._check_gate(2)

    def sign_off_condition(self, gate: int, condition_name: str, operator: str) -> GateCondition:
        """
        Manually sign off a condition.
        Only non-automated conditions can be signed off manually.
        """
        conditions = self._get_conditions(gate)
        if condition_name not in conditions:
            raise ValueError(f"Unknown condition: {condition_name!r} for gate {gate}")

        cond = conditions[condition_name]
        if cond.automated:
            raise ValueError(f"Condition {condition_name!r} is automated — cannot be manually signed off")

        now = datetime.now(timezone.utc).isoformat()
        event = {
            "type": "condition_signed_off",
            "gate": gate,
            "condition": condition_name,
            "signed_off_by": operator,
            "timestamp": now,
        }
        with self._lock:
            self._append_event(event)
            cond.met = True
            cond.signed_off_by = operator
            cond.signed_off_at = now
            self._history.append(event)

        logger.info("Gate %d condition %s signed off by %s", gate, condition_name, operator)
        return cond

    def mark_condition_met(self, gate: int, condition_name: str) -> GateCondition:
        """
        Mark an automated condition as met.
        """
        conditions = self._get_conditions(gate)
        if condition_name not in conditions:
            raise ValueError(f"Unknown condition: {condition_name!r} for gate {gate}")

        cond = conditions[condition_name]
        now = datetime.now(timezone.utc).isoformat()
        event = {
            "type": "condition_auto_met",
            "gate": gate,
            "condition": condition_name,
            "timestamp": now,
        }
        with self._lock:
            self._append_event(event)
            cond.met = True
            self._history.append(event)

        return cond

    def sign_off_gate(self, gate: int, operator: str) -> GateCheckResult:
        """
        Sign off an entire gate.
        Raises ValueError if automated conditions are not all met.
        """
        conditions = self._get_conditions(gate)
        automated_unmet = [
            c.name for c in conditions.values()
            if c.automated and not c.met
        ]
        if automated_unmet:
            raise ValueError(
                f"Cannot sign off gate {gate}: automated conditions not met: "
                + ", ".join(automated_unmet)
            )

        all_met = all(c.met for c in conditions.values())
        if not all_met:
            raise ValueError(
                f"Cannot sign off gate {gate}: not all conditions are met"
            )

        now = datetime.now(timezone.utc).isoformat()
        event = {
            "type": "gate_signed_off",
            "gate": gate,
            "signed_off_by": operator,
            "timestamp": now,
        }
        with self._lock:
            self._append_event(event)
            self._history.append(event)
            if gate == 1:
                self._gate1_status = GateStatus.SIGNED_OFF
                self._gate1_signed_off_by = operator
                self._gate1_signed_off_at = now
                # Auto-mark gate2 condition
                self._gate2_conditions["gate1_signed_off"].met = True
            elif gate == 2:
                self._gate2_status = GateStatus.SIGNED_OFF
                self._gate2_signed_off_by = operator
                self._gate2_signed_off_at = now

        logger.info("Gate %d signed off by %s", gate, operator)
        return self._check_gate(gate)

    def promote_gate(self, gate: int, operator: str) -> GateCheckResult:
        """Promote a signed-off gate to promoted status."""
        if gate == 1 and self._gate1_status != GateStatus.SIGNED_OFF:
            raise ValueError("Gate 1 must be signed off before promotion")
        if gate == 2 and self._gate2_status != GateStatus.SIGNED_OFF:
            raise ValueError("Gate 2 must be signed off before promotion")

        now = datetime.now(timezone.utc).isoformat()
        event = {
            "type": "gate_promoted",
            "gate": gate,
            "promoted_by": operator,
            "timestamp": now,
        }
        with self._lock:
            self._append_event(event)
            self._history.append(event)
            if gate == 1:
                self._gate1_status = GateStatus.PROMOTED
            elif gate == 2:
                self._gate2_status = GateStatus.PROMOTED

        logger.info("Gate %d promoted by %s", gate, operator)
        return self._check_gate(gate)

    def get_current_gate_status(self) -> Dict[str, Any]:
        """Get status of both gates."""
        return {
            "gate1": self.check_gate1().to_dict(),
            "gate2": self.check_gate2().to_dict(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

GATE_MANAGER = GateManager()
