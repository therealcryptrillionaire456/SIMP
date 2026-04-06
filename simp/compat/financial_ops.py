"""
SIMP FinancialOps Agent — Sprints S7, 41-45

Implements the financial_ops agent skeleton with strict policies,
an immutable simulated spend ledger, payment connector integration,
approval queue, live execution, and A2A-compatible card generation.

CRITICAL: ALL OPERATIONS ARE SIMULATED unless FINANCIAL_OPS_LIVE_ENABLED=true.
No credential storage. No external API calls with real keys.
"""

import logging
import os
import uuid
from typing import Dict, Any, Tuple, List, Optional

from simp.compat.ops_policy import SPEND_LEDGER, OpsPolicy
from simp.compat.a2a_security import build_a2a_security_schemes_block
from simp.compat.payment_connector import (
    build_connector,
    validate_payment_request,
    ALLOWED_CONNECTORS,
    HEALTH_TRACKER,
)

logger = logging.getLogger("SIMP.FinancialOps")

# ---------------------------------------------------------------------------
# Capabilities and limits
# ---------------------------------------------------------------------------

FINANCIAL_OPS_CAPABILITIES = ["small_purchase", "subscription_management", "license_renewal"]

FINANCIAL_OPS_LIMITS: Dict[str, Any] = {
    "maxSpendPerTask": 20.00,
    "maxSpendPerDay": 50.00,
    "maxSpendPerMonth": 200.00,
    "maxVendors": 5,
    "currency": "USD",
    "mode": "simulate_only",
}


# ---------------------------------------------------------------------------
# Agent card
# ---------------------------------------------------------------------------


def build_financial_ops_card(broker_base_url: str = "http://127.0.0.1:5555") -> Dict[str, Any]:
    """
    Return A2A Agent Card for FinancialOps.

    NEVER includes payment credentials, real API endpoints, or real vendor names.
    """
    base = broker_base_url.rstrip("/")

    skills: List[Dict[str, Any]] = [
        {
            "id": f"financial.{cap}",
            "name": cap.replace("_", " ").title() + " (Simulated)",
            "description": f"Simulate {cap.replace('_', ' ')} operation. No real spend.",
        }
        for cap in FINANCIAL_OPS_CAPABILITIES
    ]

    live_enabled = os.environ.get("FINANCIAL_OPS_LIVE_ENABLED", "").lower() == "true"

    return {
        "name": "SIMP FinancialOps Agent",
        "description": (
            "Planned financial operations agent for small purchases and subscriptions. "
            "SIMULATED ONLY — status: planned."
        ),
        "version": "1.0",
        "url": f"{base}/a2a/agents/financial-ops",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": skills,
        "securitySchemes": build_a2a_security_schemes_block(),
        "security": [
            {"scheme": "oauth2", "scopes": ["payments.simulate"]},
        ],
        "safetyPolicies": {
            "requiresManualApproval": True,
            "manualApprovalThreshold": 0.00,
            "readOnlyMode": True,
            "noCredentialStorage": True,
            "sandboxMode": True,
        },
        "resourceLimits": dict(FINANCIAL_OPS_LIMITS),
        "x-simp": {
            "agent_type": "financial_ops",
            "status": "planned",
            "mode": "simulate_only",
            "all_ops_require_approval": True,
            "environment": "development",
            "protocol": "simp/1.0",
            "livePaymentPolicy": {
                "enabled": live_enabled,
                "connectors": sorted(ALLOWED_CONNECTORS.keys()),
                "pilotLimits": {
                    "maxPerTransaction": 20.00,
                    "maxPerDay": 50.00,
                    "maxPerMonth": 200.00,
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Validation — Sprint 43: 3-state return
# ---------------------------------------------------------------------------


def validate_financial_op(
    op_type: str, would_spend: float, vendor: str = "", category: str = ""
) -> Tuple[str, str]:
    """
    Validate a financial operation request.

    Returns (state, message) where state is one of:
      - "rejected": operation is not allowed
      - "pending_approval": structurally valid, needs approval
      - "approved_for_execution": already approved (not used directly here)
    """
    if op_type not in FINANCIAL_OPS_CAPABILITIES:
        return "rejected", f"Unknown financial operation type: {op_type}"

    if would_spend > FINANCIAL_OPS_LIMITS["maxSpendPerTask"]:
        return "rejected", (
            f"Would-spend amount ${would_spend:.2f} exceeds per-task limit "
            f"${FINANCIAL_OPS_LIMITS['maxSpendPerTask']:.2f}"
        )

    if would_spend <= 0:
        return "rejected", "Amount must be positive"

    return "pending_approval", "Manual approval required — all financial ops require explicit approval"


# ---------------------------------------------------------------------------
# Record simulated spend
# ---------------------------------------------------------------------------


def record_would_spend(
    agent_id: str,
    op_type: str,
    would_spend: float,
    description: str,
) -> Dict[str, Any]:
    """
    Create a SpendRecord via the ops_policy SPEND_LEDGER.

    Logs as SIMULATED — never as real spend.
    """
    logger.info(
        "SIMULATED SPEND: would spend $%.2f on %s — %s",
        would_spend, op_type, description,
    )
    record = SPEND_LEDGER.record_simulated_spend(
        agent_id=agent_id,
        description=f"would spend ${would_spend:.2f} on {op_type} for {description}",
        would_spend=would_spend,
    )
    return record.to_dict()


# ---------------------------------------------------------------------------
# Execute approved payment — Sprint 44
# ---------------------------------------------------------------------------


def execute_approved_payment(proposal_id: str) -> Dict[str, Any]:
    """
    Execute a previously approved payment proposal.

    Steps:
      1. Check FINANCIAL_OPS_LIVE_ENABLED env var
      2. Load proposal, verify status="approved"
      3. Re-validate against OpsPolicy (defense in depth)
      4. Idempotency check via LIVE_LEDGER
      5. Record attempt, call connector, record outcome

    Returns {"status": "succeeded|failed|already_executed", ...}
    """
    import simp.compat.approval_queue as _aq_mod
    import simp.compat.live_ledger as _ll_mod
    APPROVAL_QUEUE = _aq_mod.APPROVAL_QUEUE
    LIVE_LEDGER = _ll_mod.LIVE_LEDGER
    PaymentProposalStatus = _aq_mod.PaymentProposalStatus

    # Step 0: check rollback state
    from simp.compat.rollback import ROLLBACK_MANAGER, RollbackState
    rollback_state = ROLLBACK_MANAGER.get_state()
    if rollback_state == RollbackState.ACTIVE:
        raise RuntimeError(
            "Rollback is ACTIVE — live payments are blocked. "
            "Deactivate rollback before executing payments."
        )

    # Step 1: env var gate
    live_enabled = os.environ.get("FINANCIAL_OPS_LIVE_ENABLED", "").lower() == "true"
    if not live_enabled:
        raise RuntimeError(
            "Live payments are not enabled. Set FINANCIAL_OPS_LIVE_ENABLED=true."
        )

    # Step 2: load and verify proposal
    proposal = APPROVAL_QUEUE.get_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"Proposal {proposal_id!r} not found")
    if proposal.status != PaymentProposalStatus.APPROVED:
        raise ValueError(
            f"Proposal {proposal_id!r} is {proposal.status}, not approved"
        )

    # Step 2b: budget monitor check — CRITICAL task/daily alerts block execution
    from simp.compat.budget_monitor import BUDGET_MONITOR
    BUDGET_MONITOR.check_task_limit(proposal.amount)
    if BUDGET_MONITOR.has_critical_alert(categories=["task", "daily"]):
        raise RuntimeError(
            "Budget monitor has CRITICAL alerts (task or daily limit). "
            "Acknowledge alerts before executing payments."
        )

    # Step 3: re-validate against policy (defense in depth)
    state, msg = validate_financial_op(
        proposal.op_type, proposal.amount,
        vendor=proposal.vendor, category=proposal.category,
    )
    if state == "rejected":
        raise ValueError(f"Policy re-validation failed: {msg}")

    # Step 4: idempotency check
    idempotency_key = f"proposal-{proposal_id}"
    if LIVE_LEDGER.is_already_executed(idempotency_key):
        return {
            "status": "already_executed",
            "proposal_id": proposal_id,
            "message": "This proposal has already been executed (idempotency guard).",
        }

    # Step 5: record attempt, execute, record outcome
    attempt = LIVE_LEDGER.record_attempt(
        proposal_id=proposal_id,
        idempotency_key=idempotency_key,
        connector_name=proposal.connector_name,
        vendor=proposal.vendor,
        category=proposal.category,
        amount=proposal.amount,
    )

    try:
        connector = build_connector(proposal.connector_name)
        result = connector.execute_small_payment(
            amount=proposal.amount,
            vendor=proposal.vendor,
            description=proposal.description,
            idempotency_key=idempotency_key,
        )

        if result.success:
            LIVE_LEDGER.record_outcome(
                record_id=attempt.record_id,
                status="succeeded",
                provider_reference=result.reference_id,
            )
            return {
                "status": "succeeded",
                "record_id": attempt.record_id,
                "proposal_id": proposal_id,
                "amount": proposal.amount,
                "dry_run": result.dry_run,
            }
        else:
            LIVE_LEDGER.record_outcome(
                record_id=attempt.record_id,
                status="failed",
                error=result.error or result.message,
            )
            return {
                "status": "failed",
                "record_id": attempt.record_id,
                "proposal_id": proposal_id,
                "error": result.error or result.message,
            }

    except Exception as exc:
        LIVE_LEDGER.record_outcome(
            record_id=attempt.record_id,
            status="failed",
            error=str(exc),
        )
        return {
            "status": "failed",
            "record_id": attempt.record_id,
            "proposal_id": proposal_id,
            "error": str(exc),
        }
