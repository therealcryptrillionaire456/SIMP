from __future__ import annotations

from types import SimpleNamespace

from simp.mcp.tool_registry import ToolRegistry
from simp.projectx.tool_factory import ProjectXToolFactory


class _DummyOrchestrator:
    def __init__(self) -> None:
        self._executor = lambda system, user: f"exec::{user}"

    def run(self, goal: str, context: str | None = None):
        return SimpleNamespace(to_dict=lambda: {"goal": goal, "context": context, "success": True})

    def self_improve(self):
        return {"status": "ok", "cycle": "dummy"}

    def get_status(self):
        return {"status": "ok", "runtime": "dummy"}


def test_tool_factory_registers_default_projectx_suite() -> None:
    agent_id = "projectx_tool_factory_test"
    factory = ProjectXToolFactory(orchestrator=_DummyOrchestrator(), agent_id=agent_id)

    report = factory.ensure_default_tools()
    registry = ToolRegistry.get_registry(agent_id)

    assert registry is not None
    assert report.tool_count >= 8
    assert "projectx_run_goal" in report.tool_names
    assert "projectx_multimodal_analyse" in report.tool_names


def test_registered_projectx_tool_is_callable() -> None:
    agent_id = "projectx_tool_factory_call_test"
    factory = ProjectXToolFactory(orchestrator=_DummyOrchestrator(), agent_id=agent_id)
    factory.ensure_default_tools()
    registry = ToolRegistry.get_registry(agent_id)

    result = registry.call_tool("projectx_run_goal", goal="Ship readiness proof", context="now")

    assert result["success"] is True
    assert result["goal"] == "Ship readiness proof"
