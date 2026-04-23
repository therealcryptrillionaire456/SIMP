"""
Quantum defense helpers for BRP.

This module provides an advisory-only bridge between BRP and the existing
quantum intelligence stack. It never overrides deterministic BRP decisions and
never enables real hardware execution by itself. The goal is to surface:

1. Backend posture: which quantum backends are available and whether IBM
   hardware is configured but still safely disabled.
2. Skill posture: whether the quantum intelligence stack has relevant
   optimization / cryptography / search skills for deeper defensive analysis.
3. Small bounded threat boosts for cases where the quantum advisory layer
   indicates stronger defensive scrutiny is warranted.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set


class QuantumDefenseAdvisor:
    """Advisory-only quantum posture analysis for BRP."""

    _PROBLEM_MARKERS = {
        "cryptography": {
            "auth", "credential", "token", "permission", "identity", "signature",
            "crypto", "encryption", "key", "mfa",
        },
        "search": {
            "probe", "scan", "mesh", "network", "socket", "dns", "route",
            "exfiltration", "traffic", "header", "request", "bot",
        },
        "machine_learning": {
            "pattern", "anomaly", "multimodal", "classifier", "model",
            "signal", "predictive", "forecast", "cluster",
        },
        "optimization": {
            "queue", "latency", "retry", "schedule", "controller", "fallback",
            "path", "resource", "optimize",
        },
        "finance": {
            "fund", "wallet", "withdrawal", "position", "order", "trade",
        },
        "arbitrage": {
            "arbitrage", "spread", "venue", "execution",
        },
    }

    _HIGH_PRIORITY_TAGS = {
        "restricted_action",
        "zero_day_signal",
        "cross_domain_signal",
        "near_miss_cluster",
        "adaptive_rule_match",
        "projectx_sensitive_action",
        "low_mesh_trust",
        "low_mesh_reputation",
    }

    def __init__(
        self,
        *,
        backend_manager=None,
        skill_evolver=None,
    ) -> None:
        self._backend_manager = backend_manager or self._load_backend_manager()
        self._skill_evolver = skill_evolver or self._load_skill_evolver()

    def assess(
        self,
        record: Dict[str, Any],
        *,
        threat_score: float,
        threat_tags: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Return bounded quantum-defense metadata and a small advisory boost."""
        QuantumIntelligenceLevel, QuantumProblemType, BackendStatus, QuantumBackendType = self._load_quantum_symbols()
        tags = {str(tag).strip().lower() for tag in threat_tags or [] if str(tag).strip()}
        problem_type_value = self._select_problem_type(record, tags)
        problem_type = QuantumProblemType(problem_type_value)
        complexity = min(max(float(threat_score or 0.0), 0.1), 1.0)

        recommendation, recommendation_details = self._skill_evolver.get_skill_recommendation(
            problem_type=problem_type,
            problem_complexity=complexity,
        )
        target_level = (
            QuantumIntelligenceLevel.QUANTUM_INTUITIVE
            if complexity >= 0.75
            else QuantumIntelligenceLevel.QUANTUM_FLUENT
        )
        gaps = self._skill_evolver.assess_skill_gaps(
            target_intelligence_level=target_level,
            current_problems=[problem_type],
        )

        posture = self.build_posture_summary()
        connected = int(posture["backend_summary"]["connected_backends"])
        real_hardware_ready = bool(posture["backend_summary"]["real_hardware_ready"])
        real_hardware_available = bool(posture["backend_summary"]["real_hardware_available"])

        score_boost = 0.0
        reasons: List[str] = []
        if connected:
            score_boost += 0.02
            reasons.append(f"{connected} quantum backend(s) available for advisory analysis")
        if real_hardware_available and not real_hardware_ready:
            reasons.append("IBM Quantum available but still guarded behind explicit hardware opt-in")
        if tags & self._HIGH_PRIORITY_TAGS:
            score_boost += 0.03
            reasons.append("high-priority BRP threat tags warrant deeper defensive scrutiny")
        if recommendation in {"use_existing_skill", "use_and_improve_skill"}:
            score_boost += 0.02
            reasons.append(f"quantum skill posture supports {problem_type.value} defensive analysis")
        if not gaps.get("missing_skills"):
            score_boost += 0.01
            reasons.append("no missing quantum defense skills for the selected problem type")
        if complexity >= 0.8:
            score_boost += 0.02
            reasons.append("critical threat complexity raises quantum-defense review priority")

        score_boost = min(round(score_boost, 4), 0.1)

        return {
            "enabled": True,
            "problem_type": problem_type.value,
            "score_boost": score_boost,
            "backend_summary": posture["backend_summary"],
            "skill_recommendation": {
                "recommendation": recommendation,
                "details": recommendation_details,
            },
            "skill_gap_counts": {
                "missing_skills": len(gaps.get("missing_skills", [])),
                "underdeveloped_skills": len(gaps.get("underdeveloped_skills", [])),
                "recommended_development": len(gaps.get("recommended_development", [])),
            },
            "advisory_actions": reasons,
        }

    def build_posture_summary(self) -> Dict[str, Any]:
        """Return a compact operator-safe view of quantum defensive posture."""
        _, _, BackendStatus, QuantumBackendType = self._load_quantum_symbols()
        backends = list(self._backend_manager.get_available_backends())
        connected = [backend for backend in backends if backend.status == BackendStatus.CONNECTED]
        real_backends = [
            backend for backend in backends
            if backend.backend_type == QuantumBackendType.IBM_QUANTUM and backend.status == BackendStatus.CONNECTED
        ]
        best_backend = self._backend_manager.get_best_backend(qubits_needed=2, max_cost=0.0, min_fidelity=0.8)
        usage = self._backend_manager.get_usage_stats()
        skill_levels = [skill.skill_level for skill in self._skill_evolver.skills.values()]
        avg_skill_level = round(sum(skill_levels) / len(skill_levels), 4) if skill_levels else 0.0

        return {
            "backend_summary": {
                "active_backend": usage.get("active_backend"),
                "available_backends": len(backends),
                "connected_backends": len(connected),
                "real_hardware_available": bool(real_backends),
                "real_hardware_ready": bool(
                    self._backend_manager.config.get("enable_real_hardware", False) and real_backends
                ),
                "best_backend": best_backend.backend_id if best_backend else None,
                "fallback_order": list(self._backend_manager.config.get("fallback_order", [])),
                "cost_limit_per_month": float(self._backend_manager.config.get("cost_limit_per_month", 0.0) or 0.0),
            },
            "usage_summary": {
                "total_jobs": int(usage.get("total_jobs", 0)),
                "success_rate": round(float(usage.get("success_rate", 0.0) or 0.0), 4),
                "total_cost": round(float(usage.get("total_cost", 0.0) or 0.0), 4),
            },
            "skill_summary": {
                "skill_count": len(self._skill_evolver.skills),
                "average_skill_level": avg_skill_level,
                "top_skills": [
                    {
                        "skill_id": skill.skill_id,
                        "skill_level": skill.skill_level,
                        "success_rate": round(float(skill.success_rate or 0.0), 4),
                    }
                    for skill in sorted(
                        self._skill_evolver.skills.values(),
                        key=lambda item: (-item.skill_level, -float(item.success_rate or 0.0), item.skill_id),
                    )[:5]
                ],
            },
        }

    def _select_problem_type(self, record: Dict[str, Any], tags: Set[str]) -> str:
        serialised = self._normalise_text(record)
        tag_text = " ".join(sorted(tags))
        combined = f"{serialised} {tag_text}".lower()

        best_type = "optimization"
        best_hits = 0
        for problem_type, markers in self._PROBLEM_MARKERS.items():
            hits = sum(1 for marker in markers if marker in combined)
            if hits > best_hits:
                best_hits = hits
                best_type = problem_type
        return best_type

    @staticmethod
    def _load_quantum_symbols():
        from simp.organs.quantum_intelligence import (
            QuantumIntelligenceLevel,
            QuantumProblemType,
        )
        from simp.organs.quantum_intelligence.quantum_backend_manager import (
            BackendStatus,
            QuantumBackendType,
        )

        return QuantumIntelligenceLevel, QuantumProblemType, BackendStatus, QuantumBackendType

    @staticmethod
    def _load_backend_manager():
        from simp.organs.quantum_intelligence.quantum_backend_manager import get_quantum_backend_manager

        return get_quantum_backend_manager()

    @staticmethod
    def _load_skill_evolver():
        from simp.organs.quantum_intelligence.quantum_evolver import QuantumSkillEvolver

        return QuantumSkillEvolver(agent_id="brp_quantum_defense")

    @staticmethod
    def _normalise_text(record: Dict[str, Any]) -> str:
        chunks: List[str] = []
        for key in ("source_agent", "event_type", "action"):
            value = record.get(key)
            if value:
                chunks.append(str(value))
        for key in ("context", "params", "result_data", "tags", "metadata"):
            value = record.get(key)
            if value:
                chunks.append(str(value))
        return " ".join(chunks).lower()
