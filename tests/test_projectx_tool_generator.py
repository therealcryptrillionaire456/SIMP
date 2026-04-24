from __future__ import annotations

from simp.mcp.tool_registry import ToolRegistry
from simp.projectx.tool_generator import get_dynamic_tool_creator


def test_dynamic_tool_creator_is_stable_per_agent() -> None:
    creator_a1 = get_dynamic_tool_creator("projectx_dynamic_a")
    creator_a2 = get_dynamic_tool_creator("projectx_dynamic_a")
    creator_b = get_dynamic_tool_creator("projectx_dynamic_b")

    assert creator_a1 is creator_a2
    assert creator_a1 is not creator_b


def test_dynamic_tool_creator_registers_and_runs_summarize_tool() -> None:
    agent_id = "projectx_dynamic_summary"
    creator = get_dynamic_tool_creator(agent_id)

    result = creator.register_tool("summarize incident items", name_hint="incident_summary")
    registry = ToolRegistry.get_registry(agent_id)

    assert result["status"] == "success"
    assert registry is not None

    tool_result = registry.call_tool(
        "incident_summary",
        items=["alpha event", "beta event", "gamma event"],
        max_items=2,
    )

    assert tool_result["count"] == 3
    assert "alpha event" in tool_result["summary"]
    assert "gamma event" not in tool_result["summary"]


def test_dynamic_tool_creator_registers_threshold_filter_tool() -> None:
    agent_id = "projectx_dynamic_filter"
    creator = get_dynamic_tool_creator(agent_id)

    creator.register_tool("filter records above threshold", name_hint="high_scores")
    registry = ToolRegistry.get_registry(agent_id)

    tool_result = registry.call_tool(
        "high_scores",
        items=[
            {"symbol": "AAA", "score": 0.42},
            {"symbol": "BBB", "score": 0.91},
            {"symbol": "CCC", "score": "bad"},
        ],
        field="score",
        min_value=0.5,
    )

    assert tool_result["count"] == 1
    assert tool_result["items"][0]["symbol"] == "BBB"
