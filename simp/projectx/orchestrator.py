"""
ProjectX Orchestrator — Phase 3/5 Integration Point

Central controller that coordinates all ProjectX subsystems into a
single recursive self-improvement loop. Wires together:

  computer       → bounded action execution (existing)
  mesh_bridge    → SIMP mesh connectivity (existing)
  internet       → web access (Phase 1)
  rag_memory     → long-term knowledge (Phase 2)
  subsystems     → specialised sub-agents (Phase 2)
  apo_engine     → prompt optimisation (Phase 3)
  safety_monitor → health/safety gating (Phase 4)
  validator      → answer verification (Phase 4)
  parallel_exec  → concurrent task dispatch (Phase 5)

The orchestrator implements a four-stage pipeline per task:
  1. RETRIEVE  — pull relevant memory + web context
  2. PLAN      — decompose into subtasks via planning subsystem
  3. EXECUTE   — run subtasks in parallel (or sequentially if ordered)
  4. VALIDATE  — verify outputs; re-try if below threshold; store results

Self-improvement loop (called by cron / mesh event):
  - Collect recent eval_scores from safety_monitor
  - Run APO step on the planning prompt
  - Prune expired RAG entries
  - Run protocol health check
  - Emit SIMP mesh heartbeat with full status
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .computer import ProjectXComputer
from .internet import get_internet_client, InternetClient
from .rag_memory import get_rag_memory, RAGMemory
from .apo_engine import APOEngine
from .subsystems import get_subsystem_registry, SubsystemRegistry
from .safety_monitor import get_safety_monitor, SafetyMonitor
from .validator import AnswerValidator
from .parallel_executor import ParallelExecutor, TaskSpec
from .skill_engine import get_skill_engine
from .intent_adapter import get_intent_adapter
from .meta_learner import MetaLearner
from .evolution_tracker import get_evolution_tracker
from .resource_monitor import get_resource_monitor
from .knowledge_distiller import get_knowledge_distiller
from .agent_spawner import get_agent_spawner
from .telemetry import get_telemetry_collector
from .mesh_intelligence import get_mesh_intelligence
from .benchmark import BenchmarkRunner
from .tool_ecology import get_tool_ecology

logger = logging.getLogger(__name__)

_PLANNING_PROMPT = (
    "You are a task planner. Break the following goal into a numbered list of "
    "concrete, independent subtasks. Each subtask must be completable by one "
    "of these agent types: code_gen, research, analysis, creative, planning. "
    "Format: <number>. [agent_type] <subtask description>. Goal: {goal}"
)


@dataclass
class OrchestratorConfig:
    max_retries: int = 2
    validation_threshold: float = 0.55
    memory_persist_dir: str = "./projectx_memory"
    apo_steps_per_cycle: int = 10
    parallel_max_concurrent: int = 6
    enable_web: bool = True
    enable_apo: bool = True
    enable_validation: bool = True


@dataclass
class TaskResult:
    task_id: str
    goal: str
    subtask_results: List[Dict[str, Any]] = field(default_factory=list)
    final_output: str = ""
    validation_score: float = 0.0
    validated: bool = False
    retries: int = 0
    latency_ms: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "success": self.success,
            "validated": self.validated,
            "validation_score": round(self.validation_score, 4),
            "retries": self.retries,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "subtask_count": len(self.subtask_results),
        }


class ProjectXOrchestrator:
    """
    Unified ProjectX task orchestrator with recursive self-improvement.

    Quick start::

        from simp.projectx.orchestrator import ProjectXOrchestrator

        def my_llm(system: str, user: str) -> str:
            # call Claude / GPT / local model here
            ...

        orc = ProjectXOrchestrator(executor=my_llm)
        result = orc.run("Research and summarise quantum computing breakthroughs in 2025")
        print(result.final_output)
    """

    def __init__(
        self,
        executor: Optional[Callable[[str, str], str]] = None,
        config: Optional[OrchestratorConfig] = None,
        computer: Optional[ProjectXComputer] = None,
    ) -> None:
        self._config = config or OrchestratorConfig()
        self._executor = executor or self._stub_executor
        self._computer = computer or ProjectXComputer()

        # Subsystems
        self._memory: RAGMemory = get_rag_memory(self._config.memory_persist_dir)
        self._internet: InternetClient = get_internet_client()
        self._registry: SubsystemRegistry = get_subsystem_registry()
        self._safety: SafetyMonitor = get_safety_monitor()
        self._validator = AnswerValidator(
            threshold=self._config.validation_threshold,
            memory=self._memory,
            web_client=self._internet if self._config.enable_web else None,
        )
        self._parallel = ParallelExecutor(
            computer=self._computer,
            max_concurrent=self._config.parallel_max_concurrent,
        )

        # APO engine for the planning prompt
        self._apo: Optional[APOEngine] = None
        if self._config.enable_apo:
            self._apo = APOEngine(
                base_prompt=_PLANNING_PROMPT,
                task_name="planning",
                persist_path="./projectx_logs/apo_planning_history.jsonl",
            )

        # Skill engine — loads simp/skills/*.md into the subsystem registry
        self._skill_engine = get_skill_engine()

        # Intent adapter — bidirectional SIMP mesh integration
        self._intent_adapter = get_intent_adapter()

        # Meta-learner — bridges APO/trade history to SystemMemoryStore
        self._meta_learner = MetaLearner(
            rag_memory=self._memory,
            safety_monitor=self._safety,
            apo_engine=self._apo,
        )

        # Evolution tracker — tracks capability growth vs roadmap targets
        self._evolution_tracker = get_evolution_tracker()

        # Wave 4 modules — resource monitor, knowledge distiller, spawner,
        # telemetry, and mesh intelligence (all lazy-start)
        self._resource_monitor = get_resource_monitor(auto_start=True)
        self._knowledge_distiller = get_knowledge_distiller()
        self._agent_spawner = get_agent_spawner()
        self._telemetry = get_telemetry_collector(auto_start=True)
        self._mesh_intel = get_mesh_intelligence(auto_start=True)
        self._benchmark = BenchmarkRunner(executor_id="projectx_orchestrator")
        self._tool_ecology = get_tool_ecology()

        try:
            from .tool_factory import get_tool_factory
            get_tool_factory(self).ensure_default_tools()
        except Exception as exc:
            logger.debug("ProjectX tool suite bootstrap skipped: %s", exc)

        logger.info("ProjectXOrchestrator initialized")

    # ── Public API ────────────────────────────────────────────────────────

    def run(self, goal: str, context: Optional[str] = None) -> TaskResult:
        """
        Execute a high-level goal through the full 4-stage pipeline.

        Args:
            goal:    Natural-language goal description.
            context: Optional additional context to prime the run.

        Returns:
            TaskResult with final_output and validation info.
        """
        task_id = uuid.uuid4().hex[:8]

        # Input validation
        try:
            from simp.projectx.hardening import InputGuard
            goal = InputGuard.check_string(goal, "goal", max_len=InputGuard.MAX_PROMPT_BYTES)
        except Exception as exc:
            return TaskResult(task_id=task_id, goal=str(goal)[:80], error=str(exc))

        # Resource throttle — hard-abort on critical load, log on other errors
        try:
            self._resource_monitor.check_throttle()
        except Exception as exc:
            from simp.projectx.resource_monitor import ThrottleSignal
            if isinstance(exc, ThrottleSignal):
                logger.error("Task %s rejected: resource critical — %s", task_id, exc)
                return TaskResult(
                    task_id=task_id,
                    goal=goal,
                    error=f"Resource throttle: {exc}",
                )
            logger.warning("Resource monitor error (non-critical): %s", exc)

        if self._safety.emergency_stopped:
            return TaskResult(
                task_id=task_id,
                goal=goal,
                error="Emergency stop is active — no tasks executed",
            )
        if self._safety.is_paused:
            return TaskResult(
                task_id=task_id,
                goal=goal,
                error="Safety pause in effect — operations temporarily halted",
            )

        t0 = time.time()
        result = TaskResult(task_id=task_id, goal=goal)

        for attempt in range(self._config.max_retries + 1):
            try:
                result.retries = attempt
                output, subtask_results = self._pipeline(goal, context, task_id)
                result.final_output = output
                result.subtask_results = subtask_results

                if self._config.enable_validation:
                    report = self._validator.validate(goal, output)
                    result.validation_score = report.composite_score
                    result.validated = report.passed
                    self._safety.record("eval_score", report.composite_score)

                    if report.passed or attempt >= self._config.max_retries:
                        break
                    logger.info(
                        "Task %s attempt %d validation score %.3f < %.3f — retrying",
                        task_id, attempt + 1, report.composite_score,
                        self._config.validation_threshold,
                    )
                    # Enrich context with validation failure reasons for next attempt
                    context = (context or "") + f"\n\nPrevious attempt issues: {report.flagged_reasons}"
                else:
                    result.validated = True
                    break

            except Exception as exc:
                logger.error("Task %s attempt %d failed: %s", task_id, attempt, exc)
                result.error = str(exc)
                self._safety.record("eval_error", 1)
                if attempt >= self._config.max_retries:
                    break

        result.latency_ms = int((time.time() - t0) * 1000)
        self._safety.record("inference_latency_ms", result.latency_ms)
        self._safety.record("eval_total", 1)

        # Store successful output in memory for future retrieval
        if result.success and result.final_output:
            self._memory.store(
                result.final_output,
                source=f"task:{task_id}",
                metadata={"goal": goal[:200]},
            )

        return result

    def self_improve(self) -> Dict[str, Any]:
        """
        Run one self-improvement cycle:
          1. APO step on planning prompt
          2. Meta-learning cycle (episodes → lessons → policies)
          3. Prune expired memory
          4. Protocol health check
          5. Safety alert sweep
          6. Evolution snapshot
          7. Return improvement report
        """
        report: Dict[str, Any] = {
            "timestamp": time.time(),
            "apo_report": None,
            "apo_backends": [],
            "benchmark": None,
            "meta_learning": None,
            "memory_pruned": 0,
            "health": None,
            "safety_alerts": [],
            "evolution": None,
        }

        # APO step
        if self._apo and self._config.enable_apo:
            try:
                def _apo_scorer(prompt: str) -> float:
                    result = self.run(prompt[:200], context="self-improvement eval")
                    return result.validation_score if result.success else 0.0

                self._apo.optimize(_apo_scorer, steps=self._config.apo_steps_per_cycle)
                report["apo_report"] = self._apo.report()

                backend_reports = []
                for backend in ("bayesian", "evolutionary"):
                    backend_reports.append(
                        self._apo.optimize_prompt_knobs(
                            _apo_scorer,
                            backend=backend,
                            iterations=min(8, max(4, self._config.apo_steps_per_cycle)),
                        )
                    )
                report["apo_backends"] = backend_reports
            except Exception as exc:
                logger.warning("APO step failed: %s", exc)

        # Benchmark pass — stable score for improvement tracking
        try:
            bench = self._benchmark.run(self._executor, domains=["reasoning", "planning", "analysis"])
            report["benchmark"] = {
                **bench.to_dict(),
                "trend": self._benchmark.improvement_trend(),
            }
        except Exception as exc:
            logger.warning("Benchmark step failed: %s", exc)

        # Meta-learning cycle
        try:
            ml_report = self._meta_learner.run_cycle()
            report["meta_learning"] = ml_report.to_dict()
        except Exception as exc:
            logger.warning("Meta-learning cycle failed: %s", exc)

        # Memory maintenance
        try:
            report["memory_pruned"] = self._memory.prune_expired()
        except Exception as exc:
            logger.warning("Memory prune failed: %s", exc)

        # Protocol health
        try:
            report["health"] = self._computer.check_protocol_health()
        except Exception as exc:
            logger.warning("Health check failed: %s", exc)

        # Safety sweep
        try:
            alerts = self._safety.check_alerts()
            report["safety_alerts"] = [
                {"type": a.alert_type.value, "severity": a.severity.value, "message": a.message}
                for a in alerts
            ]
        except Exception as exc:
            logger.warning("Safety sweep failed: %s", exc)

        # Evolution tracking
        try:
            evo_report = self._evolution_tracker.track_cycle(
                safety_monitor=self._safety,
                apo_engine=self._apo,
                rag_memory=self._memory,
            )
            report["evolution"] = {
                "trend": evo_report.trend,
                "on_track_for_2x": evo_report.on_track_for_2x,
                "targets_met": evo_report.targets_met,
                "week_over_week": evo_report.week_over_week,
            }
        except Exception as exc:
            logger.warning("Evolution tracking failed: %s", exc)

        # Knowledge distillation — compress RAG + lessons into high-signal fragments
        try:
            dist_report = self._knowledge_distiller.run(top_n=100, min_signal=0.3)
            self._knowledge_distiller.inject_into_rag(dist_report.fragments[:30])
            report["knowledge_distillation"] = dist_report.to_dict()
        except Exception as exc:
            logger.warning("Knowledge distillation failed: %s", exc)

        # Mesh intelligence — rebalancing recommendations
        try:
            rebalance = self._mesh_intel.recommend_rebalance()
            report["mesh_rebalance"] = rebalance
        except Exception as exc:
            logger.warning("Mesh intelligence failed: %s", exc)

        # Telemetry flush
        try:
            self._telemetry.collect()
        except Exception as exc:
            logger.debug("Telemetry collect failed: %s", exc)

        return report

    def get_status(self) -> Dict[str, Any]:
        resource_snap = self._resource_monitor.latest()
        tool_snapshot = self._tool_ecology.snapshot()
        return {
            "memory_entries": self._memory.count(),
            "safety": self._safety.get_summary(),
            "apo": self._apo.report() if self._apo else None,
            "benchmark_trend": self._benchmark.improvement_trend(),
            "subsystems": self._registry.all_status(),
            "skills_loaded": [s.name for s in self._skill_engine.all_skills()],
            "intent_mappings": len(self._skill_engine.list_intent_mappings()),
            "evolution": self._evolution_tracker.get_dashboard_data(),
            "learning_loop_running": False,  # set by LearningLoop.start()
            "resources": resource_snap.to_dict() if resource_snap else None,
            "active_agents": len(self._agent_spawner.list_agents()),
            "mesh_topology": self._mesh_intel.topology(),
            "tool_ecology": tool_snapshot.to_dict(),
        }

    def dispatch_intent(
        self, intent_type: str, goal: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route a task through the SIMP intent system (broker → agent pool).
        Falls back to local execution if broker is unreachable.
        """
        resp = self._intent_adapter.dispatch(
            intent_type=intent_type,
            goal=goal,
            params=params,
        )
        return {
            "intent_id": resp.intent_id,
            "intent_type": resp.intent_type,
            "success": resp.success,
            "result": resp.result,
            "error": resp.error,
            "latency_ms": resp.latency_ms,
        }

    # ── Pipeline stages ───────────────────────────────────────────────────

    def _pipeline(self, goal: str, context: Optional[str], task_id: str) -> tuple[str, List[Dict[str, Any]]]:
        # Stage 1: Retrieve
        memory_ctx = self._retrieve(goal)

        # Stage 2: Plan
        subtasks = self._plan(goal, context, memory_ctx)

        # Stage 3: Execute subtasks
        outputs, subtask_results = self._execute_subtasks(subtasks, goal)

        # Stage 4: Synthesise
        return self._synthesise(goal, outputs), subtask_results

    def _retrieve(self, goal: str) -> str:
        context_parts: List[str] = []
        try:
            hits = self._memory.query(goal, top_k=3)
            if hits:
                context_parts.append(
                    "\n".join(f"[Memory] {r.entry.content[:300]}" for r in hits)
                )
        except Exception as exc:
            logger.debug("Retrieval failed: %s", exc)
        try:
            distilled = self._knowledge_distiller.get_top(3)
            if distilled:
                context_parts.append(
                    "\n".join(f"[Distilled] {frag.content[:240]}" for frag in distilled)
                )
        except Exception as exc:
            logger.debug("Distilled retrieval failed: %s", exc)
        return "\n".join(context_parts)

    def _plan(self, goal: str, context: Optional[str], memory_ctx: str) -> List[Dict[str, str]]:
        """Ask the planning subsystem to decompose the goal."""
        planning_prompt = _PLANNING_PROMPT
        if self._apo:
            planning_prompt = self._apo.best_candidate.template

        tool_ctx = self._tool_ecology.brief_for_goal(goal)
        full_context = "\n".join(filter(None, [memory_ctx, tool_ctx, context, planning_prompt[:300]]))
        result = self._registry.route(
            task=goal,
            executor=self._executor,
            preferred="planning",
            context=full_context or None,
            memory=self._memory,
        )
        return self._parse_subtasks(result.output, goal)

    def _parse_subtasks(self, plan_text: str, goal: str) -> List[Dict[str, str]]:
        """Parse the planner's numbered list into subtask dicts."""
        import re
        subtasks = []
        for line in plan_text.splitlines():
            m = re.match(r"^\d+\.\s+\[(\w+)\]\s+(.+)$", line.strip())
            if m:
                subtasks.append({"agent": m.group(1), "task": m.group(2)})
        if not subtasks:
            subtasks = [{"agent": "analysis", "task": goal}]
        return subtasks[:8]  # cap at 8 subtasks

    def _execute_subtasks(
        self,
        subtasks: List[Dict[str, str]],
        goal: str,
    ) -> tuple[List[str], List[Dict[str, Any]]]:
        batch_specs: List[TaskSpec] = []
        for idx, spec in enumerate(subtasks):
            agent_name = spec.get("agent", "analysis")
            task_text = spec.get("task", goal)
            batch_specs.append(
                TaskSpec(
                    name=f"subtask_{idx + 1}",
                    action=agent_name,
                    params={"task": task_text, "preferred": agent_name},
                    priority=idx + 1,
                    executor=self._run_subtask,
                    metadata={"goal": goal},
                )
            )

        batch = self._parallel.run_batch(batch_specs) if batch_specs else None
        outputs: List[str] = []
        subtask_results: List[Dict[str, Any]] = []
        for outcome in batch.outcomes if batch else []:
            payload = {
                "task_id": outcome.task_id,
                "name": outcome.name,
                "success": outcome.success,
                "latency_ms": outcome.latency_ms,
                "error": outcome.error,
            }
            if outcome.success and hasattr(outcome.result, "output"):
                payload["subsystem"] = getattr(outcome.result, "subsystem", "")
                payload["memory_hits"] = getattr(outcome.result, "memory_hits", 0)
                payload["sources"] = getattr(outcome.result, "sources", [])
                outputs.append(outcome.result.output)
            subtask_results.append(payload)
        return outputs, subtask_results

    def _run_subtask(self, action: str, params: Dict[str, Any]) -> Any:
        task_text = params.get("task", "")
        preferred = params.get("preferred")
        routed_agent = self._mesh_intel.route(task_text)
        spawned = self._agent_spawner.route_task(task_text)
        started = time.time()
        result = self._registry.route(
            task=task_text,
            executor=self._executor,
            preferred=preferred if preferred in ("code_gen", "research", "analysis", "creative", "planning") else None,
            memory=self._memory,
            web_client=self._internet if self._config.enable_web else None,
            context=self._tool_ecology.brief_for_goal(task_text) or None,
        )
        if routed_agent:
            self._mesh_intel.record_call(routed_agent, latency_ms=(time.time() - started) * 1000, error=not result.success)
        if spawned:
            spawned.increment()
        return result

    def _synthesise(self, goal: str, subtask_outputs: List[str]) -> str:
        """Combine subtask outputs into a final answer."""
        if not subtask_outputs:
            return ""
        combined = "\n\n".join(f"Part {i+1}:\n{out}" for i, out in enumerate(subtask_outputs))
        synthesis_prompt = (
            "Synthesise the following partial answers into a single coherent, "
            "complete response to the original goal. Eliminate redundancy. "
            "Be concise and accurate.\n\n"
            f"Goal: {goal}\n\n{combined}"
        )
        try:
            from simp.projectx.hardening import get_circuit_breaker
            cb = get_circuit_breaker("llm_executor")
            return cb.call(
                self._executor,
                "You are a synthesis agent. Combine partial answers into one complete response.",
                synthesis_prompt,
            )
        except Exception as exc:
            logger.warning("Synthesis failed: %s — returning concatenation", exc)
            return combined

    @staticmethod
    def _stub_executor(system_prompt: str, user_message: str) -> str:
        """Placeholder executor when no LLM is wired up."""
        return (
            f"[stub] system={system_prompt[:60]}… | "
            f"user={user_message[:120]}…"
        )
