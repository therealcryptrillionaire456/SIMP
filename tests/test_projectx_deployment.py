from __future__ import annotations

from types import SimpleNamespace

from simp.projectx.deployment import ProjectXDeploymentManager


class _DummyOrchestrator:
    def __init__(self) -> None:
        self._executor = lambda system, user: f"exec::{user}"

    def run(self, goal: str, context: str | None = None):
        return SimpleNamespace(to_dict=lambda: {"goal": goal, "success": True})

    def self_improve(self):
        return {"status": "ok"}

    def get_status(self):
        return {"status": "ok", "tool_ecology": {"tool_count": 8}}


def test_deployment_manager_reports_ready_when_checks_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        "simp.projectx.deployment.run_self_test",
        lambda fast=True: SimpleNamespace(to_dict=lambda: {"passed": True, "passed_count": 3}),
    )
    monkeypatch.setattr(
        "simp.projectx.deployment.BenchmarkRunner.run",
        lambda self, executor, domains=None: SimpleNamespace(to_dict=lambda: {"overall_score": 0.75}),
    )
    monkeypatch.setattr(
        "simp.projectx.deployment.BenchmarkRunner.history_summary",
        lambda self, limit=5: SimpleNamespace(
            to_dict=lambda: {
                "history_path": "projectx_logs/benchmark_history.jsonl",
                "run_count": 2,
                "latest_score": 0.75,
                "best_score": 0.75,
                "trend_ratio": 1.05,
                "latest_executor_id": "dummy",
                "recent_runs": [{"overall_score": 0.71}, {"overall_score": 0.75}],
            }
        ),
    )

    manager = ProjectXDeploymentManager(orchestrator=_DummyOrchestrator())
    report = manager.readiness_report(fast=True)

    assert report.status == "ready"
    assert report.tool_suite["tool_count"] >= 8
    assert all(artifact.exists for artifact in report.artifacts)
    assert report.benchmark_history["run_count"] == 2
    assert report.manifest_validation["status"] == "valid"
    assert report.missing_requirements == []


def test_deployment_manifest_validation_reports_valid_bundle() -> None:
    report = ProjectXDeploymentManager.validate_manifests()

    assert report.status == "valid"
    assert report.checks["deployment_kind"] is True
    assert report.checks["service_target_port"] is True
    assert report.checks["hpa_cpu_metric"] is True
