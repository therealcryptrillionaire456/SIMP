"""
ProjectX Tool Factory

Creates a concrete native SIMP tool suite for the ProjectX runtime.
The MCP layer can re-export these tools, but it is no longer the source of truth.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from simp.native_tools import NativeToolRegistry, SimpTool

from .benchmark import BenchmarkRunner
from .multimodal import get_multimodal_processor
from .orchestrator import ProjectXOrchestrator
from .self_test import run_self_test
from .tool_ecology import get_tool_ecology
from .tool_generator import get_dynamic_tool_creator


@dataclass
class ToolFactoryReport:
    agent_id: str
    tool_count: int
    tool_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "tool_count": self.tool_count,
            "tool_names": self.tool_names,
        }


class ProjectXToolFactory:
    """Register the default ProjectX native tool suite."""

    DEFAULT_AGENT_ID = "projectx"

    def __init__(
        self,
        orchestrator: Optional[ProjectXOrchestrator] = None,
        agent_id: str = DEFAULT_AGENT_ID,
    ) -> None:
        self._orchestrator = orchestrator or ProjectXOrchestrator()
        self._agent_id = agent_id

    def ensure_default_tools(self) -> ToolFactoryReport:
        registry = NativeToolRegistry.get_registry(self._agent_id, create=True)
        assert registry is not None
        tools = self._build_default_tools()
        registry.register_many(tools)
        return ToolFactoryReport(
            agent_id=self._agent_id,
            tool_count=len(registry.list_tools()),
            tool_names=sorted(registry.tool_names()),
        )

    def _build_default_tools(self) -> List[SimpTool]:
        benchmark = BenchmarkRunner(executor_id=f"{self._agent_id}_tool_suite")
        ecology = get_tool_ecology()
        processor = get_multimodal_processor()
        dynamic_creator = get_dynamic_tool_creator(self._agent_id)

        def run_goal(goal: str, context: str = "") -> Dict[str, Any]:
            return self._orchestrator.run(goal, context=context or None).to_dict()

        def self_improve() -> Dict[str, Any]:
            return self._orchestrator.self_improve()

        def get_status() -> Dict[str, Any]:
            return self._orchestrator.get_status()

        def run_benchmark(domains: Optional[List[str]] = None) -> Dict[str, Any]:
            report = benchmark.run(self._orchestrator._executor, domains=domains)
            return report.to_dict()

        def run_self_tests(fast: bool = True) -> Dict[str, Any]:
            return run_self_test(fast=fast).to_dict()

        def analyse_multimodal(
            text: str = "",
            image_b64: str = "",
            audio_b64: str = "",
            video_b64: str = "",
        ) -> Dict[str, Any]:
            image_bytes = base64.b64decode(image_b64) if image_b64 else None
            audio_bytes = base64.b64decode(audio_b64) if audio_b64 else None
            video_bytes = base64.b64decode(video_b64) if video_b64 else None
            return processor.analyse_payload(
                text=text,
                image_bytes=image_bytes,
                audio_bytes=audio_bytes,
                video_bytes=video_bytes,
            ).to_dict()

        def inventory_tools(goal: str = "") -> Dict[str, Any]:
            return ecology.snapshot(goal).to_dict()

        def deployment_readiness(fast: bool = True) -> Dict[str, Any]:
            from .deployment import ProjectXDeploymentManager

            return ProjectXDeploymentManager(orchestrator=self._orchestrator).readiness_report(
                fast=fast
            ).to_dict()

        def optimize_prompt_backend(
            backend: str = "bayesian",
            iterations: int = 8,
        ) -> Dict[str, Any]:
            if self._orchestrator._apo is None:
                return {"status": "unavailable", "reason": "apo_disabled"}

            def scorer(prompt: str) -> float:
                result = self._orchestrator.run(prompt[:200], context="tool-driven apo optimization")
                return result.validation_score if result.success else 0.0

            return self._orchestrator._apo.optimize_prompt_knobs(
                scorer,
                backend=backend,
                iterations=max(3, min(int(iterations), 20)),
            )

        def generate_tool(requirement: str, name_hint: str = "") -> Dict[str, Any]:
            return dynamic_creator.register_tool(requirement, name_hint=name_hint)

        return [
            SimpTool.from_function(
                run_goal,
                name="projectx_run_goal",
                description="Run a ProjectX goal through retrieval, planning, execution, and validation.",
                intent_type="projectx_run_goal",
            ),
            SimpTool.from_function(
                self_improve,
                name="projectx_self_improve",
                description="Execute one ProjectX self-improvement cycle.",
                intent_type="projectx_self_improve",
            ),
            SimpTool.from_function(
                get_status,
                name="projectx_status",
                description="Return the current ProjectX runtime status.",
                intent_type="projectx_status",
            ),
            SimpTool.from_function(
                run_benchmark,
                name="projectx_benchmark",
                description="Run the ProjectX benchmark suite.",
                intent_type="projectx_benchmark",
            ),
            SimpTool.from_function(
                run_self_tests,
                name="projectx_self_test",
                description="Run the ProjectX self-test suite.",
                intent_type="projectx_self_test",
            ),
            SimpTool.from_function(
                analyse_multimodal,
                name="projectx_multimodal_analyse",
                description="Analyse text, image, audio, and video inputs through the ProjectX multimodal runtime.",
                intent_type="projectx_multimodal_analyse",
            ),
            SimpTool.from_function(
                inventory_tools,
                name="projectx_tool_inventory",
                description="Inspect the currently registered ProjectX tool ecology and capability gaps.",
                intent_type="projectx_tool_inventory",
            ),
            SimpTool.from_function(
                deployment_readiness,
                name="projectx_deployment_readiness",
                description="Generate a ProjectX production-readiness report.",
                intent_type="projectx_deployment_readiness",
            ),
            SimpTool.from_function(
                optimize_prompt_backend,
                name="projectx_optimize_prompt",
                description="Run Bayesian or evolutionary prompt optimization for ProjectX APO.",
                intent_type="projectx_optimize_prompt",
            ),
            SimpTool.from_function(
                generate_tool,
                name="projectx_generate_tool",
                description="Generate and register a bounded ProjectX MCP tool from a requirement string.",
                intent_type="projectx_generate_tool",
            ),
        ]


_tool_factory: Optional[ProjectXToolFactory] = None


def get_tool_factory(orchestrator: Optional[ProjectXOrchestrator] = None) -> ProjectXToolFactory:
    global _tool_factory
    if _tool_factory is None or orchestrator is not None:
        _tool_factory = ProjectXToolFactory(orchestrator=orchestrator)
    return _tool_factory
