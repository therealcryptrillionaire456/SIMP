"""
Quantum advisory optimizer for BRP.

This layer derives queueing and prioritization advice from the quantum posture
already exposed by the BRP quantum defense advisor. It remains advisory only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .quantum_defense import QuantumDefenseAdvisor


class QuantumAdvisoryOptimizer:
    """Priority and optimization hints built on top of quantum posture."""

    def __init__(self, advisor: QuantumDefenseAdvisor | None = None) -> None:
        self._advisor = advisor or QuantumDefenseAdvisor()

    def build_summary(self) -> Dict[str, Any]:
        posture = self._advisor.build_posture_summary()
        backend_summary = posture.get("backend_summary", {})
        skill_summary = posture.get("skill_summary", {})
        connected = int(backend_summary.get("connected_backends") or 0)
        average_skill_level = float(skill_summary.get("average_skill_level") or 0.0)
        return {
            "mode": "advisory_only",
            "connected_backends": connected,
            "best_backend": backend_summary.get("best_backend"),
            "recommended_queue": "priority" if connected else "serial",
            "optimization_ready": connected > 0 and average_skill_level >= 0.5,
            "average_skill_level": round(average_skill_level, 4),
        }

    def assess(self, record: Dict[str, Any], *, threat_score: float, threat_tags: Sequence[str]) -> Dict[str, Any]:
        posture = self.build_summary()
        tags = {str(tag).strip().lower() for tag in threat_tags if str(tag).strip()}
        record_text = " ".join(
            [
                str(record.get("action") or ""),
                str(record.get("event_type") or ""),
                str(record.get("context") or ""),
                str(record.get("params") or ""),
            ]
        ).lower()

        lane = "general"
        if any(token in record_text for token in ("route", "mesh", "network", "scan", "probe")):
            lane = "search"
        elif any(token in record_text for token in ("token", "auth", "key", "crypto", "signature")):
            lane = "cryptography"
        elif any(token in record_text for token in ("queue", "retry", "fallback", "controller", "schedule")):
            lane = "optimization"

        priority = "routine"
        score_boost = 0.0
        reasons: List[str] = []
        if threat_score >= 0.75 or tags.intersection({"restricted_action", "low_mesh_trust", "low_mesh_reputation"}):
            priority = "expedite"
            score_boost += 0.02
            reasons.append("high-risk record should be prioritized for deeper advisory review")
        if posture.get("optimization_ready"):
            score_boost += 0.01
            reasons.append("quantum advisory posture is ready for bounded optimization support")
        if lane != "general":
            reasons.append(f"record maps to the {lane} optimization lane")

        return {
            "enabled": True,
            "lane": lane,
            "priority": priority,
            "recommended_queue": posture.get("recommended_queue"),
            "optimization_ready": posture.get("optimization_ready"),
            "score_boost": round(min(score_boost, 0.04), 4),
            "threat_tags": ["quantum_optimizer_priority"] if score_boost > 0 else [],
            "advisory_actions": reasons,
        }

