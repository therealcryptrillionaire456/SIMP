"""
SIMP Reconciliation — Sprint 45 (Sprint 45)

Read-only reconciliation engine that compares live ledger totals
against a reference total. Never modifies ledgers.
"""

import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from simp.compat.live_ledger import LIVE_LEDGER

logger = logging.getLogger("SIMP.Reconciliation")


# ---------------------------------------------------------------------------
# ReconciliationResult
# ---------------------------------------------------------------------------

@dataclass
class ReconciliationResult:
    run_id: str = ""
    period_start: str = ""
    period_end: str = ""
    live_ledger_total: float = 0.0
    reference_total: Optional[float] = None
    discrepancy: float = 0.0
    status: str = "reference_unavailable"  # matched, discrepancy, reference_unavailable
    flagged_records: List[Dict[str, Any]] = field(default_factory=list)
    run_at: str = ""

    def __post_init__(self):
        if not self.run_id:
            self.run_id = str(uuid.uuid4())
        if not self.run_at:
            self.run_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Reconciliation engine
# ---------------------------------------------------------------------------

def run_reconciliation(
    period_start: str,
    period_end: str,
    reference_total: Optional[float] = None,
) -> ReconciliationResult:
    """
    Run reconciliation for a time period.

    - Sums succeeded payments in the live ledger within the period.
    - Compares against reference_total if provided.
    - Never modifies any ledger.
    - Flags records with errors or anomalies.

    Returns ReconciliationResult with status:
      - "matched" if totals match within $0.01
      - "discrepancy" if totals differ
      - "reference_unavailable" if no reference_total provided
    """
    records = LIVE_LEDGER.get_all_records()

    # Filter by period
    in_period = []
    for rec in records:
        ts = rec.attempted_at or ""
        if period_start <= ts <= period_end:
            in_period.append(rec)

    # Sum succeeded
    live_total = sum(r.amount for r in in_period if r.status == "succeeded")
    live_total = round(live_total, 2)

    # Flag anomalies
    flagged = []
    for rec in in_period:
        flags = []
        if rec.status == "failed":
            flags.append("failed_payment")
        if rec.status == "pending":
            flags.append("still_pending")
        if rec.error:
            flags.append("has_error")
        if flags:
            flagged.append({
                "record_id": rec.record_id,
                "proposal_id": rec.proposal_id,
                "amount": rec.amount,
                "status": rec.status,
                "flags": flags,
            })

    # Determine status
    if reference_total is None:
        status = "reference_unavailable"
        discrepancy = 0.0
    else:
        discrepancy = round(live_total - reference_total, 2)
        if abs(discrepancy) <= 0.01:
            status = "matched"
        else:
            status = "discrepancy"

    result = ReconciliationResult(
        period_start=period_start,
        period_end=period_end,
        live_ledger_total=live_total,
        reference_total=reference_total,
        discrepancy=discrepancy,
        status=status,
        flagged_records=flagged,
    )

    logger.info(
        "Reconciliation %s: %s (live=$%.2f, ref=%s, disc=$%.2f)",
        result.run_id, status, live_total,
        f"${reference_total:.2f}" if reference_total is not None else "N/A",
        discrepancy,
    )

    return result
