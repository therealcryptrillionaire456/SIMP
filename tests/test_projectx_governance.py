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

def test_apo_auto_apply_triggers_without_operator_approval(tmp_path, monkeypatch) -> None:
    """When APO_AUTO_APPLY=true, a passing proposal auto-triggers apply."""
    import os
    monkeypatch.setenv("APO_AUTO_APPLY", "true")
    # Force reload of governance module to pick up env var
    import importlib
    import simp.projectx.governance as gov_module
    importlib.reload(gov_module)

    contract_log_path = tmp_path / "projectx_contracts.jsonl"
    engine = gov_module.GovernedImprovementEngine(
        contract_log_path=contract_log_path,
        safety_monitor=SafetyMonitor(SafetyConfig(escalation_pause_seconds=1.0)),
    )

    result = engine.run_patch_flow(
        objective="Minor benchmark improvement via threshold nudge",
        target_file="simp/projectx/validator.py",
        original_snippet="VALIDATION_THRESHOLD = 0.55",
        patched_snippet="VALIDATION_THRESHOLD = 0.551",
        rationale="Minor tweak for test.",
        evidence={"source": "test"},
        benchmark_delta=0.01,
        operator_approved=False,   # no operator approval
        apply_requested=False,     # no explicit apply request
    )

    assert result["status"] == "ok"
    # Should be approved because APO_AUTO_APPLY=true and thresholds met
    assert result["decision"]["decision"] == "approve", f"Got: {result['decision']['reasons']}"
    # Apply should have been auto-triggered
    assert result["decision"]["apply_requested"] is True, "apply_requested should be True via auto-apply"
    assert result["decision"]["applied"] is True, "patch should be applied when approved"
    # Check for auto_apply_triggered contract
    summary = contract_summary(log_path=contract_log_path)
    assert summary["counts"].get("mission_lifecycle_event", 0) >= 4


def test_apo_auto_apply_uses_benchmark_delta_guardrail(tmp_path, monkeypatch) -> None:
    """APO auto-apply still denies negative benchmark delta."""
    import os
    monkeypatch.setenv("APO_AUTO_APPLY", "true")
    import importlib
    import simp.projectx.governance as gov_module
    importlib.reload(gov_module)

    contract_log_path = tmp_path / "projectx_contracts2.jsonl"
    engine = gov_module.GovernedImprovementEngine(
        contract_log_path=contract_log_path,
        safety_monitor=SafetyMonitor(SafetyConfig(escalation_pause_seconds=1.0)),
    )

    result = engine.run_patch_flow(
        objective="Regression attempt",
        target_file="simp/projectx/validator.py",
        original_snippet="VALIDATION_THRESHOLD = 0.55",
        patched_snippet="VALIDATION_THRESHOLD = 0.4",
        rationale="Attempt to lower threshold.",
        evidence={"source": "test"},
        benchmark_delta=-0.1,   # regression
        operator_approved=False,
        apply_requested=False,
    )

    assert result["decision"]["decision"] == "deny"
    assert any("negative" in r.lower() for r in result["decision"]["reasons"])


def test_apo_auto_apply_requires_validation_threshold(tmp_path, monkeypatch) -> None:
    """APO auto-apply requires validation score to meet threshold."""
    import os
    monkeypatch.setenv("APO_AUTO_APPLY", "true")
    import importlib
    import simp.projectx.governance as gov_module
    import simp.projectx.validator as validator_module
    importlib.reload(gov_module)

    # Monkeypatch the validator to always return a composite_score below 0.9
    original_validate = validator_module.AnswerValidator.validate
    def _fake_validate(self, *args, **kwargs):
        class FakeReport:
            passed = False
            composite_score = 0.3  # deliberately low
            latency_ms = 1
            flagged_reasons = []
            to_dict = lambda s: {"passed": False, "composite_score": 0.3}
        return FakeReport()
    monkeypatch.setattr(validator_module.AnswerValidator, "validate", _fake_validate)

    contract_log_path = tmp_path / "projectx_contracts3.jsonl"
    engine = gov_module.GovernedImprovementEngine(
        contract_log_path=contract_log_path,
        safety_monitor=SafetyMonitor(SafetyConfig(escalation_pause_seconds=1.0)),
        validation_threshold=0.9,
    )

    result = engine.run_patch_flow(
        objective="Change that will not pass high validation threshold",
        target_file="simp/projectx/validator.py",
        original_snippet="VALIDATION_THRESHOLD = 0.55",
        patched_snippet="VALIDATION_THRESHOLD = 0.56",
        rationale="Nudge.",
        evidence={"source": "test"},
        benchmark_delta=0.01,
        operator_approved=False,
        apply_requested=False,
    )

    assert result["decision"]["decision"] in ("hold", "deny"), f"Got: {result['decision']['decision']} — validation score was forced to 0.3, should not approve"

