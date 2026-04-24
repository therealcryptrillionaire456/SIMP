"""ProjectX bounded self-repair planner.

Phase 11 scope:
  - inspect the world-model twin
  - check invariants and scenario risk estimates
  - propose bounded, non-destructive repair plans

This module does not apply code changes, file deletions, process restarts, or
other destructive actions. It only emits structured repair assessments.
"""

from __future__ import annotations

import math
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from projectx_security import append_redacted_jsonl, utc_now_iso
from projectx_simp_config import get_projectx_runtime_dir
from projectx_world_model import InvariantCheck, ScenarioRiskEstimate, WorldModelTwin, get_world_twin


SELF_REPAIR_PHASE = 11
DEFAULT_SELF_REPAIR_DIR = get_projectx_runtime_dir() / "data" / "self_repair"
DEFAULT_SELF_REPAIR_DIR.mkdir(parents=True, exist_ok=True)


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return max(0.0, min(1.0, parsed))


def _severity_rank(severity: str) -> int:
    order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return order.get(str(severity).lower(), 2)


def _severity_from_rank(rank: int) -> str:
    reverse = {1: "low", 2: "medium", 3: "high", 4: "critical"}
    return reverse.get(max(1, min(4, rank)), "medium")


@dataclass
class RepairFinding:
    finding_id: str = field(default_factory=lambda: f"finding-{uuid4().hex[:12]}")
    source_kind: str = "invariant"
    source_id: str = ""
    severity: str = "medium"
    status: str = "fail"
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["risk_score"] = _clamp01(data.get("risk_score"))
        return data


@dataclass
class RepairAction:
    action_id: str = field(default_factory=lambda: f"action-{uuid4().hex[:12]}")
    kind: str = "manual_review"
    description: str = ""
    target: str = ""
    expected_effect: str = ""
    validation_steps: List[str] = field(default_factory=list)
    destructive: bool = False
    requires_human_approval: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepairPlan:
    plan_id: str = field(default_factory=lambda: f"repair-{uuid4().hex[:12]}")
    created_at: str = field(default_factory=utc_now_iso)
    objective: str = ""
    status: str = "proposed"
    dry_run: bool = True
    confidence: float = 0.5
    risk_before: float = 0.0
    risk_after_estimate: float = 0.0
    destructive: bool = False
    findings: List[RepairFinding] = field(default_factory=list)
    actions: List[RepairAction] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["confidence"] = _clamp01(data.get("confidence"), default=0.5)
        data["risk_before"] = _clamp01(data.get("risk_before"))
        data["risk_after_estimate"] = _clamp01(data.get("risk_after_estimate"))
        return data


@dataclass
class RepairAssessment:
    generated_at: str
    twin_status: Dict[str, Any]
    invariant_checks: List[InvariantCheck]
    scenario_risks: List[ScenarioRiskEstimate]
    findings: List[RepairFinding]
    plans: List[RepairPlan]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": SELF_REPAIR_PHASE,
            "generated_at": self.generated_at,
            "twin_status": self.twin_status,
            "invariant_checks": [check.to_dict() for check in self.invariant_checks],
            "scenario_risks": [risk.to_dict() for risk in self.scenario_risks],
            "findings": [finding.to_dict() for finding in self.findings],
            "plans": [plan.to_dict() for plan in self.plans],
        }


class SelfRepairEngine:
    """Read-only repair planner for ProjectX world-model failures."""

    def __init__(
        self,
        twin: Optional[WorldModelTwin] = None,
        *,
        dry_run: bool = True,
        max_plans: int = 5,
        max_actions_per_plan: int = 4,
        root: Optional[Path] = None,
    ) -> None:
        self.twin = twin or get_world_twin()
        self.dry_run = dry_run
        self.max_plans = max(1, int(max_plans))
        self.max_actions_per_plan = max(1, int(max_actions_per_plan))
        self.root = root or DEFAULT_SELF_REPAIR_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.assessments_path = self.root / "assessments.jsonl"
        self.plans_path = self.root / "repair_plans.jsonl"
        self._lock = threading.Lock()

    def inspect(self, *, persist: bool = True) -> RepairAssessment:
        self.twin.refresh()
        twin_status = self.twin.status()
        invariant_checks = self.twin.evaluate_invariants(persist_checks=persist)
        scenario_risks = self.twin.scenario_risk_estimates()
        findings = self._build_findings(invariant_checks, scenario_risks)
        plans = self.propose_repair_plans(findings=findings)
        assessment = RepairAssessment(
            generated_at=utc_now_iso(),
            twin_status=twin_status,
            invariant_checks=invariant_checks,
            scenario_risks=scenario_risks,
            findings=findings,
            plans=plans,
        )
        if persist:
            self._record_assessment(assessment)
        return assessment

    def check_invariants(self, *, persist: bool = True) -> List[InvariantCheck]:
        return self.twin.evaluate_invariants(persist_checks=persist)

    def propose_repair_plans(
        self,
        *,
        findings: Optional[List[RepairFinding]] = None,
        max_plans: Optional[int] = None,
    ) -> List[RepairPlan]:
        self.twin.refresh()
        if findings is None:
            findings = self._build_findings(self.twin.evaluate_invariants(), self.twin.scenario_risk_estimates())
        ordered = sorted(
            findings,
            key=lambda item: (item.risk_score, _severity_rank(item.severity)),
            reverse=True,
        )
        plans: List[RepairPlan] = []
        for finding in ordered[: max_plans or self.max_plans]:
            plan = self._plan_for_finding(finding)
            plans.append(plan)
        if not plans:
            plans.append(self._safe_monitoring_plan())
        self._record_plans(plans)
        return plans

    def build_report(self) -> Dict[str, Any]:
        assessment = self.inspect(persist=True)
        return assessment.to_dict()

    def can_apply(self, plan: RepairPlan) -> bool:
        return False if plan.destructive else False

    def apply_plan(self, plan: RepairPlan) -> Dict[str, Any]:
        """Explicitly non-destructive: never mutates files or processes."""
        payload = {
            "plan_id": plan.plan_id,
            "status": "blocked",
            "reason": "destructive changes are disabled in Phase 11 self-repair",
            "dry_run": True,
            "applied": False,
            "plan": plan.to_dict(),
            "timestamp": utc_now_iso(),
        }
        self._append_jsonl(self.assessments_path, {"record_type": "blocked_apply", **payload})
        return payload

    def status(self) -> Dict[str, Any]:
        snapshot = self.twin.snapshot(persist=False)
        return {
            "phase": SELF_REPAIR_PHASE,
            "dry_run": self.dry_run,
            "twin_status": snapshot["risk_summary"],
            "counts": snapshot["counts"],
        }

    def _build_findings(
        self,
        invariant_checks: List[InvariantCheck],
        scenario_risks: List[ScenarioRiskEstimate],
    ) -> List[RepairFinding]:
        findings: List[RepairFinding] = []
        for check in invariant_checks:
            if check.status == "pass":
                continue
            risk_score = self._risk_from_invariant(check)
            recommendation = self._recommendation_for_invariant(check)
            findings.append(
                RepairFinding(
                    source_kind="invariant",
                    source_id=check.invariant_id,
                    severity=check.severity,
                    status=check.status,
                    summary=check.message,
                    details=check.to_dict(),
                    risk_score=risk_score,
                    recommendation=recommendation,
                )
            )

        for scenario in scenario_risks:
            if scenario.risk_score < 0.6:
                continue
            findings.append(
                RepairFinding(
                    source_kind="scenario",
                    source_id=scenario.scenario_id,
                    severity=_severity_from_rank(3 if scenario.risk_score < 0.8 else 4),
                    status="warn",
                    summary=f"Scenario risk elevated for {scenario.name or scenario.scenario_id}",
                    details=scenario.to_dict(),
                    risk_score=scenario.risk_score,
                    recommendation="Increase monitoring, verify upstream invariants, and review mitigations.",
                )
            )
        return findings

    def _plan_for_finding(self, finding: RepairFinding) -> RepairPlan:
        actions: List[RepairAction] = []
        details = dict(finding.details)
        if finding.source_kind == "invariant":
            invariant = details
            condition = str(invariant.get("condition") or "").lower()
            target = str(invariant.get("target_id") or "")
            if condition == "entity_exists":
                actions.append(
                    RepairAction(
                        kind="refresh_entity_source",
                        description=f"Refresh authoritative source for entity {target!r}.",
                        target=target,
                        expected_effect="Entity becomes present in the world model.",
                        validation_steps=[
                            f"Confirm entity {target!r} is present after refresh.",
                            "Recompute invariant checks.",
                        ],
                        destructive=False,
                        requires_human_approval=True,
                    )
                )
            elif condition in {"attribute_equals", "attribute_min", "attribute_max"}:
                actions.append(
                    RepairAction(
                        kind="sync_attribute",
                        description=f"Reconcile attribute {invariant.get('subject_attribute')!r} for {target!r} against the authoritative source.",
                        target=target,
                        expected_effect="Observed attribute matches the invariant expectation.",
                        validation_steps=[
                            "Compare current attribute to source of truth.",
                            "Re-run the invariant check after refresh.",
                        ],
                        destructive=False,
                        requires_human_approval=True,
                    )
                )
            elif condition == "relation_exists":
                actions.append(
                    RepairAction(
                        kind="rebuild_relation",
                        description=f"Rebuild the missing relation described by invariant {finding.source_id}.",
                        target=target,
                        expected_effect="The relation is restored in the graph.",
                        validation_steps=[
                            "Verify both endpoints are still present.",
                            "Confirm the relation appears in the world model.",
                        ],
                        destructive=False,
                        requires_human_approval=True,
                    )
                )
            elif condition in {"relation_count_min", "relation_count_max"}:
                actions.append(
                    RepairAction(
                        kind="review_graph_cardinality",
                        description=f"Review relation cardinality for entity {target!r} and adjust monitoring or projection logic.",
                        target=target,
                        expected_effect="Relation density matches the intended bounded range.",
                        validation_steps=[
                            "Inspect adjacent relations.",
                            "Recompute the invariant check.",
                        ],
                        destructive=False,
                        requires_human_approval=True,
                    )
                )
            else:
                actions.append(
                    RepairAction(
                        kind="manual_review",
                        description=f"Unsupported invariant condition {condition!r}; route to manual review.",
                        target=target,
                        expected_effect="Human triage identifies the correct bounded fix.",
                        validation_steps=["Document the source of truth.", "Approve any follow-up action."],
                        destructive=False,
                        requires_human_approval=True,
                    )
                )
        else:
            actions.append(
                RepairAction(
                    kind="tighten_monitoring",
                    description=f"Increase observability around {finding.source_id} and the affected scenario.",
                    target=finding.source_id,
                    expected_effect="Scenario risk decreases or becomes easier to explain.",
                    validation_steps=[
                        "Capture a fresh world-model snapshot.",
                        "Re-evaluate scenario risk estimates.",
                    ],
                    destructive=False,
                    requires_human_approval=True,
                )
            )

        actions = actions[: self.max_actions_per_plan]
        current_risk = _clamp01(finding.risk_score)
        estimated_drop = 0.15 if finding.severity in {"low", "medium"} else 0.25
        if finding.source_kind == "scenario":
            estimated_drop = 0.10
        after_risk = _clamp01(current_risk - estimated_drop)
        confidence = _clamp01(1.0 - (0.2 * _severity_rank(finding.severity) / 4.0))
        return RepairPlan(
            objective=finding.recommendation or f"Address {finding.summary}",
            status="proposed",
            dry_run=True,
            confidence=confidence,
            risk_before=current_risk,
            risk_after_estimate=after_risk,
            destructive=False,
            findings=[finding],
            actions=actions,
            notes=[
                "Bounded repair only.",
                "No file writes, deletions, restarts, or external side effects are applied.",
            ],
        )

    def _safe_monitoring_plan(self) -> RepairPlan:
        action = RepairAction(
            kind="collect_more_signal",
            description="No invariant failures detected; continue bounded monitoring and periodic snapshots.",
            target="system",
            expected_effect="Maintain visibility without taking action.",
            validation_steps=["Take another snapshot.", "Re-check risk summary."],
            destructive=False,
            requires_human_approval=False,
        )
        return RepairPlan(
            objective="Maintain bounded monitoring",
            status="proposed",
            dry_run=True,
            confidence=0.9,
            risk_before=self.twin.snapshot(persist=False)["risk_summary"]["overall_risk"],
            risk_after_estimate=self.twin.snapshot(persist=False)["risk_summary"]["overall_risk"],
            destructive=False,
            findings=[],
            actions=[action],
            notes=["No repair required; continue monitoring."],
        )

    def _risk_from_invariant(self, check: InvariantCheck) -> float:
        severity_score = {"low": 0.2, "medium": 0.45, "high": 0.75, "critical": 0.95}
        base = severity_score.get(str(check.severity).lower(), 0.45)
        if check.status == "unknown":
            base *= 0.5
        return _clamp01(base)

    def _recommendation_for_invariant(self, check: InvariantCheck) -> str:
        if check.status == "unknown":
            return "Collect more evidence and define the invariant more precisely."
        if check.condition == "entity_exists":
            return "Reconcile the authoritative entity source and rebuild the projection."
        if check.condition in {"attribute_equals", "attribute_min", "attribute_max"}:
            return "Synchronize the observed attribute with the authoritative source."
        if check.condition == "relation_exists":
            return "Restore the missing relation from source records."
        return "Review the invariant and re-run the bounded check."

    def _append_jsonl(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            append_redacted_jsonl(path, payload)

    def _record_assessment(self, assessment: RepairAssessment) -> None:
        self._append_jsonl(self.assessments_path, {"record_type": "assessment", **assessment.to_dict()})

    def _record_plans(self, plans: List[RepairPlan]) -> None:
        for plan in plans:
            self._append_jsonl(self.plans_path, {"record_type": "repair_plan", **plan.to_dict()})


_self_repair_engine: Optional[SelfRepairEngine] = None


def get_self_repair_engine() -> SelfRepairEngine:
    global _self_repair_engine
    if _self_repair_engine is None:
        _self_repair_engine = SelfRepairEngine()
    return _self_repair_engine


def inspect_world_model(*, persist: bool = True) -> Dict[str, Any]:
    return get_self_repair_engine().build_report() if persist else get_self_repair_engine().inspect(persist=False).to_dict()


def propose_repair_plans() -> List[Dict[str, Any]]:
    return [plan.to_dict() for plan in get_self_repair_engine().propose_repair_plans()]


def self_repair_status() -> Dict[str, Any]:
    return get_self_repair_engine().status()


__all__ = [
    "SELF_REPAIR_PHASE",
    "RepairFinding",
    "RepairAction",
    "RepairPlan",
    "RepairAssessment",
    "SelfRepairEngine",
    "get_self_repair_engine",
    "inspect_world_model",
    "propose_repair_plans",
    "self_repair_status",
]
