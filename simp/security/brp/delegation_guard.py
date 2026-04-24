"""
Delegation guard for BRP.

Describes a bounded worker-pool model that mirrors useful delegation semantics
without enabling cloning or uncontrolled self-expansion.
"""

from __future__ import annotations

from typing import Any, Dict, List


class DelegationGuard:
    """Bounded worker delegation policy for BRP."""

    def __init__(self, *, max_workers: int = 6) -> None:
        self.max_workers = max(1, int(max_workers))

    def build_summary(self) -> Dict[str, Any]:
        return {
            "mode": "bounded_worker_pool",
            "max_workers": self.max_workers,
            "clone_operations_allowed": False,
            "high_risk_requires_approval": True,
            "task_leasing_enabled": True,
        }

    def assess(self, record: Dict[str, Any]) -> Dict[str, Any]:
        params = record.get("params") if isinstance(record.get("params"), dict) else {}
        context = record.get("context") if isinstance(record.get("context"), dict) else {}
        action = str(record.get("action") or "").lower()
        requested_parallelism = self._coerce_int(
            params.get("parallelism")
            or params.get("worker_count")
            or context.get("parallelism")
            or context.get("worker_count")
            or 1
        )

        clone_requested = any(token in action for token in ("clone", "replicate", "spawn_swarm", "self_replicate"))
        requires_review = clone_requested or requested_parallelism > self.max_workers
        allowed_parallelism = min(max(requested_parallelism, 1), self.max_workers)

        guardrails: List[str] = [
            "fixed worker pool only",
            "task leasing required for delegated work",
            "capability scope per worker",
        ]
        if clone_requested:
            guardrails.append("reject clone and self-replication semantics")
        if requested_parallelism > self.max_workers:
            guardrails.append(f"parallelism capped at {self.max_workers}")

        score_boost = 0.0
        threat_tags: List[str] = []
        if requested_parallelism > self.max_workers:
            score_boost += 0.03
            threat_tags.append("delegation_overflow")
        if clone_requested:
            score_boost += 0.06
            threat_tags.append("clone_semantics_blocked")

        return {
            "enabled": True,
            "requested_parallelism": requested_parallelism,
            "allowed_parallelism": allowed_parallelism,
            "requires_review": requires_review,
            "clone_requested": clone_requested,
            "guardrails": guardrails,
            "score_boost": round(min(score_boost, 0.1), 4),
            "threat_tags": threat_tags,
        }

    @staticmethod
    def _coerce_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 1

