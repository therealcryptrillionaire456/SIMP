"""Governed recursive-improvement helpers for ProjectX.

The engine plans and evaluates self-improvement proposals while keeping code
changes behind explicit approval and promotion gates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from simp.compat.projectx_contracts import DEFAULT_CONTRACT_LOG, append_contract
from simp.projectx.safety_monitor import SafetyMonitor, get_safety_monitor
from simp.projectx.self_modifier import PatchProposal, SelfModifier
from simp.projectx.validator import AnswerValidator, ValidationReport


@dataclass
class PromotionDecision:
    decision: str
    reasons: List[str] = field(default_factory=list)
    validation_score: float = 0.0
    benchmark_delta: Optional[float] = None
    operator_approval_required: bool = True
    operator_approved: bool = False
    apply_requested: bool = False
    applied: bool = False
    guardrails: Dict[str, Any] = field(default_factory=dict)
    policy_contract_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "validation_score": round(self.validation_score, 4),
            "benchmark_delta": self.benchmark_delta,
            "operator_approval_required": self.operator_approval_required,
            "operator_approved": self.operator_approved,
            "apply_requested": self.apply_requested,
            "applied": self.applied,
            "guardrails": dict(self.guardrails),
            "policy_contract_id": self.policy_contract_id,
        }


class GovernedImprovementEngine:
    """Bounded proposal/eval/promotion workflow for ProjectX code changes."""

    def __init__(
        self,
        *,
        repo_root: Optional[str] = None,
        contract_log_path: Path = DEFAULT_CONTRACT_LOG,
        validator: Optional[AnswerValidator] = None,
        safety_monitor: Optional[SafetyMonitor] = None,
        self_modifier: Optional[SelfModifier] = None,
        validation_threshold: float = 0.55,
    ) -> None:
        self._contract_log_path = Path(contract_log_path)
        self._validation_threshold = float(validation_threshold)
        self._validator = validator or AnswerValidator(threshold=self._validation_threshold)
        self._safety = safety_monitor or get_safety_monitor()
        self._modifier = self_modifier or SelfModifier(
            repo_root=repo_root,
            safety_monitor=self._safety,
        )

    def run_patch_flow(
        self,
        *,
        objective: str,
        target_file: str,
        original_snippet: str,
        patched_snippet: str,
        rationale: str,
        evidence: Optional[Dict[str, Any]] = None,
        benchmark_delta: Optional[float] = None,
        operator_approved: bool = False,
        apply_requested: bool = False,
        run_regression_tests: bool = False,
    ) -> Dict[str, Any]:
        mission_id = f"px-improve-{uuid.uuid4().hex[:10]}"
        emitted_contracts: list[Dict[str, Any]] = []
        evidence = evidence or {}

        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "mission_lifecycle_event",
                    "mission_id": mission_id,
                    "event_type": "mission_created",
                    "status": "planned",
                    "objective": objective,
                    "target_file": target_file,
                }
            )
        )
        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "memory_episode",
                    "mission_id": mission_id,
                    "kind": "improvement_request",
                    "summary": rationale,
                    "objective": objective,
                    "target_file": target_file,
                    "evidence": evidence,
                }
            )
        )

        proposal = self._modifier.propose_patch(
            target_file=target_file,
            original_snippet=original_snippet,
            patched_snippet=patched_snippet,
            rationale=rationale,
        )
        gate_pass_rate = self._gate_pass_rate(proposal)
        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "validation_evidence",
                    "mission_id": mission_id,
                    "validation_id": f"{mission_id}:proposal-gates",
                    "result": "passed" if proposal.all_gates_passed else "failed",
                    "target_file": proposal.target_file,
                    "gate_results": dict(proposal.gate_results),
                    "proposal_id": proposal.proposal_id,
                    "error": proposal.error,
                }
            )
        )
        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "scoreboard_metric",
                    "mission_id": mission_id,
                    "metric_name": "patch_gate_pass_rate",
                    "value": gate_pass_rate,
                    "proposal_id": proposal.proposal_id,
                }
            )
        )

        candidate_summary = (
            f"Objective: {objective}. Rationale: {rationale}. "
            f"Patch summary: {proposal.summary()}."
        )
        validation_report = self._validator.validate(
            question=objective,
            answer=candidate_summary,
            expected_format="prose",
        )
        self._safety.record("eval_score", validation_report.composite_score)
        alerts = [alert.alert_type.value for alert in self._safety.check_alerts()]
        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "validation_evidence",
                    "mission_id": mission_id,
                    "validation_id": f"{mission_id}:summary-validation",
                    "result": "passed" if validation_report.passed else "failed",
                    "validation_score": validation_report.composite_score,
                    "flagged_reasons": validation_report.flagged_reasons,
                    "latency_ms": validation_report.latency_ms,
                }
            )
        )
        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "scoreboard_metric",
                    "mission_id": mission_id,
                    "metric_name": "validation_score",
                    "value": round(validation_report.composite_score, 4),
                    "proposal_id": proposal.proposal_id,
                }
            )
        )
        if benchmark_delta is not None:
            emitted_contracts.append(
                self._append_contract(
                    {
                        "contract_type": "scoreboard_metric",
                        "mission_id": mission_id,
                        "metric_name": "benchmark_delta",
                        "value": benchmark_delta,
                        "proposal_id": proposal.proposal_id,
                    }
                )
            )

        decision = self._decide_promotion(
            proposal=proposal,
            validation_report=validation_report,
            benchmark_delta=benchmark_delta,
            operator_approved=operator_approved,
            apply_requested=apply_requested,
        )
        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "policy_decision",
                    "mission_id": mission_id,
                    "decision": decision.decision,
                    "reasons": decision.reasons,
                    "operator_approved": operator_approved,
                    "apply_requested": apply_requested,
                    "validation_score": round(validation_report.composite_score, 4),
                    "benchmark_delta": benchmark_delta,
                    "proposal_id": proposal.proposal_id,
                    "guardrails": decision.guardrails,
                    "alerts": alerts,
                }
            )
        )
        decision.policy_contract_id = emitted_contracts[-1]["record_id"]
        emitted_contracts.append(
            self._append_contract(
                {
                    "contract_type": "mission_lifecycle_event",
                    "mission_id": mission_id,
                    "event_type": "promotion_decision_recorded",
                    "status": decision.decision,
                    "proposal_id": proposal.proposal_id,
                    "policy_contract_id": decision.policy_contract_id,
                }
            )
        )

        if decision.decision == "approve" and apply_requested:
            proposal.approved = True
            decision.applied = self._modifier.apply(proposal, run_tests=run_regression_tests)
            if not decision.applied:
                decision.decision = "hold"
                decision.reasons.append("Apply step failed; proposal remains held for operator review.")
            emitted_contracts.append(
                self._append_contract(
                    {
                        "contract_type": "mission_lifecycle_event",
                        "mission_id": mission_id,
                        "event_type": "patch_applied" if decision.applied else "patch_apply_failed",
                        "status": "applied" if decision.applied else "hold",
                        "proposal_id": proposal.proposal_id,
                    }
                )
            )

        return {
            "status": "ok",
            "mission_id": mission_id,
            "proposal": proposal.to_dict(),
            "validation": self._validation_payload(validation_report, alerts),
            "decision": decision.to_dict(),
            "contracts_emitted": [record["record_id"] for record in emitted_contracts],
            "guardrails": dict(decision.guardrails),
        }

    def _append_contract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return append_contract(payload, log_path=self._contract_log_path)

    @staticmethod
    def _gate_pass_rate(proposal: PatchProposal) -> float:
        if not proposal.gate_results:
            return 0.0
        passed = sum(1 for ok in proposal.gate_results.values() if ok)
        return round(passed / len(proposal.gate_results), 4)

    def _validation_payload(self, report: ValidationReport, alerts: List[str]) -> Dict[str, Any]:
        return {
            **report.to_dict(),
            "alerts": alerts,
            "threshold": self._validation_threshold,
        }

    def _decide_promotion(
        self,
        *,
        proposal: PatchProposal,
        validation_report: ValidationReport,
        benchmark_delta: Optional[float],
        operator_approved: bool,
        apply_requested: bool,
    ) -> PromotionDecision:
        reasons: list[str] = []
        decision = "hold"
        guardrails = {
            "self_modification_scope": "simp/projectx only",
            "requires_operator_approval": True,
            "requires_non_negative_benchmark_delta": True,
            "requires_gate_passes": True,
            "validation_threshold": self._validation_threshold,
        }

        if self._safety.emergency_stopped:
            reasons.append("Safety monitor emergency stop is active.")
            decision = "deny"
        elif not proposal.all_gates_passed:
            reasons.append("Patch proposal failed one or more modifier gates.")
            if proposal.error:
                reasons.append(proposal.error)
            decision = "deny"
        elif self._safety.is_paused:
            reasons.append("Safety monitor is currently paused pending escalation review.")
            decision = "hold"
        elif validation_report.composite_score < self._validation_threshold:
            reasons.append(
                f"Validation score {validation_report.composite_score:.3f} is below threshold {self._validation_threshold:.3f}."
            )
            decision = "hold"
        elif benchmark_delta is None:
            reasons.append("Benchmark delta evidence is required before promotion.")
            decision = "hold"
        elif benchmark_delta < 0:
            reasons.append(f"Benchmark delta {benchmark_delta:.4f} is negative.")
            decision = "deny"
        elif not operator_approved:
            reasons.append("Operator approval is required before promotion.")
            decision = "hold"
        else:
            reasons.append("Proposal passed gates, validation, and benchmark review.")
            decision = "approve"

        return PromotionDecision(
            decision=decision,
            reasons=reasons,
            validation_score=validation_report.composite_score,
            benchmark_delta=benchmark_delta,
            operator_approval_required=True,
            operator_approved=operator_approved,
            apply_requested=apply_requested,
            guardrails=guardrails,
        )
