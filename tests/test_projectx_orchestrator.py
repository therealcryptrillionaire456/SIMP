from __future__ import annotations

from types import SimpleNamespace

from simp.projectx.resource_monitor import ResourceSnapshot, ThrottleSignal


class _DummyResourceMonitor:
    def __init__(self, should_throttle: bool = False) -> None:
        self._should_throttle = should_throttle

    def check_throttle(self) -> None:
        if self._should_throttle:
            raise ThrottleSignal("CPU critical: 99.0%", ResourceSnapshot(cpu_percent=99.0))

    def latest(self):
        return None


class _DummySafety:
    emergency_stopped = False
    is_paused = False

    def record(self, *args, **kwargs) -> None:
        return None

    def check_alerts(self):
        return []

    def get_summary(self):
        return {"status": "ok"}


class _DummyTelemetry:
    def collect(self) -> None:
        return None


class _DummyMeshIntel:
    def route(self, goal: str):
        return None

    def record_call(self, agent_id: str, latency_ms: float = 0.0, error: bool = False) -> None:
        return None

    def recommend_rebalance(self):
        return []

    def topology(self):
        return {"total_agents": 0}


class _DummySpawner:
    def list_agents(self):
        return []

    def route_task(self, goal: str):
        return None


class _DummyDistiller:
    def get_top(self, n: int = 20):
        return []

    def run(self, top_n: int = 100, min_signal: float = 0.3):
        return SimpleNamespace(
            fragments=[],
            to_dict=lambda: {"fragments_out": 0},
        )

    def inject_into_rag(self, fragments=None):
        return 0


class _DummyMetaLearner:
    def run_cycle(self):
        return SimpleNamespace(to_dict=lambda: {"episodes_recorded": 0})


class _DummyEvolutionTracker:
    def track_cycle(self, **kwargs):
        return SimpleNamespace(
            trend="flat",
            on_track_for_2x=False,
            targets_met=[],
            week_over_week=1.0,
        )

    def get_dashboard_data(self):
        return {"trend": "flat"}


def _patch_orchestrator_runtime(monkeypatch, should_throttle: bool = False) -> None:
    monkeypatch.setattr(
        "simp.projectx.orchestrator.get_resource_monitor",
        lambda auto_start=True: _DummyResourceMonitor(should_throttle=should_throttle),
    )
    monkeypatch.setattr("simp.projectx.orchestrator.get_safety_monitor", lambda: _DummySafety())
    monkeypatch.setattr("simp.projectx.orchestrator.get_telemetry_collector", lambda auto_start=True: _DummyTelemetry())
    monkeypatch.setattr("simp.projectx.orchestrator.get_mesh_intelligence", lambda auto_start=True: _DummyMeshIntel())
    monkeypatch.setattr("simp.projectx.orchestrator.get_agent_spawner", lambda: _DummySpawner())
    monkeypatch.setattr("simp.projectx.orchestrator.get_knowledge_distiller", lambda: _DummyDistiller())
    monkeypatch.setattr("simp.projectx.orchestrator.get_evolution_tracker", lambda: _DummyEvolutionTracker())


def test_orchestrator_run_records_subtask_results(monkeypatch) -> None:
    _patch_orchestrator_runtime(monkeypatch)

    from simp.projectx.orchestrator import ProjectXOrchestrator

    orchestrator = ProjectXOrchestrator(executor=lambda system, user: f"response::{user}")
    orchestrator._meta_learner = _DummyMetaLearner()
    orchestrator._benchmark.improvement_trend = lambda last_n=10: 1.05
    orchestrator._plan = lambda goal, context, memory_ctx: [
        {"agent": "analysis", "task": "Summarize the current state"},
        {"agent": "creative", "task": "Suggest one improvement"},
    ]
    orchestrator._synthesise = lambda goal, outputs: "\n".join(outputs)
    orchestrator._validator.validate = lambda goal, output: SimpleNamespace(
        composite_score=0.91,
        passed=True,
        flagged_reasons=[],
    )

    result = orchestrator.run("Improve ProjectX routing")

    assert result.success is True
    assert result.validated is True
    assert len(result.subtask_results) == 2
    assert all(entry["success"] is True for entry in result.subtask_results)
    status = orchestrator.get_status()
    assert "tool_ecology" in status
    assert status["benchmark_trend"] == 1.05


def test_orchestrator_handles_pre_pipeline_throttle(monkeypatch) -> None:
    _patch_orchestrator_runtime(monkeypatch, should_throttle=True)

    from simp.projectx.orchestrator import ProjectXOrchestrator

    orchestrator = ProjectXOrchestrator(executor=lambda system, user: user)
    result = orchestrator.run("Trigger the resource guard")

    assert result.success is False
    assert "Resource throttle" in (result.error or "")


def test_orchestrator_self_improve_reports_apo_backends(monkeypatch) -> None:
    _patch_orchestrator_runtime(monkeypatch)

    from simp.projectx.orchestrator import ProjectXOrchestrator

    orchestrator = ProjectXOrchestrator(executor=lambda system, user: user)
    orchestrator._meta_learner = _DummyMetaLearner()
    orchestrator._benchmark.run = lambda executor, domains=None: SimpleNamespace(
        to_dict=lambda: {"overall_score": 0.74, "domains": domains or []}
    )
    orchestrator._benchmark.improvement_trend = lambda last_n=10: 1.12
    orchestrator._memory.prune_expired = lambda: 2
    orchestrator._computer.check_protocol_health = lambda: {"status": "ok"}
    orchestrator._apo.optimize = lambda scorer, steps: None
    orchestrator._apo.report = lambda: {"best_score": 0.81, "generation": 3}
    orchestrator._apo.optimize_prompt_knobs = lambda scorer, backend, iterations: {
        "backend": backend,
        "best_score": 0.72 if backend == "bayesian" else 0.76,
        "iterations": iterations,
        "candidate_id": f"{backend}-candidate",
    }

    report = orchestrator.self_improve()

    assert report["apo_report"]["best_score"] == 0.81
    assert [entry["backend"] for entry in report["apo_backends"]] == ["bayesian", "evolutionary"]
    assert report["benchmark"]["trend"] == 1.12
