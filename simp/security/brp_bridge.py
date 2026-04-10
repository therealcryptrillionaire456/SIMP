"""
Bill Russell Protocol (BRP) - Bridge Implementation

Concrete bridge that evaluates events, plans, and observations against
BRP policy rules and persists all records to JSONL for audit.

Default mode: shadow/advisory.  Enforced DENY only for clearly restricted
high-risk actions (withdrawal, admin_delete, etc.).
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from simp.security.brp_models import (
    BRPDecision,
    BRPEvent,
    BRPEventType,
    BRPMode,
    BRPObservation,
    BRPPlan,
    BRPResponse,
    BRPSeverity,
    RESTRICTED_ACTIONS,
)

logger = logging.getLogger("SIMP.BRP")


# ---------------------------------------------------------------------------
# JSONL persistence helpers
# ---------------------------------------------------------------------------

def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _append_jsonl(filepath: Path, record: Dict[str, Any]) -> None:
    """Thread-safe append of a single JSON object to a JSONL file."""
    line = json.dumps(record, default=str) + "\n"
    with threading.Lock():
        with open(filepath, "a") as f:
            f.write(line)


# ---------------------------------------------------------------------------
# BRP Bridge
# ---------------------------------------------------------------------------

class BRPBridge:
    """
    Central BRP evaluation and persistence bridge.

    Usage::

        bridge = BRPBridge()
        response = bridge.evaluate_event(event)
        response = bridge.evaluate_plan(plan)
        bridge.ingest_observation(observation)
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        default_mode: str = BRPMode.SHADOW.value,
    ):
        self.default_mode = default_mode
        self.data_dir = Path(data_dir) if data_dir else Path("data/brp")
        _ensure_dir(self.data_dir)

        # JSONL log files
        self.events_log = self.data_dir / "events.jsonl"
        self.plans_log = self.data_dir / "plans.jsonl"
        self.observations_log = self.data_dir / "observations.jsonl"
        self.responses_log = self.data_dir / "responses.jsonl"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_event(self, event: BRPEvent) -> BRPResponse:
        """
        Evaluate a pre-action event and return a BRPResponse.

        Scoring logic:
        - Restricted actions get threat_score >= 0.8 and ELEVATE/DENY
        - Everything else defaults to SHADOW_ALLOW / ALLOW with low threat
        """
        mode = event.mode or self.default_mode
        threat_score, severity, threat_tags = self._score_event(event)
        decision = self._decide(threat_score, mode, event.action)

        response = BRPResponse(
            event_id=event.event_id,
            decision=decision,
            mode=mode,
            severity=severity,
            threat_score=threat_score,
            confidence=self._confidence_for(threat_score),
            threat_tags=threat_tags,
            summary=self._build_summary(event.action, decision, threat_score),
        )

        # Persist
        _append_jsonl(self.events_log, event.to_dict())
        _append_jsonl(self.responses_log, response.to_dict())

        logger.info(
            "BRP event evaluated: %s -> %s (threat=%.2f, mode=%s)",
            event.event_id, decision, threat_score, mode,
        )
        return response

    def evaluate_plan(self, plan: BRPPlan) -> BRPResponse:
        """
        Evaluate a multi-step plan and return a BRPResponse.

        Iterates plan steps; if any step references a restricted action the
        overall threat score and decision are elevated accordingly.
        """
        mode = plan.mode or self.default_mode
        max_threat = 0.0
        all_tags: List[str] = []

        for step in plan.steps:
            action = step.get("action", "")
            t, _, tags = self._score_action(action, step)
            max_threat = max(max_threat, t)
            all_tags.extend(tags)

        severity = self._severity_for(max_threat)
        decision = self._decide(max_threat, mode, "plan_review")

        response = BRPResponse(
            event_id=plan.plan_id,
            decision=decision,
            mode=mode,
            severity=severity,
            threat_score=max_threat,
            confidence=self._confidence_for(max_threat),
            threat_tags=list(set(all_tags)),
            summary=self._build_summary("plan_review", decision, max_threat),
        )

        _append_jsonl(self.plans_log, plan.to_dict())
        _append_jsonl(self.responses_log, response.to_dict())

        logger.info(
            "BRP plan evaluated: %s -> %s (threat=%.2f, steps=%d)",
            plan.plan_id, decision, max_threat, len(plan.steps),
        )
        return response

    def ingest_observation(self, observation: BRPObservation) -> None:
        """
        Record a post-action observation for audit and temporal correlation.

        Observations are logged but do not produce a decision response.
        """
        _append_jsonl(self.observations_log, observation.to_dict())
        logger.info(
            "BRP observation ingested: %s (event=%s, outcome=%s)",
            observation.observation_id, observation.event_id, observation.outcome,
        )

    # ------------------------------------------------------------------
    # Scoring internals
    # ------------------------------------------------------------------

    def _score_event(self, event: BRPEvent):
        """Return (threat_score, severity, threat_tags) for an event."""
        return self._score_action(event.action, event.params)

    def _score_action(self, action: str, params: Dict[str, Any] = None):
        """Score a single action string + params."""
        params = params or {}
        threat_tags: List[str] = []
        threat_score = 0.0

        action_lower = action.lower().strip()

        # Restricted action check
        if action_lower in RESTRICTED_ACTIONS:
            threat_score = 0.85
            threat_tags.append("restricted_action")
            threat_tags.append(action_lower)

        # Large-value heuristic
        quantity = params.get("quantity", 0)
        if isinstance(quantity, (int, float)) and quantity > 100_000:
            threat_score = max(threat_score, 0.6)
            threat_tags.append("high_value")

        severity = self._severity_for(threat_score)
        return threat_score, severity, threat_tags

    @staticmethod
    def _severity_for(threat_score: float) -> str:
        if threat_score >= 0.8:
            return BRPSeverity.CRITICAL.value
        if threat_score >= 0.6:
            return BRPSeverity.HIGH.value
        if threat_score >= 0.4:
            return BRPSeverity.MEDIUM.value
        if threat_score >= 0.2:
            return BRPSeverity.LOW.value
        return BRPSeverity.INFO.value

    @staticmethod
    def _confidence_for(threat_score: float) -> float:
        """Higher threat scores yield higher confidence in the assessment."""
        if threat_score >= 0.8:
            return 0.95
        if threat_score >= 0.5:
            return 0.8
        return 1.0  # low threat = high confidence it's safe

    @staticmethod
    def _decide(threat_score: float, mode: str, action: str) -> str:
        """
        Determine the BRP decision based on threat score and mode.

        Enforced mode: restricted actions => DENY; high threat => ELEVATE
        Advisory/Shadow mode: always SHADOW_ALLOW or ALLOW (never blocks)
        """
        action_lower = action.lower().strip()

        if mode == BRPMode.ENFORCED.value:
            if action_lower in RESTRICTED_ACTIONS:
                return BRPDecision.DENY.value
            if threat_score >= 0.8:
                return BRPDecision.ELEVATE.value
            if threat_score >= 0.5:
                return BRPDecision.ELEVATE.value
            return BRPDecision.ALLOW.value

        if mode == BRPMode.ADVISORY.value:
            if threat_score >= 0.8:
                return BRPDecision.ELEVATE.value
            return BRPDecision.ALLOW.value

        # Shadow (default) and disabled modes never block
        if mode == BRPMode.SHADOW.value:
            return BRPDecision.SHADOW_ALLOW.value

        # Disabled
        return BRPDecision.LOG_ONLY.value

    @staticmethod
    def _build_summary(action: str, decision: str, threat_score: float) -> str:
        return (
            f"BRP evaluated action='{action}': "
            f"decision={decision}, threat_score={threat_score:.2f}"
        )
