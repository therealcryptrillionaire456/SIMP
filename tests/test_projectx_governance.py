from __future__ import annotations

from simp.compat.projectx_contracts import contract_summary
from simp.projectx.governance import GovernedImprovementEngine
from simp.projectx.safety_monitor import SafetyConfig, SafetyMonitor


def test_governed_improvement_holds_without_benchmark(tmp_path) -> None:
    contract_log_path = tmp_path / "projectx_contracts.jsonl"
    engine = GovernedImprovementEngine(
        contract_log_path=contract_log_path,
        safety_monitor=SafetyMonitor(SafetyConfig(escalation_pause_seconds=1.0)),
    )

    result = engine.run_patch_flow(
        objective="Clamp ProjectX validator threshold safely",
        target_file="simp/projectx/validator.py",
        original_snippet="VALIDATION_THRESHOLD = 0.55",
        patched_snippet="VALIDATION_THRESHOLD = 0.56",
        rationale="Tighten the default validator threshold slightly.",
        evidence={"source": "test"},
    )

    assert result["status"] == "ok"
    assert result["decision"]["decision"] == "hold"
    assert "Benchmark delta evidence is required before promotion." in result["decision"]["reasons"]
    summary = contract_summary(log_path=contract_log_path)
    assert summary["counts"]["mission_lifecycle_event"] >= 2
    assert summary["counts"]["validation_evidence"] >= 2
    assert summary["counts"]["policy_decision"] >= 1
    assert summary["counts"]["memory_episode"] >= 1
    assert summary["counts"]["scoreboard_metric"] >= 2


def test_governed_improvement_approves_with_operator_and_positive_benchmark(tmp_path) -> None:
    contract_log_path = tmp_path / "projectx_contracts.jsonl"
    engine = GovernedImprovementEngine(
        contract_log_path=contract_log_path,
        safety_monitor=SafetyMonitor(SafetyConfig(escalation_pause_seconds=1.0)),
    )

    result = engine.run_patch_flow(
        objective="Slightly increase the validator threshold for prose validation",
        target_file="simp/projectx/validator.py",
        original_snippet="VALIDATION_THRESHOLD = 0.55",
        patched_snippet="VALIDATION_THRESHOLD = 0.551",
        rationale="Slightly increase the validator threshold for prose validation.",
        evidence={"source": "operator"},
        benchmark_delta=0.02,
        operator_approved=True,
        apply_requested=False,
    )

    assert result["decision"]["decision"] == "approve"
    assert result["decision"]["operator_approved"] is True
    assert result["decision"]["applied"] is False
    assert result["proposal"]["gate_results"]["scope"] is True
