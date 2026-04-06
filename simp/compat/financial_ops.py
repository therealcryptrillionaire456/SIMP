"""
SIMP FinancialOps Agent — Simulated Only (Sprint S7, Sprint 37)

Implements the simulated financial_ops agent skeleton with strict policies,
an immutable simulated spend ledger, and A2A-compatible card generation.

CRITICAL: ALL OPERATIONS ARE SIMULATED. No real spend. No credential storage.
No external API calls. This is a "would-spend ledger" only.
Status: planned (not yet production-enabled).
"""

import logging
from typing import Dict, Any, Tuple, List

import os

from simp.compat.ops_policy import SPEND_LEDGER, get_live_policy_dict
from simp.compat.a2a_security import build_a2a_security_schemes_block

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
            "livePaymentPolicy": get_live_policy_dict(),
        },
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_financial_op(op_type: str, would_spend: float) -> Tuple[bool, str]:
    """
    Validate a financial operation request.

    ALWAYS returns (False, ...) — no autonomous financial action is ever allowed.
    """
    if op_type not in FINANCIAL_OPS_CAPABILITIES:
        return False, f"Unknown financial operation type: {op_type}"

    if would_spend > FINANCIAL_OPS_LIMITS["maxSpendPerTask"]:
        return False, (
            f"Would-spend amount ${would_spend:.2f} exceeds per-task limit "
            f"${FINANCIAL_OPS_LIMITS['maxSpendPerTask']:.2f}"
        )

    return False, "manual approval required — all financial ops require explicit approval"


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
# Live payment execution (Sprint 44) — feature-flagged OFF by default
# ---------------------------------------------------------------------------


def _is_live_enabled() -> bool:
    return os.getenv("FINANCIAL_OPS_LIVE_ENABLED", "false").lower() == "true"


def execute_approved_payment(proposal_id: str) -> Dict[str, Any]:
    """
    Execute an approved payment proposal through the connector pipeline.

    Guards:
    1. FINANCIAL_OPS_LIVE_ENABLED must be 'true'
    2. Proposal must exist and be approved
    3. Idempotency: already-executed proposals are silently returned
    4. Connector must be allowed and healthy
    """
    from simp.compat.approval_queue import APPROVAL_QUEUE
    from simp.compat.payment_connector import (
        build_connector, validate_payment_request, HEALTH_TRACKER,
    )
    from simp.compat.live_ledger import LIVE_SPEND_LEDGER

    # Gate 1: feature flag
    if not _is_live_enabled():
        return {
            "success": False,
            "error": "Live payments not enabled. Set FINANCIAL_OPS_LIVE_ENABLED=true.",
            "proposal_id": proposal_id,
        }

    # Gate 2: idempotency
    if LIVE_SPEND_LEDGER.is_proposal_already_executed(proposal_id):
        return {
            "success": True,
            "message": "Payment already executed (idempotent).",
            "proposal_id": proposal_id,
        }

    # Gate 3: proposal lookup
    proposal = APPROVAL_QUEUE.get_proposal(proposal_id)
    if proposal is None:
        return {"success": False, "error": f"Proposal '{proposal_id}' not found."}

    if proposal.status != "approved":
        return {
            "success": False,
            "error": f"Proposal status is '{proposal.status}', must be 'approved'.",
            "proposal_id": proposal_id,
        }

    # Gate 4: validate payment request
    ok, err = validate_payment_request(
        vendor=proposal.vendor,
        category=proposal.category,
        amount=proposal.would_spend,
        connector_name=proposal.connector_name,
    )
    if not ok:
        return {"success": False, "error": err, "proposal_id": proposal_id}

    # Gate 5: connector health
    health_status = HEALTH_TRACKER.get_status(proposal.connector_name)
    if health_status.get("status") not in ("ok", "unknown"):
        return {
            "success": False,
            "error": f"Connector '{proposal.connector_name}' health: {health_status.get('status')}",
            "proposal_id": proposal_id,
        }

    # Execute
    try:
        connector = build_connector(proposal.connector_name)
        result = connector.execute_small_payment(
            vendor=proposal.vendor,
            amount=proposal.would_spend,
            category=proposal.category,
            idempotency_key=proposal_id,
            proposal_id=proposal_id,
        )

        if result.success:
            record = LIVE_SPEND_LEDGER.record_live_spend(
                proposal_id=proposal_id,
                connector_name=proposal.connector_name,
                vendor=proposal.vendor,
                category=proposal.category,
                amount=proposal.would_spend,
                reference_id=result.reference_id,
                operator_subject=proposal.approved_by or "",
                provider_response=result.provider_response,
                idempotency_key=proposal_id,
            )
            logger.info(
                "LIVE PAYMENT EXECUTED: $%.2f to %s via %s (proposal %s)",
                proposal.would_spend, proposal.vendor,
                proposal.connector_name, proposal_id,
            )
            return {
                "success": True,
                "proposal_id": proposal_id,
                "reference_id": result.reference_id,
                "amount": proposal.would_spend,
                "vendor": proposal.vendor,
                "connector": proposal.connector_name,
                "record_id": record.record_id if record else None,
            }
        else:
            LIVE_SPEND_LEDGER.record_failed_spend(
                proposal_id=proposal_id,
                connector_name=proposal.connector_name,
                vendor=proposal.vendor,
                category=proposal.category,
                amount=proposal.would_spend,
                error=result.error or "Unknown connector error",
            )
            return {
                "success": False,
                "error": result.error or "Payment failed",
                "proposal_id": proposal_id,
            }
    except Exception as exc:
        logger.error("Payment execution failed for proposal %s: %s", proposal_id, exc)
        LIVE_SPEND_LEDGER.record_failed_spend(
            proposal_id=proposal_id,
            connector_name=proposal.connector_name,
            vendor=proposal.vendor,
            category=proposal.category,
            amount=proposal.would_spend,
            error=str(exc),
        )
        return {
            "success": False,
            "error": str(exc),
            "proposal_id": proposal_id,
        }
