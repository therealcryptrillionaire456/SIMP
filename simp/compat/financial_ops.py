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

from simp.compat.ops_policy import SPEND_LEDGER
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
