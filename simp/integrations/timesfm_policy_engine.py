"""
TimesFM Policy Engine — SIMP Integration

Enforces per-agent policies before any TimesFM forecast is executed.
Agents must satisfy Q1/Q3/Q8 assessment criteria to receive forecasts.

This engine is intentionally conservative — it gates on documented
utility (Q1), confirmed shadow readiness (Q3), and non-blocking
contract compliance (Q8). Any gap in the assessment causes the request
to be denied with a clear rationale.

Usage:
    from simp.integrations.timesfm_policy_engine import (
        PolicyEngine, AgentContext, make_agent_context_for
    )

    ctx = make_agent_context_for("quantumarb", params)
    engine = PolicyEngine()
    decision = engine.evaluate(ctx)
    if decision.approved:
        resp = await svc.forecast(req)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Q-assessment question keys (must match assessment framework)
# ---------------------------------------------------------------------------

Q1_UTILITY_THRESHOLD = 3       # Minimum utility score (1-5) to proceed
Q3_SHADOW_REQUIRED = True      # Shadow mode must be confirmed before live
Q8_NONBLOCKING_REQUIRED = True # Agent must guarantee non-blocking execution


# ---------------------------------------------------------------------------
# AgentContext — carries per-call context for policy evaluation
# ---------------------------------------------------------------------------

@dataclass
class AgentContext:
    """
    Per-request context submitted to the policy engine.

    Fields map directly to the TimesFM assessment rubric questions:
        q1_utility_score:     Numeric utility score (1=none, 5=critical)
        q3_shadow_confirmed:  Agent has been tested in shadow mode
        q8_nonblocking:       Forecast call is non-blocking to agent execution
        agent_id:             The requesting agent's identifier
        series_id:            The time series being forecasted
        min_series_length:    Number of observations currently available
        requesting_handler:   Name of the agent method/handler making the request
        extra:                Arbitrary metadata for logging / audit
    """
    agent_id: str
    series_id: str
    q1_utility_score: int           # 1–5
    q3_shadow_confirmed: bool
    q8_nonblocking: bool
    min_series_length: int = 0
    requesting_handler: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PolicyDecision — result of a policy evaluation
# ---------------------------------------------------------------------------

@dataclass
class PolicyDecision:
    """
    Result returned by PolicyEngine.evaluate().

    approved:   True if the forecast request may proceed.
    reason:     Human-readable explanation of the decision.
    violations: List of specific policy checks that failed.
    agent_id:   Echo of the requesting agent_id.
    series_id:  Echo of the series_id.
    """
    approved: bool
    reason: str
    violations: List[str]
    agent_id: str
    series_id: str

    @property
    def denied(self) -> bool:
        return not self.approved

    def __str__(self) -> str:
        status = "APPROVED" if self.approved else "DENIED"
        return (
            f"PolicyDecision({status} agent={self.agent_id} "
            f"series={self.series_id} reason={self.reason!r})"
        )


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """
    Evaluates whether an AgentContext satisfies all TimesFM usage policies.

    Policies checked (in order):
        1. Q1 utility score ≥ Q1_UTILITY_THRESHOLD (3)
        2. Q3 shadow mode confirmed (agent tested in shadow before live)
        3. Q8 non-blocking confirmed (forecast cannot stall agent execution)
        4. Minimum series length ≥ 16 observations (prevents nonsense forecasts)

    All policies must pass for approved=True.
    """

    # Minimum number of observations for a meaningful forecast
    MIN_OBSERVATIONS = 16

    def health(self) -> Dict[str, Any]:
        """Return policy engine health and configuration."""
        return {
            "version": "1.0.0",
            "min_observations": self.MIN_OBSERVATIONS,
            "q1_utility_threshold": Q1_UTILITY_THRESHOLD,
            "q3_shadow_required": Q3_SHADOW_REQUIRED,
            "q8_nonblocking_required": Q8_NONBLOCKING_REQUIRED,
            "policy_description": (
                "Evaluates agent context against Q1 (utility ≥ 3), "
                "Q3 (shadow mode confirmed), Q8 (non-blocking), "
                "and minimum series length (≥ 16 observations)"
            ),
        }

    def evaluate(self, ctx: AgentContext) -> PolicyDecision:
        """
        Evaluate the agent context against all policies.

        Args:
            ctx: AgentContext for this request.

        Returns:
            PolicyDecision with approved=True iff all checks pass.
        """
        violations: List[str] = []

        # Q1: Utility threshold
        if ctx.q1_utility_score < Q1_UTILITY_THRESHOLD:
            violations.append(
                f"Q1_UTILITY: score={ctx.q1_utility_score} < required={Q1_UTILITY_THRESHOLD}"
            )

        # Q3: Shadow mode confirmation
        if Q3_SHADOW_REQUIRED and not ctx.q3_shadow_confirmed:
            violations.append(
                "Q3_SHADOW: agent has not been confirmed through shadow mode evaluation"
            )

        # Q8: Non-blocking contract
        if Q8_NONBLOCKING_REQUIRED and not ctx.q8_nonblocking:
            violations.append(
                "Q8_NONBLOCKING: forecast call must be non-blocking to agent execution"
            )

        # Minimum series length
        if ctx.min_series_length < self.MIN_OBSERVATIONS:
            violations.append(
                f"MIN_SERIES_LENGTH: {ctx.min_series_length} < {self.MIN_OBSERVATIONS} "
                f"observations required"
            )

        if violations:
            reason = "; ".join(violations)
            log.debug(
                "PolicyEngine DENIED agent=%s series=%s violations=%s",
                ctx.agent_id,
                ctx.series_id,
                violations,
            )
            return PolicyDecision(
                approved=False,
                reason=reason,
                violations=violations,
                agent_id=ctx.agent_id,
                series_id=ctx.series_id,
            )

        log.debug(
            "PolicyEngine APPROVED agent=%s series=%s handler=%s",
            ctx.agent_id,
            ctx.series_id,
            ctx.requesting_handler,
        )
        return PolicyDecision(
            approved=True,
            reason="All policy checks passed",
            violations=[],
            agent_id=ctx.agent_id,
            series_id=ctx.series_id,
        )


# ---------------------------------------------------------------------------
# Per-agent context factories
# ---------------------------------------------------------------------------
# Q1/Q3/Q8 scores come from the TimesFM Agent Assessment Framework.
# These are fixed at assessment time; the requesting_handler and
# series_id are injected at call time.

_AGENT_ASSESSMENTS: Dict[str, Dict[str, Any]] = {
    "quantumarb": {
        "q1_utility_score": 5,
        "q3_shadow_confirmed": True,
        "q8_nonblocking": True,
    },
    "kashclaw": {
        "q1_utility_score": 4,
        "q3_shadow_confirmed": True,
        "q8_nonblocking": True,
    },
    "kloutbot": {
        "q1_utility_score": 4,
        "q3_shadow_confirmed": True,
        "q8_nonblocking": True,
    },
    "bullbear_predictor": {
        "q1_utility_score": 5,
        "q3_shadow_confirmed": True,
        "q8_nonblocking": True,
    },
    "projectx_native": {
        "q1_utility_score": 3,
        "q3_shadow_confirmed": False,
        "q8_nonblocking": True,
    },
    "claude_cowork": {
        "q1_utility_score": 2,
        "q3_shadow_confirmed": False,
        "q8_nonblocking": True,
    },
    "financial_ops": {
        "q1_utility_score": 3,
        "q3_shadow_confirmed": False,
        "q8_nonblocking": True,
    },
}

# Default for unregistered agents — conservative (denied by default via low Q1)
_DEFAULT_ASSESSMENT: Dict[str, Any] = {
    "q1_utility_score": 1,
    "q3_shadow_confirmed": False,
    "q8_nonblocking": True,
}


def make_agent_context_for(
    agent_id: str,
    series_id: str,
    series_length: int,
    requesting_handler: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> AgentContext:
    """
    Factory: build an AgentContext for a registered agent.

    Args:
        agent_id:            Canonical agent identifier.
        series_id:           Time series identifier for this request.
        series_length:       Number of historical observations available.
        requesting_handler:  Name of the calling method (for audit).
        extra:               Optional metadata dict.

    Returns:
        AgentContext ready for PolicyEngine.evaluate().
    """
    # Normalize agent_id to base name (strip colon-qualified suffixes)
    base_id = agent_id.split(":")[0].lower()
    assessment = _AGENT_ASSESSMENTS.get(base_id, _DEFAULT_ASSESSMENT)

    return AgentContext(
        agent_id=agent_id,
        series_id=series_id,
        q1_utility_score=assessment["q1_utility_score"],
        q3_shadow_confirmed=assessment["q3_shadow_confirmed"],
        q8_nonblocking=assessment["q8_nonblocking"],
        min_series_length=series_length,
        requesting_handler=requesting_handler,
        extra=extra or {},
    )
