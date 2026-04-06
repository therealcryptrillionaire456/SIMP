"""
SIMP Autonomous Operations Policy — Sprint S4 (Sprint 34)

Defines and enforces the policy model for autonomous operations
(maintenance, analysis, simulated spend). This is not an enforcement engine —
it's a type-safe policy document and validation layer that gates what the
compat layer will accept.

All financial operations are SIMULATED ONLY. No real spend occurs.
"""

import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any


# ---------------------------------------------------------------------------
# Op-type constants
# ---------------------------------------------------------------------------

class AutonomousOpType:
    MAINTENANCE = "maintenance"
    ANALYSIS = "analysis"
    SIMULATED_SPEND = "simulated_spend"


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------

@dataclass
class OpsPolicy:
    version: str = "0.1.0"
    default_mode: str = "recommendation_only"
    allowed_op_types: List[str] = field(
        default_factory=lambda: ["maintenance", "analysis", "simulated_spend"]
    )
    spend_limits_enabled: bool = True
    spend_mode: str = "simulation"
    global_max_spend_per_task: float = 20.00
    global_max_spend_per_day: float = 50.00
    global_max_spend_per_month: float = 200.00
    currency: str = "USD"
    approval_required: bool = True
    log_all_decisions: bool = True
    log_destination: str = "immutable_ledger"
    include_reasoning_summary: bool = True
    exclude_raw_inputs: bool = True


_DEFAULT_POLICY = OpsPolicy()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_op_request(
    op_type: str, spend_amount: float = 0.0
) -> Tuple[bool, Optional[str]]:
    """
    Validate an autonomous operation request against the default policy.

    Returns (True, None) if structurally valid but still needs approval,
    or (False, reason) if rejected outright.

    In practice this ALWAYS returns (False, ...) because all ops
    require manual approval.
    """
    policy = _DEFAULT_POLICY

    if op_type not in policy.allowed_op_types:
        return False, f"Operation type '{op_type}' is not allowed"

    if spend_amount > policy.global_max_spend_per_task:
        return False, (
            f"Spend amount ${spend_amount:.2f} exceeds per-task limit "
            f"${policy.global_max_spend_per_task:.2f}"
        )

    if policy.spend_mode != "simulation":
        return False, "Spend mode must be 'simulation'"

    # All ops require manual approval — this is intentional
    return False, "manual approval required"


def get_policy_dict() -> Dict[str, Any]:
    """
    Serialise the default policy for inclusion in A2A cards / API responses.

    Never includes internal log_destination details.
    """
    d = asdict(_DEFAULT_POLICY)
    # Redact internals
    d.pop("log_destination", None)
    return d


# ---------------------------------------------------------------------------
# Spend record + ledger
# ---------------------------------------------------------------------------

@dataclass
class SpendRecord:
    record_id: str = ""
    timestamp: str = ""
    op_type: str = ""
    agent_id: str = ""
    description: str = ""
    would_spend: float = 0.0
    currency: str = "USD"
    status: str = "simulated"
    approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SimulatedSpendLedger:
    """In-memory, append-only simulated spend ledger (thread-safe)."""

    def __init__(self) -> None:
        self._records: List[SpendRecord] = []
        self._lock = threading.Lock()

    def record_simulated_spend(
        self,
        agent_id: str,
        description: str,
        would_spend: float,
    ) -> SpendRecord:
        rec = SpendRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            op_type=AutonomousOpType.SIMULATED_SPEND,
            agent_id=agent_id,
            description=description,
            would_spend=would_spend,
            currency="USD",
            status="simulated",
            approved=False,
        )
        with self._lock:
            self._records.append(rec)
        return rec

    def get_ledger(self) -> List[SpendRecord]:
        with self._lock:
            return list(self._records)

    def get_ledger_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = sum(r.would_spend for r in self._records)
            return {
                "total_would_spend": round(total, 2),
                "count": len(self._records),
                "currency": "USD",
                "last_10": [r.to_dict() for r in self._records[-10:]],
            }


# Module-level singleton
SPEND_LEDGER = SimulatedSpendLedger()
