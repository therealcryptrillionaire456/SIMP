"""Deterministic iterative controller for ambiguous BRP cases."""

from __future__ import annotations

from typing import Any


class DeterministicRecurrentController:
    """Bounded iterative refinement for BRP metadata, not hard decisions."""

    MAX_SCORE_DELTA = 0.12
    MAX_CONFIDENCE_DELTA = 0.1
    MAX_ROUNDS = 3

    def should_run(self, *, threat_score: float, decision: str) -> bool:
        decision_value = str(decision or "").upper()
        if decision_value == "DENY":
            return False
        return 0.35 <= float(threat_score or 0.0) <= 0.92

    def run(
        self,
        *,
        namespace: str,
        cache_key: str,
        evidence: dict[str, Any],
        cached_state: dict[str, Any] | None = None,
        max_rounds: int | None = None,
    ) -> dict[str, Any]:
        rounds = max(1, min(int(max_rounds or self.MAX_ROUNDS), self.MAX_ROUNDS))
        if not self.should_run(
            threat_score=float(evidence.get("threat_score") or 0.0),
            decision=str(evidence.get("decision") or ""),
        ):
            return {
                "namespace": namespace,
                "cache_key": cache_key,
                "controller_rounds": 0,
                "score_delta": 0.0,
                "confidence_delta": 0.0,
                "reasoning_tags": [],
                "terminal_state": "skipped",
                "round_summaries": [],
            }

        current_delta = float((cached_state or {}).get("score_delta") or 0.0) * 0.15
        current_confidence = float((cached_state or {}).get("confidence_delta") or 0.0) * 0.1
        round_summaries: list[dict[str, Any]] = []
        reasoning_tags: list[str] = []

        predictive_boost = float(evidence.get("predictive_boost") or 0.0)
        multimodal_boost = float(evidence.get("multimodal_boost") or 0.0)
        negative_observations = min(int(evidence.get("negative_observations") or 0), 4)
        failed_remediations = min(int(evidence.get("failed_remediations") or 0), 3)
        completed_remediations = min(int(evidence.get("completed_remediations") or 0), 2)
        related_rules = min(int(evidence.get("related_rules") or 0), 5)
        restricted_action = bool(evidence.get("restricted_action"))
        incident_state = str(evidence.get("incident_state") or "open").lower()
        reopen_count = min(int(evidence.get("reopen_count") or 0), 3)

        positive_pressure = (
            predictive_boost * 0.35
            + multimodal_boost * 0.25
            + negative_observations * 0.03
            + failed_remediations * 0.05
            + related_rules * 0.02
            + (0.08 if restricted_action else 0.0)
            + (0.05 if incident_state in {"reopened", "investigating"} else 0.0)
            + (0.02 * reopen_count)
        )
        relieving_pressure = (
            completed_remediations * 0.04
            + (0.05 if incident_state in {"remediated", "monitoring", "closed"} and failed_remediations == 0 else 0.0)
        )

        if predictive_boost > 0:
            reasoning_tags.append("predictive_pressure")
        if multimodal_boost > 0:
            reasoning_tags.append("multimodal_confirmation")
        if negative_observations:
            reasoning_tags.append("negative_observation_cluster")
        if failed_remediations:
            reasoning_tags.append("remediation_failure_pressure")
        if completed_remediations:
            reasoning_tags.append("remediation_relief")
        if restricted_action:
            reasoning_tags.append("restricted_action_pressure")
        if reopen_count:
            reasoning_tags.append("reopen_pressure")

        for round_index in range(1, rounds + 1):
            damping = 1.0 if round_index == 1 else 0.6 if round_index == 2 else 0.4
            round_delta = (positive_pressure - relieving_pressure) * 0.2 * damping
            round_confidence = abs(positive_pressure - relieving_pressure) * 0.15 * damping
            current_delta += round_delta
            current_confidence += round_confidence
            round_summaries.append(
                {
                    "round": round_index,
                    "damping": damping,
                    "score_delta": round(round_delta, 4),
                    "confidence_delta": round(round_confidence, 4),
                }
            )

        score_delta = max(-self.MAX_SCORE_DELTA, min(round(current_delta, 4), self.MAX_SCORE_DELTA))
        confidence_delta = max(0.0, min(round(current_confidence, 4), self.MAX_CONFIDENCE_DELTA))
        if score_delta >= 0.06:
            terminal_state = "escalate_bias"
        elif score_delta <= -0.03:
            terminal_state = "monitor_bias"
        else:
            terminal_state = "stable"

        return {
            "namespace": namespace,
            "cache_key": cache_key,
            "controller_rounds": rounds,
            "score_delta": score_delta,
            "confidence_delta": confidence_delta,
            "reasoning_tags": sorted(set(reasoning_tags)),
            "terminal_state": terminal_state,
            "round_summaries": round_summaries,
        }
