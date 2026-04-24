from __future__ import annotations

from simp.mcp.tool_registry import TOOL_REGISTRIES, ToolRegistry
from simp.mcp.tool_schema import SimpMCPTool
from simp.projectx.tool_ecology import ProjectXToolEcology


def test_tool_registry_supports_global_lookup_and_kwargs_calls() -> None:
    registry = ToolRegistry(agent_id="projectx_tool_ecology_test")
    registry.register(
        SimpMCPTool(
            name="echo_tool",
            description="Echo a payload",
            input_schema={},
            handler=lambda text="": {"text": text},
        )
    )

    assert ToolRegistry.get_registry("projectx_tool_ecology_test") is registry
    assert TOOL_REGISTRIES["projectx_tool_ecology_test"] is registry
    assert registry.call_tool("echo_tool", text="hello") == {"text": "hello"}


def test_tool_ecology_reports_capability_gaps_from_runtime_inventory() -> None:
    ecology = ProjectXToolEcology()

    snapshot = ecology.snapshot("inspect this screenshot and explain the UI layout")

    assert snapshot.subsystem_count >= 5
    if any(gap.capability == "vision" for gap in snapshot.gaps):
        assert False, "vision capability gap should be closed by the ProjectX multimodal tool suite"
