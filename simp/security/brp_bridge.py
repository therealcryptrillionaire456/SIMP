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
from simp.security.brp.multimodal_analysis import MultiModalSafetyAnalyzer
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
        self.remediations_log = self.data_dir / "remediations.jsonl"
        self.adaptive_rules_file = self.data_dir / "adaptive_rules.json"

        self._predictive = PredictiveSafetyIntelligence()
        self._multimodal = MultiModalSafetyAnalyzer()
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
        multimodal = self._evaluate_multimodal_record(
            {
                **event.to_dict(),
                "action": event.action,
                "params": event.params,
                "context": event.context,
                "tags": event.tags,
            }
        )
        threat_score = min(1.0, threat_score + multimodal["score_boost"])
        threat_tags = self._merge_tags(threat_tags, multimodal["threat_tags"])
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
            metadata={
                "predictive_assessment": predictive,
                "multimodal_assessment": multimodal,
            },
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
        multimodal_details: List[Dict[str, Any]] = []

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
            multimodal = self._evaluate_multimodal_record(
                {
                    "source_agent": plan.source_agent,
                    "event_type": BRPEventType.PLAN_REVIEW.value,
                    "action": action,
                    "params": step,
                    "context": plan.context,
                    "tags": plan.tags,
                }
            )
            step_threat = min(1.0, step_threat + multimodal["score_boost"])
            max_threat = max(max_threat, step_threat)
            all_tags.extend(tags)
            all_tags.extend(predictive["threat_tags"])
            all_tags.extend(multimodal["threat_tags"])
            predictive_details.append({"action": action, **predictive})
            multimodal_details.append({"action": action, **multimodal})

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
            metadata={
                "predictive_steps": predictive_details,
                "multimodal_steps": multimodal_details,
            },
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

    @classmethod
    def read_operator_status(
        cls,
        data_dir: Optional[str] = None,
        recent_limit: int = 50,
    ) -> Dict[str, Any]:
        """Read a lightweight operator-facing BRP summary without instantiating the bridge."""
        brp_dir = cls._resolve_data_dir(data_dir)
        recent_evaluations = cls.read_operator_evaluations(data_dir=str(brp_dir), limit=recent_limit)
        recent_observations = cls._load_jsonl_tail(brp_dir / "observations.jsonl", limit=recent_limit)
        recent_remediations = cls.read_operator_remediations(data_dir=str(brp_dir), limit=recent_limit)
        adaptive_rules = cls.read_operator_adaptive_rules(data_dir=str(brp_dir), limit=500)

        decision_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}
        mode_counts: Dict[str, int] = {}
        tag_counts: Dict[str, int] = {}
        total_threat = 0.0

        for evaluation in recent_evaluations:
            decision = str(evaluation.get("decision") or "unknown")
            severity = str(evaluation.get("severity") or "unknown")
            mode = str(evaluation.get("mode") or "unknown")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            total_threat += float(evaluation.get("threat_score") or 0.0)
            for tag in evaluation.get("threat_tags", []) or []:
                tag_key = str(tag)
                tag_counts[tag_key] = tag_counts.get(tag_key, 0) + 1

        active_rules = [rule for rule in adaptive_rules if rule.get("active", True)]
        latest_evaluation = recent_evaluations[0].get("timestamp") if recent_evaluations else None
        latest_observation = recent_observations[-1].get("timestamp") if recent_observations else None
        latest_remediation = recent_remediations[0].get("timestamp") if recent_remediations else None
        average_threat = round(total_threat / len(recent_evaluations), 4) if recent_evaluations else 0.0

        return {
            "status": "success",
            "has_data": any(
                (
                    cls._count_jsonl(brp_dir / "events.jsonl"),
                    cls._count_jsonl(brp_dir / "plans.jsonl"),
                    cls._count_jsonl(brp_dir / "responses.jsonl"),
                    cls._count_jsonl(brp_dir / "observations.jsonl"),
                    cls._count_jsonl(brp_dir / "remediations.jsonl"),
                    len(adaptive_rules),
                )
            ),
            "data_dir": str(brp_dir),
            "counts": {
                "events": cls._count_jsonl(brp_dir / "events.jsonl"),
                "plans": cls._count_jsonl(brp_dir / "plans.jsonl"),
                "responses": cls._count_jsonl(brp_dir / "responses.jsonl"),
                "observations": cls._count_jsonl(brp_dir / "observations.jsonl"),
                "remediations": cls._count_jsonl(brp_dir / "remediations.jsonl"),
            },
            "recent": {
                "window_size": recent_limit,
                "decision_counts": decision_counts,
                "severity_counts": severity_counts,
                "mode_counts": mode_counts,
                "active_adaptive_rules": len(active_rules),
                "last_evaluation_at": latest_evaluation,
                "last_observation_at": latest_observation,
                "last_remediation_at": latest_remediation,
                "max_threat_score": max((float(item.get("threat_score") or 0.0) for item in recent_evaluations), default=0.0),
                "average_threat_score": average_threat,
                "top_threat_tags": [
                    {"tag": tag, "count": count}
                    for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
                ],
            },
        }

    @classmethod
    def read_operator_evaluations(
        cls,
        data_dir: Optional[str] = None,
        limit: int = 25,
        decision: Optional[str] = None,
        severity: Optional[str] = None,
        source_agent: Optional[str] = None,
        action: Optional[str] = None,
        query: Optional[str] = None,
        event_id: Optional[str] = None,
        record_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Read normalized BRP evaluations for dashboard/operator views."""
        brp_dir = cls._resolve_data_dir(data_dir)
        safe_limit = max(1, min(limit, 200))
        search_limit = max(safe_limit * 8, 400)
        responses = cls._load_jsonl_tail(brp_dir / "responses.jsonl", limit=search_limit)
        events = cls._load_jsonl_tail(brp_dir / "events.jsonl", limit=max(search_limit * 2, 400))
        plans = cls._load_jsonl_tail(brp_dir / "plans.jsonl", limit=max(search_limit * 2, 400))
        event_index = {str(record.get("event_id")): record for record in events}
        plan_index = {str(record.get("plan_id")): record for record in plans}

        decision_filter = str(decision or "").strip().upper()
        severity_filter = str(severity or "").strip().lower()
        source_filter = str(source_agent or "").strip().lower()
        action_filter = str(action or "").strip().lower()
        query_filter = str(query or "").strip().lower()
        event_id_filter = str(event_id or "").strip()
        record_type_filter = str(record_type or "").strip().lower()

        evaluations: List[Dict[str, Any]] = []
        for response in responses:
            event_id = str(response.get("event_id") or "")
            event_record = event_index.get(event_id)
            plan_record = plan_index.get(event_id)
            source_record = event_record or plan_record or {}
            record_type = "event" if event_record else "plan" if plan_record else "unknown"
            metadata = response.get("metadata") if isinstance(response.get("metadata"), dict) else {}
            predictive = metadata.get("predictive_assessment") if isinstance(metadata.get("predictive_assessment"), dict) else {}
            multimodal = metadata.get("multimodal_assessment") if isinstance(metadata.get("multimodal_assessment"), dict) else {}
            predictive_steps = metadata.get("predictive_steps") if isinstance(metadata.get("predictive_steps"), list) else []
            multimodal_steps = metadata.get("multimodal_steps") if isinstance(metadata.get("multimodal_steps"), list) else []

            step_predictive_boost = max((float(step.get("score_boost") or 0.0) for step in predictive_steps), default=0.0)
            step_multimodal_boost = max((float(step.get("score_boost") or 0.0) for step in multimodal_steps), default=0.0)
            step_multimodal_detections = sum(
                int((step.get("summary") or {}).get("total_detections", 0))
                for step in multimodal_steps
                if isinstance(step, dict)
            )

            evaluations.append(
                {
                    "response_id": response.get("response_id"),
                    "event_id": event_id,
                    "record_type": record_type,
                    "timestamp": response.get("timestamp"),
                    "decision": response.get("decision"),
                    "mode": response.get("mode"),
                    "severity": response.get("severity"),
                    "threat_score": response.get("threat_score"),
                    "confidence": response.get("confidence"),
                    "threat_tags": response.get("threat_tags", []),
                    "summary": response.get("summary"),
                    "source_agent": source_record.get("source_agent"),
                    "event_type": source_record.get("event_type", "plan_review" if plan_record else None),
                    "action": source_record.get("action", "plan_review" if plan_record else None),
                    "step_count": len(plan_record.get("steps", [])) if plan_record else None,
                    "predictive_score_boost": round(
                        max(float(predictive.get("score_boost") or 0.0), step_predictive_boost),
                        4,
                    ),
                    "multimodal_score_boost": round(
                        max(float(multimodal.get("score_boost") or 0.0), step_multimodal_boost),
                        4,
                    ),
                    "multimodal_detections": (
                        int((multimodal.get("summary") or {}).get("total_detections", 0))
                        if multimodal
                        else step_multimodal_detections
                    ),
                    "metadata": metadata,
                }
            )

        filtered = []
        for item in evaluations:
            if decision_filter and str(item.get("decision") or "").upper() != decision_filter:
                continue
            if severity_filter and str(item.get("severity") or "").lower() != severity_filter:
                continue
            if source_filter and source_filter not in str(item.get("source_agent") or "").lower():
                continue
            if action_filter and action_filter not in str(item.get("action") or item.get("event_type") or "").lower():
                continue
            if query_filter:
                haystack = " ".join(
                    [
                        str(item.get("source_agent") or ""),
                        str(item.get("action") or ""),
                        str(item.get("event_type") or ""),
                        " ".join(str(tag) for tag in (item.get("threat_tags") or [])),
                    ]
                ).lower()
                if query_filter not in haystack:
                    continue
            if event_id_filter and str(item.get("event_id") or "") != event_id_filter:
                continue
            if record_type_filter and str(item.get("record_type") or "").lower() != record_type_filter:
                continue
            filtered.append(item)

        filtered.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return filtered[:safe_limit]

    @classmethod
    def read_operator_evaluation_detail(
        cls,
        event_id: str,
        data_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return a single operator-facing BRP evaluation detail bundle."""
        lookup_event_id = str(event_id or "").strip()
        if not lookup_event_id:
            return None

        brp_dir = cls._resolve_data_dir(data_dir)
        evaluations = cls.read_operator_evaluations(
            data_dir=str(brp_dir),
            limit=1,
            event_id=lookup_event_id,
        )
        if not evaluations:
            return None

        evaluation = evaluations[0]
        events = cls._load_jsonl_tail(brp_dir / "events.jsonl", limit=800)
        plans = cls._load_jsonl_tail(brp_dir / "plans.jsonl", limit=800)
        observations = cls._load_jsonl_tail(brp_dir / "observations.jsonl", limit=800)
        adaptive_rules = cls.read_operator_adaptive_rules(data_dir=str(brp_dir), limit=200)

        event_record = next((record for record in reversed(events) if str(record.get("event_id") or "") == lookup_event_id), None)
        plan_record = next((record for record in reversed(plans) if str(record.get("plan_id") or "") == lookup_event_id), None)
        related_observations = [
            record for record in observations
            if str(record.get("event_id") or "") == lookup_event_id
        ][-20:]

        action_name = str(evaluation.get("action") or "").strip().lower()
        related_rules = []
        for rule in adaptive_rules:
            key = str(rule.get("key") or "").lower()
            if action_name and f"action:{action_name}" in key:
                related_rules.append(rule)
                continue
            if any(str(tag).lower() in key for tag in evaluation.get("threat_tags", []) or []):
                related_rules.append(rule)

        related_alert = next(
            (
                alert
                for alert in cls.read_operator_alerts(data_dir=str(brp_dir), limit=200)
                if str(alert.get("event_id") or "") == lookup_event_id
            ),
            None,
        )
        related_playbook = None
        if related_alert:
            related_playbook = next(
                (
                    playbook
                    for playbook in cls.read_operator_playbooks(data_dir=str(brp_dir), limit=200)
                    if str(playbook.get("alert_id") or "") == str(related_alert.get("alert_id") or "")
                ),
                None,
            )
        related_remediations = cls.read_operator_remediations(
            data_dir=str(brp_dir),
            limit=20,
            event_id=lookup_event_id,
        )

        return {
            "evaluation": evaluation,
            "source_record": event_record or plan_record,
            "related_observations": related_observations,
            "related_rules": related_rules[:20],
            "alert": related_alert,
            "playbook": related_playbook,
            "remediations": related_remediations,
        }

    @classmethod
    def read_operator_adaptive_rules(
        cls,
        data_dir: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Read adaptive rules in operator-friendly sorted order."""
        brp_dir = cls._resolve_data_dir(data_dir)
        data = cls._load_json_file(brp_dir / "adaptive_rules.json")
        if not isinstance(data, dict):
            return []

        rules: List[Dict[str, Any]] = []
        for key, value in data.items():
            if not isinstance(value, dict):
                continue
            rules.append({"key": key, **value})

        rules.sort(
            key=lambda item: (
                not bool(item.get("active", True)),
                -int(item.get("count", 0)),
                str(item.get("last_seen") or ""),
                str(item.get("key") or ""),
            ),
            reverse=False,
        )
        return rules[: max(1, min(limit, 500))]

    @classmethod
    def read_operator_alerts(
        cls,
        data_dir: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Derive operator-facing BRP alerts from recent evaluations and adaptive rules."""
        brp_dir = cls._resolve_data_dir(data_dir)
        evaluations = cls.read_operator_evaluations(data_dir=str(brp_dir), limit=max(limit * 4, 50))
        rules = cls.read_operator_adaptive_rules(data_dir=str(brp_dir), limit=100)
        alert_state = cls._load_operator_alert_state(brp_dir)

        alerts: List[Dict[str, Any]] = []
        for evaluation in evaluations:
            severity = str(evaluation.get("severity") or "").lower()
            decision = str(evaluation.get("decision") or "").upper()
            score = float(evaluation.get("threat_score") or 0.0)
            if severity not in {"high", "critical"} and decision not in {"ELEVATE", "DENY"} and score < 0.7:
                continue

            recommendation = "Review BRP detail and correlated observations."
            if decision in {"ELEVATE", "DENY"}:
                recommendation = "Inspect the BRP drawer, then verify whether the triggering action should remain blocked or elevated."
            elif "restricted_action" in (evaluation.get("threat_tags") or []):
                recommendation = "Confirm restricted-action policy and check whether the source flow is expected."
            elif (evaluation.get("predictive_score_boost") or 0) > 0.0:
                recommendation = "Inspect predictive matches and recent near-miss patterns for repeated unsafe behavior."

            alerts.append(
                {
                    "alert_id": f"brp-alert::{evaluation.get('event_id')}",
                    "event_id": evaluation.get("event_id"),
                    "timestamp": evaluation.get("timestamp"),
                    "severity": severity or "high",
                    "decision": decision or "ELEVATE",
                    "source_agent": evaluation.get("source_agent"),
                    "action": evaluation.get("action") or evaluation.get("event_type"),
                    "summary": evaluation.get("summary"),
                    "threat_score": round(score, 4),
                    "threat_tags": evaluation.get("threat_tags", []),
                    "recommendation": recommendation,
                }
            )

        active_rules = [rule for rule in rules if rule.get("active", True) and int(rule.get("count", 0)) >= 3]
        if active_rules:
            alerts.append(
                {
                    "alert_id": "brp-alert::adaptive-rules",
                    "event_id": None,
                    "timestamp": active_rules[0].get("last_seen"),
                    "severity": "medium",
                    "decision": "ADAPTIVE_RULE",
                    "source_agent": "brp_bridge",
                    "action": "adaptive_rule_growth",
                    "summary": f"{len(active_rules)} adaptive BRP rules are active with repeated matches.",
                    "threat_score": 0.55,
                    "threat_tags": [rule.get("key") for rule in active_rules[:5]],
                    "recommendation": "Review active adaptive rules for drift and confirm the rules still represent real threat signals.",
                }
            )

        for alert in alerts:
            state = alert_state.get(str(alert.get("alert_id") or ""), {})
            acknowledged = bool(state.get("acknowledged"))
            alert["state"] = str(state.get("state") or ("acknowledged" if acknowledged else "open"))
            alert["acknowledged"] = acknowledged
            alert["acknowledged_at"] = state.get("acknowledged_at")
            alert["acknowledged_by"] = state.get("acknowledged_by")
            alert["ack_note"] = state.get("ack_note")
            alert["updated_at"] = state.get("updated_at")

        alerts.sort(key=lambda item: (str(item.get("timestamp") or ""), float(item.get("threat_score") or 0.0)), reverse=True)
        return alerts[: max(1, min(limit, 100))]

    @classmethod
    def read_operator_incidents(
        cls,
        data_dir: Optional[str] = None,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Return operator incident counts plus current alert state."""
        brp_dir = cls._resolve_data_dir(data_dir)
        alerts = cls.read_operator_alerts(data_dir=str(brp_dir), limit=limit)
        open_alerts = [alert for alert in alerts if not bool(alert.get("acknowledged"))]
        critical_open = [
            alert
            for alert in open_alerts
            if str(alert.get("severity") or "").lower() == "critical"
        ]
        return {
            "status": "success",
            "count": len(alerts),
            "open_alerts": len(open_alerts),
            "acknowledged_alerts": len(alerts) - len(open_alerts),
            "critical_open_alerts": len(critical_open),
            "latest_alert_at": alerts[0].get("timestamp") if alerts else None,
            "alerts": alerts,
        }

    @classmethod
    def acknowledge_operator_alert(
        cls,
        alert_id: str,
        *,
        actor: str = "dashboard_ui",
        note: Optional[str] = None,
        data_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Persist alert acknowledgement metadata and return the merged alert."""
        brp_dir = cls._resolve_data_dir(data_dir)
        lookup_alert_id = str(alert_id or "").strip()
        if not lookup_alert_id:
            return None

        alert = next(
            (
                item
                for item in cls.read_operator_alerts(data_dir=str(brp_dir), limit=200)
                if str(item.get("alert_id") or "") == lookup_alert_id
            ),
            None,
        )
        if alert is None:
            return None

        cls._set_operator_alert_state(
            brp_dir,
            lookup_alert_id,
            state="acknowledged",
            actor=actor,
            note=note,
            acknowledged=True,
        )
        return next(
            (
                item
                for item in cls.read_operator_alerts(data_dir=str(brp_dir), limit=200)
                if str(item.get("alert_id") or "") == lookup_alert_id
            ),
            None,
        )

    @classmethod
    def read_operator_playbooks(
        cls,
        data_dir: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return derived remediation playbooks for current BRP alerts."""
        brp_dir = cls._resolve_data_dir(data_dir)
        alerts = cls.read_operator_alerts(data_dir=str(brp_dir), limit=max(limit * 3, 25))
        remediations = cls.read_operator_remediations(data_dir=str(brp_dir), limit=200)
        latest_by_alert = {}
        for remediation in remediations:
            alert_id = str(remediation.get("alert_id") or "")
            if alert_id and alert_id not in latest_by_alert:
                latest_by_alert[alert_id] = remediation

        playbooks = []
        for alert in alerts:
            playbook = cls._build_operator_playbook(alert)
            playbook["last_remediation"] = latest_by_alert.get(str(alert.get("alert_id") or ""))
            playbooks.append(playbook)
        return playbooks[: max(1, min(limit, 50))]

    @classmethod
    def read_operator_remediations(
        cls,
        data_dir: Optional[str] = None,
        limit: int = 25,
        *,
        alert_id: Optional[str] = None,
        event_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Read persisted BRP remediation actions in reverse chronological order."""
        brp_dir = cls._resolve_data_dir(data_dir)
        remediations = cls._load_jsonl_tail(brp_dir / "remediations.jsonl", limit=max(limit * 8, 100))
        alert_filter = str(alert_id or "").strip()
        event_filter = str(event_id or "").strip()
        status_filter = str(status or "").strip().lower()

        filtered: List[Dict[str, Any]] = []
        for remediation in remediations:
            if alert_filter and str(remediation.get("alert_id") or "") != alert_filter:
                continue
            if event_filter and str(remediation.get("event_id") or "") != event_filter:
                continue
            if status_filter and str(remediation.get("status") or "").lower() != status_filter:
                continue
            filtered.append(remediation)

        filtered.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return filtered[: max(1, min(limit, 100))]

    @classmethod
    def record_operator_remediation(
        cls,
        *,
        alert_id: str,
        playbook_id: str,
        actor: str,
        job: str,
        result: Dict[str, Any],
        data_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Persist an operator remediation execution and advance alert state."""
        brp_dir = cls._resolve_data_dir(data_dir)
        alerts = cls.read_operator_alerts(data_dir=str(brp_dir), limit=200)
        playbooks = cls.read_operator_playbooks(data_dir=str(brp_dir), limit=200)
        alert = next((item for item in alerts if str(item.get("alert_id") or "") == str(alert_id or "").strip()), None)
        playbook = next((item for item in playbooks if str(item.get("playbook_id") or "") == str(playbook_id or "").strip()), None)
        if alert is None or playbook is None:
            return None

        status_value = str(result.get("status") or "unknown").lower()
        remediation_status = "completed" if status_value == "success" else "failed" if status_value == "error" else "unreachable"
        response = result.get("response") if isinstance(result.get("response"), dict) else {}
        record = {
            "remediation_id": f"remediation::{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            "timestamp": datetime.utcnow().isoformat(),
            "alert_id": alert["alert_id"],
            "event_id": alert.get("event_id"),
            "playbook_id": playbook["playbook_id"],
            "actor": str(actor or "dashboard_ui"),
            "job": job,
            "status": remediation_status,
            "routing_mode": result.get("routing_mode"),
            "broker_intent_id": result.get("broker_intent_id"),
            "delivery_status": result.get("delivery_status"),
            "response_status": response.get("status") if isinstance(response, dict) else None,
            "response": result.get("response"),
            "summary": playbook.get("summary") or alert.get("summary"),
        }
        _append_jsonl(brp_dir / "remediations.jsonl", record)

        feedback_bridge = cls(data_dir=str(brp_dir))
        feedback_observation = BRPObservation(
            source_agent=str(alert.get("source_agent") or actor or "dashboard_ui"),
            event_id=str(alert.get("event_id") or ""),
            action=str(alert.get("action") or job or "remediation"),
            outcome=(
                "success"
                if remediation_status == "completed"
                else "error"
                if remediation_status == "failed"
                else "partial"
            ),
            result_data={
                "remediation_id": record["remediation_id"],
                "playbook_id": playbook["playbook_id"],
                "job": job,
                "remediation_status": remediation_status,
                "delivery_status": result.get("delivery_status"),
                "response_status": record.get("response_status"),
            },
            context={
                "actor": str(actor or "dashboard_ui"),
                "alert_id": alert["alert_id"],
                "playbook_id": playbook["playbook_id"],
                "remediation_status": remediation_status,
                "automation_job": job,
            },
            mode=str(alert.get("mode") or BRPMode.ADVISORY.value),
            tags=cls._dedupe_str_list(
                list(alert.get("threat_tags", []) or [])
                + [
                    "remediation_feedback",
                    f"remediation_{remediation_status}",
                    str(playbook.get("category") or "").strip().lower(),
                ]
            ),
        )
        feedback_bridge.ingest_observation(feedback_observation)
        record["observation_id"] = feedback_observation.observation_id

        next_state = "remediated" if remediation_status == "completed" else "acknowledged"
        note = f"Remediation {remediation_status} via {job}"
        cls._set_operator_alert_state(
            brp_dir,
            alert["alert_id"],
            state=next_state,
            actor=actor,
            note=note,
            acknowledged=True,
        )
        return record

    @classmethod
    def read_operator_report(
        cls,
        data_dir: Optional[str] = None,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Return a combined BRP operator report bundle for exports and dashboards."""
        brp_dir = cls._resolve_data_dir(data_dir)
        return {
            "status": "success",
            "generated_at": datetime.utcnow().isoformat(),
            "data_dir": str(brp_dir),
            "status_summary": cls.read_operator_status(data_dir=str(brp_dir), recent_limit=max(limit, 25)),
            "alerts": cls.read_operator_alerts(data_dir=str(brp_dir), limit=limit),
            "incidents": cls.read_operator_incidents(data_dir=str(brp_dir), limit=limit),
            "playbooks": cls.read_operator_playbooks(data_dir=str(brp_dir), limit=min(limit, 10)),
            "remediations": cls.read_operator_remediations(data_dir=str(brp_dir), limit=min(limit, 25)),
            "evaluations": cls.read_operator_evaluations(data_dir=str(brp_dir), limit=limit),
            "adaptive_rules": cls.read_operator_adaptive_rules(data_dir=str(brp_dir), limit=limit),
        }

    @classmethod
    def read_runtime_predictive_context(
        cls,
        data_dir: Optional[str] = None,
        recent_limit: int = 64,
    ) -> Dict[str, Any]:
        """Return BRP learning state for runtime consumers such as mesh screening."""
        brp_dir = cls._resolve_data_dir(data_dir)
        adaptive_rules = cls._load_json_file(brp_dir / "adaptive_rules.json")
        if not isinstance(adaptive_rules, dict):
            adaptive_rules = {}
        return {
            "data_dir": str(brp_dir),
            "recent_observations": cls._load_jsonl_tail(
                brp_dir / "observations.jsonl",
                limit=max(1, min(recent_limit, 256)),
            ),
            "adaptive_rules": adaptive_rules,
        }

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

    def _evaluate_multimodal_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        inputs = self._build_multimodal_inputs(record)
        if not any(inputs.values()):
            return {
                "score_boost": 0.0,
                "threat_tags": [],
                "summary": {"total_detections": 0, "detection_breakdown": {}},
            }

        result = self._multimodal.run_all(
            texts=inputs["texts"],
            code_samples=inputs["code_samples"],
            behavior_events=inputs["behavior_events"],
            network_flows=inputs["network_flows"],
            memory_records=inputs["memory_records"],
        )
        total_detections = int(result["total_detections"])
        max_channel_hits = max(result["detection_breakdown"].values(), default=0)
        score_boost = min(0.35, (0.08 * total_detections) + (0.03 * max_channel_hits))

        threat_tags = []
        breakdown = result["detection_breakdown"]
        if breakdown.get("text_threats"):
            threat_tags.append("multimodal_text_threat")
        if breakdown.get("code_vulnerabilities"):
            threat_tags.append("multimodal_code_risk")
        if breakdown.get("behavior_anomalies"):
            threat_tags.append("multimodal_behavior_risk")
        if breakdown.get("network_anomalies"):
            threat_tags.append("multimodal_network_risk")
        if breakdown.get("memory_correlations"):
            threat_tags.append("multimodal_memory_risk")

        return {
            "score_boost": round(score_boost, 4),
            "threat_tags": threat_tags,
            "summary": {
                "total_detections": total_detections,
                "detection_breakdown": breakdown,
                "combined_accuracy": result["combined_accuracy"],
            },
        }

    def _build_multimodal_inputs(self, record: Dict[str, Any]) -> Dict[str, Any]:
        params = record.get("params") or {}
        context = record.get("context") or {}
        tags = record.get("tags") or []

        texts = []
        code_samples = []
        behavior_events = []
        network_flows = []
        memory_records = []

        for container in (record, params, context):
            for key in ("text", "message", "prompt", "description", "details", "content", "rationale"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
            for key in ("code", "script", "patch", "command"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    code_samples.append(
                        {
                            "file": str(container.get("file") or container.get("path") or f"{record.get('action', 'snippet')}.txt"),
                            "code": value,
                        }
                    )

        if isinstance(context.get("network_flow"), dict):
            network_flows.append(context["network_flow"])
        elif any(key in context for key in ("source", "destination", "protocol", "bytes", "suspicious")):
            network_flows.append(context)

        if any(key in context for key in ("pattern", "risk_level")):
            behavior_events.append(
                {
                    "pattern": context.get("pattern", ""),
                    "description": context.get("description", context.get("details", "")),
                    "risk_level": context.get("risk_level", "medium"),
                }
            )

        if any(key in context for key in ("memory_id", "correlation_score", "access_agent")):
            memory_records.append(
                {
                    "memory_id": context.get("memory_id", record.get("event_id", "memory_record")),
                    "content": context.get("content", context.get("details", "")),
                    "access_agent": context.get("access_agent", record.get("source_agent", "")),
                    "correlation_score": context.get("correlation_score", 0),
                }
            )

        if "network" in [str(tag).lower() for tag in tags] and isinstance(params, dict) and params:
            network_flows.append(params)

        return {
            "texts": self._dedupe_str_list(texts),
            "code_samples": code_samples,
            "behavior_events": behavior_events,
            "network_flows": network_flows,
            "memory_records": memory_records,
        }

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

    @staticmethod
    def _load_json_file(filepath: Path) -> Any:
        if not filepath.exists():
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    @classmethod
    def _resolve_data_dir(cls, data_dir: Optional[str] = None) -> Path:
        if data_dir:
            return Path(data_dir)
        return cls._REPO_ROOT / "data" / "brp"

    @staticmethod
    def _count_jsonl(filepath: Path) -> int:
        if not filepath.exists():
            return 0
        count = 0
        with open(filepath, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count

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

    @classmethod
    def _operator_alert_state_file(cls, brp_dir: Path) -> Path:
        return brp_dir / "alert_state.json"

    @classmethod
    def _load_operator_alert_state(cls, brp_dir: Path) -> Dict[str, Dict[str, Any]]:
        data = cls._load_json_file(cls._operator_alert_state_file(brp_dir))
        return data if isinstance(data, dict) else {}

    @classmethod
    def _save_operator_alert_state(cls, brp_dir: Path, state: Dict[str, Dict[str, Any]]) -> None:
        filepath = cls._operator_alert_state_file(brp_dir)
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)

    @classmethod
    def _set_operator_alert_state(
        cls,
        brp_dir: Path,
        alert_id: str,
        *,
        state: str,
        actor: str,
        note: Optional[str],
        acknowledged: bool,
    ) -> None:
        stored = cls._load_operator_alert_state(brp_dir)
        current = stored.get(alert_id, {})
        timestamp = datetime.utcnow().isoformat()
        stored[alert_id] = {
            **current,
            "acknowledged": bool(acknowledged),
            "state": state,
            "acknowledged_at": current.get("acknowledged_at") or timestamp if acknowledged else current.get("acknowledged_at"),
            "acknowledged_by": str(actor or "dashboard_ui") if acknowledged else current.get("acknowledged_by"),
            "ack_note": str(note or "").strip() or current.get("ack_note"),
            "updated_at": timestamp,
        }
        cls._save_operator_alert_state(brp_dir, stored)

    @classmethod
    def _build_operator_playbook(cls, alert: Dict[str, Any]) -> Dict[str, Any]:
        actions: List[str] = [
            "Inspect the BRP evidence drawer and correlated observations.",
            "Validate that the source agent and requested action are expected for the current workflow.",
        ]
        threat_tags = {str(tag).lower() for tag in alert.get("threat_tags", []) or []}
        decision = str(alert.get("decision") or "").upper()
        severity = str(alert.get("severity") or "medium").lower()
        action_name = str(alert.get("action") or "").strip().lower()

        if decision in {"DENY", "ELEVATE"}:
            actions.append("Confirm whether the elevated or denied action should remain blocked before retrying.")
        if "restricted_action" in threat_tags or action_name in RESTRICTED_ACTIONS:
            actions.append("Review restricted-action policy and verify whether a manual approval path is required.")
        if any(tag.startswith("predictive") or tag.endswith("signal") for tag in threat_tags):
            actions.append("Review predictive matches and recent adaptive rules for repeated near-miss behavior.")
        if any(tag.startswith("multimodal_") for tag in threat_tags):
            actions.append("Inspect multimodal detections to confirm the signal is not a false positive.")
        if action_name in {"withdrawal", "fund_transfer"}:
            actions.append("Confirm destination, amount, and authorization chain before allowing any financial transfer.")
        if action_name in {"run_shell", "admin_delete"}:
            actions.append("Pause high-risk operator execution until the requested command or deletion is manually reviewed.")

        if severity == "critical":
            title = "Immediate containment required"
            category = "containment"
        elif severity == "high":
            title = "Escalated operator review"
            category = "review"
        else:
            title = "Policy drift / safety hygiene review"
            category = "hygiene"

        automation_job = "native_agent_task_audit"
        automation_reason = "Audit current task and routing state before retrying the flow."
        if severity == "critical" or decision == "DENY" or "restricted_action" in threat_tags:
            automation_job = "native_agent_security_audit"
            automation_reason = "Run the security audit path before allowing any retry or override."
        elif "multimodal_code_risk" in threat_tags or "multimodal_network_risk" in threat_tags:
            automation_job = "native_agent_repo_scan"
            automation_reason = "Run a bounded repo scan to inspect code or network-related drift."
        elif "predictive_pattern" in threat_tags or "predictive_sequence" in threat_tags:
            automation_job = "native_agent_task_audit"
            automation_reason = "Inspect recent task and event history for repeated unsafe patterns."

        deduped_actions = cls._dedupe_str_list(actions)
        return {
            "playbook_id": f"playbook::{alert.get('alert_id')}",
            "alert_id": alert.get("alert_id"),
            "event_id": alert.get("event_id"),
            "priority": severity,
            "status": alert.get("state") or ("acknowledged" if alert.get("acknowledged") else "open"),
            "title": title,
            "category": category,
            "summary": alert.get("summary"),
            "primary_action": deduped_actions[0] if deduped_actions else "Inspect BRP evidence.",
            "actions": deduped_actions,
            "recommendation": alert.get("recommendation"),
            "source_agent": alert.get("source_agent"),
            "action": alert.get("action"),
            "decision": alert.get("decision"),
            "severity": severity,
            "timestamp": alert.get("timestamp"),
            "automation": {
                "job": automation_job,
                "allowed": True,
                "reason": automation_reason,
            },
        }

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
    def _dedupe_str_list(values: List[str]) -> List[str]:
        seen = set()
        ordered = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

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
