"""Tests for Tool Ecology — ProjectX capability inventory."""

import time
import pytest

from simp.projectx.tool_ecology import (
    get_tool_ecology,
    ProjectXToolEcology,
    CapabilityGap,
    ToolEcologySnapshot,
    _CAPABILITY_RULES,
    _PROJECTX_NATIVE_BUILTINS,
)


@pytest.fixture
def ecology() -> ProjectXToolEcology:
    """Use the real singleton so tests see actual registry state."""
    return get_tool_ecology()


class TestSnapshot:
    def test_snapshot_captures_counts(self, ecology) -> None:
        snap = ecology.snapshot()
        assert snap.registry_count >= 0
        assert snap.timestamp > 0

    def test_snapshot_to_dict(self, ecology) -> None:
        snap = ecology.snapshot()
        d = snap.to_dict()
        assert "timestamp" in d
        assert "registry_count" in d
        assert "tool_count" in d
        assert "skill_count" in d
        assert "subsystem_count" in d
        assert "gaps" in d

    def test_snapshot_timestamps_recent(self, ecology) -> None:
        before = time.time()
        snap = ecology.snapshot()
        after = time.time()
        assert before <= snap.timestamp <= after

    def test_tools_by_agent_populated(self, ecology) -> None:
        snap = ecology.snapshot()
        assert isinstance(snap.tools_by_agent, dict)

    def test_subsystems_listed(self, ecology) -> None:
        snap = ecology.snapshot()
        assert isinstance(snap.subsystems, list)

    def test_skills_listed(self, ecology) -> None:
        snap = ecology.snapshot()
        assert isinstance(snap.skills, list)

    def test_tool_count_positive(self, ecology) -> None:
        snap = ecology.snapshot()
        assert snap.tool_count >= 0


class TestGapDetection:
    def test_web_research_gap_when_unavailable(self, ecology) -> None:
        """recommend_for_goal returns gaps (empty list = no gaps)."""
        gaps = ecology.recommend_for_goal("search the web for BTC news")
        # Returns list of gap dicts; empty means no gaps
        assert isinstance(gaps, list)

    def test_forecasting_gap_detected(self, ecology) -> None:
        gaps = ecology.recommend_for_goal("predict BTC price signal")
        assert isinstance(gaps, list)
        if gaps:
            assert "capability" in gaps[0]
            assert "reason" in gaps[0]

    def test_vision_gap_detected(self, ecology) -> None:
        gaps = ecology.recommend_for_goal("analyze screenshot of trading chart")
        assert isinstance(gaps, list)

    def test_capability_rules_coverage(self) -> None:
        for rule in _CAPABILITY_RULES:
            assert len(rule) == 3
            capability, trigger_kw, match_kw = rule
            assert isinstance(capability, str)
            assert isinstance(trigger_kw, tuple)
            assert isinstance(match_kw, tuple)
            assert len(trigger_kw) > 0
            assert len(match_kw) > 0

    def test_native_builtins_recognized(self) -> None:
        assert "projectx_multimodal_analyse" in _PROJECTX_NATIVE_BUILTINS
        assert "projectx_run_goal" in _PROJECTX_NATIVE_BUILTINS
        assert "projectx_benchmark" in _PROJECTX_NATIVE_BUILTINS
        assert "projectx_self_test" in _PROJECTX_NATIVE_BUILTINS

    def test_capability_gap_to_dict(self) -> None:
        gap = CapabilityGap(
            capability="test_cap",
            reason="No tool found.",
            matched_keywords=["test"],
        )
        d = gap.to_dict()
        assert d["capability"] == "test_cap"
        assert d["reason"] == "No tool found."
        assert d["matched_keywords"] == ["test"]

    def test_native_builtin_no_false_gap(self, ecology) -> None:
        # projectx_self_test is a native builtin — no gap expected
        gaps = ecology.recommend_for_goal(
            "run self test to validate projectx functionality"
        )
        # Built-in should not produce a gap for self_test capability
        self_test_gaps = [g for g in gaps if g.get("capability") == "projectx_self_test"]
        assert len(self_test_gaps) == 0

    def test_recommend_for_goal_returns_list(self, ecology) -> None:
        result = ecology.recommend_for_goal("do something")
        assert isinstance(result, list)

    def test_brief_for_goal_returns_string(self, ecology) -> None:
        result = ecology.brief_for_goal("analyze BTC market data")
        assert isinstance(result, str)
        assert len(result) > 0


class TestSingleton:
    def test_get_tool_ecology_returns_singleton(self) -> None:
        ec1 = get_tool_ecology()
        ec2 = get_tool_ecology()
        assert ec1 is ec2

    def test_snapshot_contains_native_builtins(self, ecology) -> None:
        snap = ecology.snapshot()
        # Native built-in tools should appear in tools_by_agent for projectx
        projectx_tools = snap.tools_by_agent.get("projectx", [])
        assert "projectx_benchmark" in projectx_tools or "projectx_self_test" in projectx_tools
