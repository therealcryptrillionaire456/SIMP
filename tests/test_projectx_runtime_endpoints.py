from __future__ import annotations

from types import SimpleNamespace

import pytest

from simp.mcp.tool_registry import ToolRegistry
from simp.server.http_server import SimpHttpServer


class _DummyApo:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def report(self) -> dict[str, object]:
        return {
            "generation": 2,
            "best_score": 0.82,
            "backend_reports": [{"backend": "bayesian", "best_score": 0.79}],
        }

    def optimize_prompt_knobs(self, scorer, *, backend: str = "bayesian", iterations: int = 8):
        score = scorer(f"{backend} prompt candidate")
        report = {
            "backend": backend,
            "best_score": round(float(score), 4),
            "iterations": iterations,
            "candidate_id": f"{backend}-candidate",
        }
        self.calls.append(report)
        return report


class _DummyOrchestrator:
    def __init__(self) -> None:
        self._apo = _DummyApo()
        self._benchmark = SimpleNamespace(
            history_summary=lambda limit=5: SimpleNamespace(
                to_dict=lambda: {
                    "history_path": "projectx_logs/benchmark_history.jsonl",
                    "run_count": 3,
                    "latest_score": 0.77,
                    "best_score": 0.81,
                    "trend_ratio": 1.12,
                    "latest_executor_id": "projectx_orchestrator",
                    "recent_runs": [
                        {"overall_score": 0.69},
                        {"overall_score": 0.74},
                        {"overall_score": 0.77},
                    ][:limit],
                }
            )
        )

    def get_status(self):
        return {
            "memory_entries": 4,
            "apo": self._apo.report(),
            "tool_ecology": {"tool_count": 10},
        }

    def run(self, goal: str, context: str | None = None):
        return SimpleNamespace(success=True, validation_score=0.73, goal=goal, context=context)


class _DummyDeploymentManager:
    def readiness_report(self, fast: bool = True):
        return SimpleNamespace(
            to_dict=lambda: {
                "status": "ready",
                "tool_suite": {"tool_count": 10},
                "benchmark": {"overall_score": 0.77},
                "benchmark_history": {"run_count": 3, "trend_ratio": 1.12},
                "manifest_validation": {"status": "valid", "checks": {"deployment_kind": True}},
                "runtime_status": {"tool_ecology": {"tool_count": 10}},
                "fast": fast,
            }
        )


class _DummyToolFactory:
    def ensure_default_tools(self):
        return SimpleNamespace(
            to_dict=lambda: {
                "agent_id": "projectx",
                "tool_count": 10,
                "tool_names": ["projectx_run_goal", "projectx_generate_tool"],
            }
        )


class _DummyCollector:
    def __init__(self) -> None:
        self.collect_calls = 0

    def collect(self) -> None:
        self.collect_calls += 1

    def render(self) -> str:
        return (
            "# HELP projectx_test_metric test metric\n"
            "# TYPE projectx_test_metric gauge\n"
            "projectx_test_metric 1\n"
        )


@pytest.fixture
def projectx_client(monkeypatch):
    monkeypatch.setenv("SIMP_REQUIRE_API_KEY", "false")
    server = SimpHttpServer(debug=False)
    orchestrator = _DummyOrchestrator()
    collector = _DummyCollector()
    server._get_projectx_orchestrator = lambda: orchestrator
    server._get_projectx_deployment_manager = lambda: _DummyDeploymentManager()
    server._get_projectx_tool_factory = lambda: _DummyToolFactory()
    monkeypatch.setattr(
        "simp.projectx.telemetry.get_telemetry_collector",
        lambda auto_start=True: collector,
    )
    return server.app.test_client(), orchestrator, collector


def test_projectx_runtime_and_readiness_endpoints(projectx_client) -> None:
    client, _, _ = projectx_client

    runtime_resp = client.get("/projectx/runtime/status")
    readiness_resp = client.get("/projectx/deployment/readiness?fast=false")
    validation_resp = client.get("/projectx/deployment/validate")
    history_resp = client.get("/projectx/benchmark/history?limit=3")
    tools_resp = client.get("/projectx/tools/status")

    assert runtime_resp.status_code == 200
    assert readiness_resp.status_code == 200
    assert validation_resp.status_code == 200
    assert history_resp.status_code == 200
    assert tools_resp.status_code == 200
    assert runtime_resp.get_json()["runtime"]["tool_ecology"]["tool_count"] == 10
    assert readiness_resp.get_json()["fast"] is False
    assert readiness_resp.get_json()["benchmark_history"]["run_count"] == 3
    assert validation_resp.get_json()["validation"]["status"] == "valid"
    assert history_resp.get_json()["history"]["trend_ratio"] == 1.12
    assert tools_resp.get_json()["tools"]["tool_count"] == 10


def test_projectx_apo_endpoints(projectx_client) -> None:
    client, orchestrator, _ = projectx_client

    report_resp = client.get("/projectx/apo/report")
    optimize_resp = client.post(
        "/projectx/apo/optimize",
        json={"backend": "evolutionary", "iterations": 6},
    )

    assert report_resp.status_code == 200
    assert report_resp.get_json()["apo"]["backend_reports"][0]["backend"] == "bayesian"
    assert optimize_resp.status_code == 200
    payload = optimize_resp.get_json()["optimization"]
    assert payload["backend"] == "evolutionary"
    assert payload["iterations"] == 6
    assert orchestrator._apo.calls[-1]["backend"] == "evolutionary"


def test_projectx_tool_generation_and_metrics_endpoints(projectx_client) -> None:
    client, _, collector = projectx_client

    tool_name = "runtime_counter_tool"
    generate_resp = client.post(
        "/projectx/tools/generate",
        json={"requirement": "count structured items", "name_hint": tool_name},
    )
    metrics_resp = client.get("/projectx/metrics")

    assert generate_resp.status_code == 200
    registry = ToolRegistry.get_registry("projectx")
    assert registry is not None
    assert registry.call_tool(tool_name, items=[{"id": 1}, {"id": 2}, {"id": 3}])["count"] == 3

    assert metrics_resp.status_code == 200
    assert collector.collect_calls == 1
    assert "projectx_test_metric 1" in metrics_resp.get_data(as_text=True)
    assert metrics_resp.headers["Content-Type"].startswith("text/plain; version=0.0.4")
