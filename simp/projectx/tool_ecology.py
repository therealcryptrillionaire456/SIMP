"""
ProjectX Tool Ecology

Bounded capability inventory and gap detection for the ProjectX runtime.
This does not create tools on its own; it surfaces what already exists
across MCP registries, skills, and subsystems so the orchestrator can
plan around concrete runtime capabilities.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class CapabilityGap:
    capability: str
    reason: str
    matched_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "reason": self.reason,
            "matched_keywords": list(self.matched_keywords),
        }


@dataclass
class ToolEcologySnapshot:
    timestamp: float
    registry_count: int
    tool_count: int
    skill_count: int
    subsystem_count: int
    tools_by_agent: Dict[str, List[str]] = field(default_factory=dict)
    skills: List[str] = field(default_factory=list)
    subsystems: List[str] = field(default_factory=list)
    gaps: List[CapabilityGap] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "registry_count": self.registry_count,
            "tool_count": self.tool_count,
            "skill_count": self.skill_count,
            "subsystem_count": self.subsystem_count,
            "tools_by_agent": self.tools_by_agent,
            "skills": self.skills,
            "subsystems": self.subsystems,
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


_CAPABILITY_RULES: Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    ("web_research", ("search", "research", "web", "url", "http"), ("web", "crawl", "search", "research")),
    ("vision", ("image", "vision", "screenshot", "ocr", "screen", "ui"), ("vision", "image", "screen", "ocr", "multimodal")),
    ("tool_calling", ("tool", "mcp", "function", "api"), ("tool", "mcp", "api")),
    ("forecasting", ("forecast", "prediction", "signal", "timesfm", "market"), ("forecast", "predict", "signal", "timesfm", "market")),
    ("code_execution", ("code", "patch", "python", "refactor", "debug"), ("code", "python", "patch", "debug", "review")),
)

_PROJECTX_NATIVE_BUILTINS: Dict[str, Tuple[str, ...]] = {
    "projectx_multimodal_analyse": (
        "multimodal",
        "vision",
        "image",
        "screen",
        "ocr",
        "audio",
        "video",
        "ui",
    ),
    "projectx_run_goal": ("planning", "execution", "goal"),
    "projectx_benchmark": ("benchmark", "evaluation", "metrics"),
    "projectx_self_test": ("self-test", "validation"),
    "projectx_tool_inventory": ("tool", "inventory", "capability"),
    "projectx_deployment_readiness": ("deployment", "readiness", "release"),
    "projectx_optimize_prompt": ("optimization", "prompt", "apo"),
    "projectx_generate_tool": ("tool", "generation", "native"),
}


class ProjectXToolEcology:
    """Inventory ProjectX runtime capabilities and detect obvious gaps."""

    def snapshot(self, goal: Optional[str] = None) -> ToolEcologySnapshot:
        tools_by_agent, tool_tokens = self._collect_tool_registries()
        skills = self._collect_skills()
        subsystems = self._collect_subsystems()
        searchable = self._searchable_tokens(tools_by_agent, skills, subsystems, tool_tokens)
        gaps = self._detect_gaps(goal or "", searchable)
        tool_count = sum(len(names) for names in tools_by_agent.values())
        return ToolEcologySnapshot(
            timestamp=time.time(),
            registry_count=len(tools_by_agent),
            tool_count=tool_count,
            skill_count=len(skills),
            subsystem_count=len(subsystems),
            tools_by_agent=tools_by_agent,
            skills=skills,
            subsystems=subsystems,
            gaps=gaps,
        )

    def recommend_for_goal(self, goal: str) -> List[Dict[str, Any]]:
        return [gap.to_dict() for gap in self.snapshot(goal).gaps]

    def brief_for_goal(self, goal: str) -> str:
        snapshot = self.snapshot(goal)
        lines = []
        if snapshot.tool_count:
            lines.append(
                "Available tools: "
                + ", ".join(sorted({name for names in snapshot.tools_by_agent.values() for name in names})[:12])
            )
        if snapshot.skills:
            lines.append("Loaded skills: " + ", ".join(snapshot.skills[:8]))
        if snapshot.gaps:
            lines.append(
                "Capability gaps: "
                + "; ".join(f"{gap.capability} ({', '.join(gap.matched_keywords)})" for gap in snapshot.gaps[:4])
            )
        return "\n".join(lines)

    def _collect_tool_registries(self) -> Tuple[Dict[str, List[str]], List[str]]:
        tools_by_agent: Dict[str, List[str]] = {}
        tool_tokens: List[str] = []
        try:
            from simp.mcp.tool_registry import ToolRegistry

            registries = ToolRegistry.all_registries()
            tools_by_agent = {
                agent_id: sorted(registry.tool_names())
                for agent_id, registry in sorted(registries.items())
            }
            for registry in registries.values():
                try:
                    for tool in registry.list_tools():
                        tool_tokens.extend(
                            token
                            for token in (
                                tool.name,
                                tool.description,
                                tool.intent_type,
                                tool.execution_class,
                                tool.invocation_mode,
                            )
                            if token
                        )
                except Exception:
                    continue
        except Exception:
            tools_by_agent = {}

        # ProjectX has a native built-in tool suite even before a specific
        # runtime has registered all tools into a live registry.
        for tool_name, builtin_terms in _PROJECTX_NATIVE_BUILTINS.items():
            tool_tokens.append(tool_name)
            tool_tokens.extend(builtin_terms)
        if _PROJECTX_NATIVE_BUILTINS and "projectx" not in tools_by_agent:
            tools_by_agent["projectx"] = sorted(_PROJECTX_NATIVE_BUILTINS)

        return tools_by_agent, tool_tokens

    def _collect_skills(self) -> List[str]:
        try:
            from simp.projectx.skill_engine import get_skill_engine

            return sorted(skill.name for skill in get_skill_engine().all_skills())
        except Exception:
            return []

    def _collect_subsystems(self) -> List[str]:
        try:
            from simp.projectx.subsystems import get_subsystem_registry

            statuses = get_subsystem_registry().all_status()
            return sorted(str(status.get("name")) for status in statuses if status.get("name"))
        except Exception:
            return []

    @staticmethod
    def _searchable_tokens(
        tools_by_agent: Dict[str, List[str]],
        skills: Sequence[str],
        subsystems: Sequence[str],
        tool_tokens: Sequence[str],
    ) -> str:
        tool_names = [name for names in tools_by_agent.values() for name in names]
        corpus = " ".join(list(tool_names) + list(skills) + list(subsystems) + list(tool_tokens)).lower()
        return corpus

    @staticmethod
    def _detect_gaps(goal: str, searchable: str) -> List[CapabilityGap]:
        goal_lower = goal.lower()
        gaps: List[CapabilityGap] = []
        for capability, keywords, evidence_terms in _CAPABILITY_RULES:
            matched = [kw for kw in keywords if kw in goal_lower]
            if not matched:
                continue
            if any(term in searchable for term in evidence_terms):
                continue
            gaps.append(
                CapabilityGap(
                    capability=capability,
                    reason=f"No registered tool, skill, or subsystem matches {capability}.",
                    matched_keywords=matched,
                )
            )
        return gaps


_tool_ecology: Optional[ProjectXToolEcology] = None


def get_tool_ecology() -> ProjectXToolEcology:
    global _tool_ecology
    if _tool_ecology is None:
        _tool_ecology = ProjectXToolEcology()
    return _tool_ecology
