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
from collections import deque
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
from simp.security.brp.predictive_safety import PredictiveSafetyIntelligence

logger = logging.getLogger("SIMP.BRP")


# ---------------------------------------------------------------------------
# JSONL persistence helpers
# ---------------------------------------------------------------------------

def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


_jsonl_lock = threading.Lock()


def _append_jsonl(filepath: Path, record: Dict[str, Any]) -> None:
    """Thread-safe append of a single JSON object to a JSONL file."""
    line = json.dumps(record, default=str) + "\n"
    with _jsonl_lock:
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

    # Resolve default data_dir relative to the repo root (two levels up from
    # this file: simp/security/brp_bridge.py → repo root).
    _REPO_ROOT = Path(__file__).resolve().parent.parent.parent

    def __init__(
        self,
        data_dir: Optional[str] = None,
        default_mode: str = BRPMode.SHADOW.value,
    ):
        self.default_mode = default_mode
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = self._REPO_ROOT / "data" / "brp"
        _ensure_dir(self.data_dir)

        # JSONL log files
        self.events_log = self.data_dir / "events.jsonl"
        self.plans_log = self.data_dir / "plans.jsonl"
        self.observations_log = self.data_dir / "observations.jsonl"
        self.responses_log = self.data_dir / "responses.jsonl"
        self.adaptive_rules_file = self.data_dir / "adaptive_rules.json"

        self._predictive = PredictiveSafetyIntelligence()
        self._recent_events = deque(maxlen=256)
        self._recent_observations = deque(maxlen=256)
        self._adaptive_rules: Dict[str, Dict[str, Any]] = {}
        self._warm_history()

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
        predictive = self._predictive.evaluate(
            event.to_dict(),
            recent_events=list(self._recent_events),
            recent_observations=list(self._recent_observations),
            adaptive_rules=self._adaptive_rules,
            sensitive_action_tier=self._extract_sensitive_action_tier(event.action, event.context),
        )
        threat_score = min(1.0, threat_score + predictive["score_boost"])
        threat_tags = self._merge_tags(threat_tags, predictive["threat_tags"])
        severity = self._severity_for(threat_score)
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
            metadata={"predictive_assessment": predictive},
        )

        # Persist
        event_record = event.to_dict()
        _append_jsonl(self.events_log, event_record)
        _append_jsonl(self.responses_log, response.to_dict())
        self._recent_events.append(event_record)

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
        predictive_details: List[Dict[str, Any]] = []

        for step in plan.steps:
            action = step.get("action", "")
            t, _, tags = self._score_action(action, step)
            predictive = self._predictive.evaluate(
                {
                    "source_agent": plan.source_agent,
                    "event_type": BRPEventType.PLAN_REVIEW.value,
                    "action": action,
                    "params": step,
                    "context": plan.context,
                    "tags": plan.tags,
                },
                recent_events=list(self._recent_events),
                recent_observations=list(self._recent_observations),
                adaptive_rules=self._adaptive_rules,
                sensitive_action_tier=self._extract_sensitive_action_tier(action, plan.context),
            )
            step_threat = min(1.0, t + predictive["score_boost"])
            max_threat = max(max_threat, step_threat)
            all_tags.extend(tags)
            all_tags.extend(predictive["threat_tags"])
            predictive_details.append({"action": action, **predictive})

        severity = self._severity_for(max_threat)
        decision = self._decide(max_threat, mode, "plan_review")

        response = BRPResponse(
            event_id=plan.plan_id,
            decision=decision,
            mode=mode,
            severity=severity,
            threat_score=max_threat,
            confidence=self._confidence_for(max_threat),
            threat_tags=self._merge_tags(all_tags, []),
            summary=self._build_summary("plan_review", decision, max_threat),
            metadata={"predictive_steps": predictive_details},
        )

        plan_record = plan.to_dict()
        _append_jsonl(self.plans_log, plan_record)
        _append_jsonl(self.responses_log, response.to_dict())
        self._recent_events.append(
            {
                "timestamp": plan_record["timestamp"],
                "source_agent": plan_record["source_agent"],
                "event_type": BRPEventType.PLAN_REVIEW.value,
                "action": "plan_review",
                "tags": response.threat_tags,
            }
        )

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
        observation_record = observation.to_dict()
        _append_jsonl(self.observations_log, observation_record)
        self._recent_observations.append(observation_record)
        learned_rules = self._learn_from_observation(observation_record)
        logger.info(
            "BRP observation ingested: %s (event=%s, outcome=%s)",
            observation.observation_id, observation.event_id, observation.outcome,
        )
        if learned_rules:
            logger.info(
                "BRP adaptive rules updated from observation %s: %s",
                observation.observation_id,
                ", ".join(learned_rules),
            )

    # ------------------------------------------------------------------
    # Scoring internals
    # ------------------------------------------------------------------

    def _score_event(self, event: BRPEvent):
        """Return (threat_score, severity, threat_tags) for an event."""
        threat_score, _, threat_tags = self._score_action(event.action, event.params)

        if event.event_type == BRPEventType.MESH_INTENT.value:
            threat_score = max(threat_score, 0.15)
            threat_tags.append("mesh_intent")

            context = event.context or {}
            trust_score = self._coerce_float(context.get("target_trust_score"))
            reputation_score = self._coerce_float(context.get("target_reputation_score"))
            stake_amount = self._coerce_float(context.get("mesh_stake_amount"))
            route_mode = str(context.get("mesh_route_mode", "")).strip().lower()

            if trust_score is None:
                threat_score = max(threat_score, 0.25)
                threat_tags.append("missing_mesh_trust")
            elif trust_score < 1.5:
                threat_score = max(threat_score, 0.7)
                threat_tags.append("low_mesh_trust")
            elif trust_score < 3.0:
                threat_score = max(threat_score, 0.4)
                threat_tags.append("reduced_mesh_trust")

            if reputation_score is None:
                threat_score = max(threat_score, 0.25)
                threat_tags.append("missing_mesh_reputation")
            elif reputation_score < 0.35:
                threat_score = max(threat_score, 0.6)
                threat_tags.append("low_mesh_reputation")
            elif reputation_score < 0.6:
                threat_score = max(threat_score, 0.35)
                threat_tags.append("reduced_mesh_reputation")

            if route_mode == "exclusive":
                threat_score = max(threat_score, 0.3)
                threat_tags.append("mesh_exclusive_route")

            if stake_amount is not None and stake_amount >= 250:
                threat_score = max(threat_score, 0.45)
                threat_tags.append("high_mesh_stake")

        severity = self._severity_for(threat_score)
        return threat_score, severity, list(dict.fromkeys(threat_tags))

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

    def _warm_history(self) -> None:
        self._adaptive_rules = self._load_adaptive_rules()

        for record in self._load_jsonl_tail(self.events_log):
            self._recent_events.append(record)
        for record in self._load_jsonl_tail(self.observations_log):
            self._recent_observations.append(record)

    @staticmethod
    def _load_jsonl_tail(filepath: Path, limit: int = 256) -> List[Dict[str, Any]]:
        if not filepath.exists():
            return []
        records = []
        with open(filepath, "r", encoding="utf-8") as handle:
            for line in deque(handle, maxlen=limit):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _load_adaptive_rules(self) -> Dict[str, Dict[str, Any]]:
        if not self.adaptive_rules_file.exists():
            return {}
        try:
            with open(self.adaptive_rules_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            logger.warning("BRP adaptive rules file unreadable: %s", self.adaptive_rules_file)
        return {}

    def _save_adaptive_rules(self) -> None:
        with open(self.adaptive_rules_file, "w", encoding="utf-8") as handle:
            json.dump(self._adaptive_rules, handle, indent=2, sort_keys=True)

    def _learn_from_observation(self, observation: Dict[str, Any]) -> List[str]:
        learned = []
        for proposal in self._predictive.derive_rules_from_observation(observation):
            existing = self._adaptive_rules.get(proposal["key"])
            if existing is None:
                count = 1
                self._adaptive_rules[proposal["key"]] = {
                    **proposal,
                    "count": count,
                    "boost": self._predictive.rule_boost_for_count(count, proposal["severity"]),
                    "last_seen": observation.get("timestamp"),
                    "active": True,
                }
            else:
                existing["count"] = int(existing.get("count", 0)) + 1
                existing["severity"] = proposal["severity"]
                existing["boost"] = self._predictive.rule_boost_for_count(
                    existing["count"],
                    proposal["severity"],
                )
                existing["last_seen"] = observation.get("timestamp")
                existing["active"] = True
            learned.append(proposal["key"])

        if learned:
            self._save_adaptive_rules()
        return learned

    @staticmethod
    def _extract_sensitive_action_tier(action: str, context: Dict[str, Any]) -> Optional[int]:
        action_name = str(
            context.get("projectx_action")
            or context.get("action")
            or action
            or ""
        ).strip()
        if not action_name:
            return None
        try:
            from simp.projectx.computer import ACTION_TIERS
        except Exception:
            return None
        return ACTION_TIERS.get(action_name)

    @staticmethod
    def _merge_tags(tags: List[str], extra_tags: List[str]) -> List[str]:
        seen = set()
        merged = []
        for tag in list(tags) + list(extra_tags):
            if tag in seen:
                continue
            seen.add(tag)
            merged.append(tag)
        return merged

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

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        """Best-effort float coercion for event context values."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
