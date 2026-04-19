"""
Kloutbot Agent: Autonomous Strategy Generation + Orchestration

Wraps Q_IntentCompiler as a SIMP-compatible agent.
Acts as GROK node in the pentagram, receiving market signals and generating
optimal trading strategies.  Also provides orchestration handlers for
goal decomposition, status checking, and replanning.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from simp.agent import SimpAgent
from simp.intent import Intent, SimpResponse
from simp.agents.q_intent_compiler import QIntentCompiler, StrategicOptimizer, DecisionTree
from simp.memory.knowledge_index import KnowledgeIndex
from simp.orchestration.task_decomposer import TaskDecomposer
from simp.integrations.timesfm_service import (
    get_timesfm_service,
    ForecastRequest,
)
from simp.integrations.timesfm_policy_engine import (
    PolicyEngine,
    make_agent_context_for,
)

# ---------------------------------------------------------------------------
# BRP integration (shadow mode — never blocks strategy generation)
# ---------------------------------------------------------------------------

_brp_bridge = None  # Module-level singleton, initialised lazily


def _get_brp_bridge():
    """Lazily create a BRP bridge for shadow observations."""
    global _brp_bridge
    if _brp_bridge is None:
        try:
            from simp.security.brp_bridge import BRPBridge
            _brp_bridge = BRPBridge()
        except Exception:
            pass
    return _brp_bridge


class KloutbotAgent(SimpAgent):
    """
    Autonomous Kloutbot Agent

    Part of the pentagram:
    - Receives market signals from VISION (foresight)
    - Receives patterns from GEMINI (cosmology)
    - Receives vectors from POE (embeddings)
    - Generates optimal strategies via Q_IntentCompiler
    - Outputs to TRUSTY for validation

    SIMP Intent Handlers:
    - "generate_strategy": Create trading strategy from market data
    - "analyze_signals": Analyze market signals
    - "optimize_decision": Run minimax optimization
    - "improve_tree": Recursively improve decision
    - "get_status": Get agent status
    """

    def __init__(
        self,
        agent_id: str = "kloutbot:grok:001",
        organization: str = "kloutbot.autonomous"
    ):
        """Initialize Kloutbot agent"""
        super().__init__(agent_id, organization)

        self.compiler = QIntentCompiler()
        self._optimizer = StrategicOptimizer()
        self.strategy_history: List[DecisionTree] = []
        self.max_history = 100

        # Orchestration state
        self.task_decomposer = TaskDecomposer()
        self.goals: Dict[str, Dict[str, Any]] = {}  # goal_id -> goal state

        # TimesFM affinity history buffer (per-agent series)
        self._affinity_buffer: List[float] = []
        self._affinity_buffer_cap: int = 256

        # ── Sprint 42: DeerFlow SubagentSpawner ─────────────────────────────
        # Lazy-loaded on first use via _get_spawner().  Enables Kloutbot to
        # self-spawn specialised sub-agents (deep-research, code-review, etc.)
        # without blocking its own event loop.
        self._spawner = None

        # Register intent handlers — trading strategy
        self.register_handler("generate_strategy", self.handle_generate_strategy)
        self.register_handler("analyze_signals", self.handle_analyze_signals)
        self.register_handler("optimize_decision", self.handle_optimize_decision)
        self.register_handler("improve_tree", self.handle_improve_tree)
        self.register_handler("get_status", self.handle_get_status)
        self.register_handler("strategy_history", self.handle_strategy_history)

        # Register intent handlers — orchestration
        self.register_handler("submit_goal", self.handle_submit_goal)
        self.register_handler("check_status", self.handle_check_status)
        self.register_handler("replan", self.handle_replan)

        # Register intent handlers — self-spawning research
        self.register_handler("research", self.handle_research)
        self.register_handler("spawn_research", self.handle_research)

    def _record_affinity(self, affinity: float) -> List[float]:
        """Append affinity observation to the per-agent history buffer."""
        self._affinity_buffer.append(affinity)
        if len(self._affinity_buffer) > self._affinity_buffer_cap:
            self._affinity_buffer = self._affinity_buffer[-self._affinity_buffer_cap:]
        return self._affinity_buffer

    def _get_spawner(self):
        """
        Lazy-load the ProjectXSubagentSpawner from the DeerFlow runtime.

        Returns None silently if the runtime is not yet active, allowing
        all handlers to degrade gracefully when the spawner is unavailable.
        """
        if self._spawner is not None:
            return self._spawner
        try:
            import sys
            import pathlib
            _scaffold = str(
                pathlib.Path(__file__).resolve().parents[4]
                / "ProjectX" / "proposals" / "scaffolding"
            )
            if _scaffold not in sys.path:
                sys.path.insert(0, _scaffold)
            from simp.orchestration.orchestration_loop import _get_deerflow_runtime
            df = _get_deerflow_runtime()
            if df and df.spawner:
                self._spawner = df.spawner
        except Exception:
            pass
        return self._spawner

    async def _get_strategy_horizon_advice(
        self,
        affinity: float,
        drift_risk: float,
    ) -> Dict[str, Any]:
        """
        Call TimesFM to forecast affinity trajectory and recommend a strategy horizon.

        Uses the per-agent affinity history to project how long the current
        market alignment is expected to persist. Returns horizon recommendation
        and rationale to be surfaced in the generate_strategy response.

        Safety:
        - Never raises. Falls back to neutral advice on any error.
        - Advisory only. Does not change ArbDecision or strategy tree.
        """
        result = {
            "recommended_horizon": "medium",
            "recommended_horizon_steps": 16,
            "timesfm_horizon_applied": False,
            "timesfm_horizon_rationale": "TimesFM unavailable: using default medium horizon (16 steps)",
        }
        try:
            series_id = f"{self.agent_id}:affinity"
            history = self._record_affinity(affinity)

            if len(history) < 16:
                result["timesfm_horizon_rationale"] = (
                    f"TimesFM insufficient history: {len(history)}/16 observations, using default medium horizon (16 steps)"
                )
                return result

            svc = await get_timesfm_service()
            ctx = make_agent_context_for(
                agent_id=self.agent_id,
                series_id=series_id,
                series_length=len(history),
                requesting_handler="handle_generate_strategy",
                extra={"drift_risk": drift_risk},
            )
            engine = PolicyEngine()
            decision = engine.evaluate(ctx)
            if decision.denied:
                result["timesfm_horizon_rationale"] = (
                    f"TimesFM policy denied: {decision.reason}, using default medium horizon (16 steps)"
                )
                return result

            req = ForecastRequest(
                series_id=series_id,
                values=history,
                requesting_agent=self.agent_id,
                horizon=32,
                context_metadata={"drift_risk": drift_risk},
            )
            resp = await svc.forecast(req)

            if not resp.available:
                result["timesfm_horizon_rationale"] = (
                    "TimesFM shadow mode: service available=False, using default medium horizon (16 steps)"
                )
                return result

            if resp.point_forecast:
                pf = resp.point_forecast
                # Estimate persistence: steps until affinity drops below 0.5 threshold
                persistence_steps = next(
                    (i for i, v in enumerate(pf) if v < 0.5),
                    len(pf),
                )

                if persistence_steps >= 24:
                    horizon_label = "long"
                    horizon_steps = 32
                elif persistence_steps >= 12:
                    horizon_label = "medium"
                    horizon_steps = 16
                else:
                    horizon_label = "short"
                    horizon_steps = 8

                result.update({
                    "recommended_horizon": horizon_label,
                    "recommended_horizon_steps": horizon_steps,
                    "timesfm_horizon_applied": True,
                    "timesfm_horizon_rationale": (
                        f"TimesFM forecast: affinity persists {persistence_steps} steps > 0.5 threshold. "
                        f"Using {horizon_label} horizon ({horizon_steps} steps) for "
                        f"{'strategic positioning' if horizon_label == 'long' else 'near-term planning' if horizon_label == 'medium' else 'immediate execution'}."
                    ),
                })

        except Exception as exc:
            result["timesfm_horizon_rationale"] = f"TimesFM horizon advice error: {exc}"

        return result

    async def handle_generate_strategy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main handler: Generate optimal trading strategy

        Input parameters:
        {
            "foresight": {
                "affinity": 0.85,
                "drift_risk": 0.12
            },
            "deltas": {
                "momentum": 0.8,
                "volume": 0.7,
                "sentiment": 0.65
            },
            "timestamp": "2026-04-02T...",
            "market_data": {...}  # Optional
        }
        """
        # BRP pre-action event (shadow mode — never blocks)
        brp_meta = {}
        brp_event_id = ""
        try:
            bridge = _get_brp_bridge()
            if bridge is not None:
                from simp.security.brp_models import BRPEvent, BRPEventType, BRPMode
                brp_event = BRPEvent(
                    source_agent="kloutbot",
                    event_type=BRPEventType.STRATEGY_GENERATION.value,
                    action="generate_strategy",
                    context={
                        "foresight": params.get("foresight", {}),
                        "deltas": params.get("deltas", {}),
                    },
                    mode=BRPMode.SHADOW.value,
                    tags=["kloutbot", "strategy_generation"],
                )
                brp_event_id = brp_event.event_id
                brp_resp = bridge.evaluate_event(brp_event)
                brp_meta = {
                    "event_id": brp_event_id,
                    "decision": brp_resp.decision,
                    "threat_score": brp_resp.threat_score,
                    "mode": brp_resp.mode,
                }
        except Exception:
            pass

        try:
            # Extract parameters
            foresight = params.get("foresight", {})
            deltas = params.get("deltas", {})
            timestamp = params.get("timestamp", datetime.utcnow().isoformat())
            market_data = params.get("market_data")

            # Validate input
            if not foresight or not deltas:
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "error_message": "Foresight and deltas are required"
                }

            # Build streams object for compiler
            streams = {
                "timestamp": timestamp,
                "deltas": deltas,
                "foresight": foresight
            }

            # Compile intent using Q_IntentCompiler
            tree = await self.compiler.compile_intent(streams, market_data)

            # Store in history
            self._add_to_history(tree)

            # TimesFM: forecast affinity trajectory → recommend strategy horizon
            affinity = float(foresight.get("affinity", 0.5))
            drift_risk = float(foresight.get("drift_risk", 0.0))
            horizon_advice = await self._get_strategy_horizon_advice(
                affinity=affinity,
                drift_risk=drift_risk,
            )

            # Convert to actionable parameters
            action_params = self.compiler.get_action_params(tree)

            # Calculate mutation-memory telemetry
            total_strategies = len(self.strategy_history)
            recent_strategies = min(10, total_strategies)

            # Calculate average horizon from recent strategies (if we tracked it)
            # For now, just include basic stats
            mutation_telemetry = {
                "total_strategies_generated": total_strategies,
                "recent_strategies_count": recent_strategies,
                "strategy_history_capacity": self.max_history,
                "compiler_iterations": self.compiler.iteration_count,
                "improvement_history_length": len(self.compiler.improvement_history),
            }

            # BRP post-action observation (success)
            try:
                bridge = _get_brp_bridge()
                if bridge is not None:
                    from simp.security.brp_models import BRPObservation, BRPMode
                    obs = BRPObservation(
                        source_agent="kloutbot",
                        event_id=brp_event_id,
                        action="generate_strategy",
                        outcome="success",
                        result_data={"strategy_count": total_strategies},
                        mode=BRPMode.SHADOW.value,
                        tags=["kloutbot", "strategy_generation"],
                    )
                    bridge.ingest_observation(obs)
            except Exception:
                pass

            return {
                "status": "success",
                "strategy": tree.to_dict(),
                "action_params": action_params,
                "recommended_horizon": horizon_advice["recommended_horizon"],
                "recommended_horizon_steps": horizon_advice["recommended_horizon_steps"],
                "timesfm_horizon_applied": horizon_advice["timesfm_horizon_applied"],
                "timesfm_horizon_rationale": horizon_advice["timesfm_horizon_rationale"],
                "mutation_telemetry": mutation_telemetry,
                "brp": brp_meta,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # BRP post-action observation (failure)
            try:
                bridge = _get_brp_bridge()
                if bridge is not None:
                    from simp.security.brp_models import BRPObservation, BRPMode
                    obs = BRPObservation(
                        source_agent="kloutbot",
                        event_id=brp_event_id,
                        action="generate_strategy",
                        outcome="error",
                        result_data={"error": str(e)},
                        mode=BRPMode.SHADOW.value,
                        tags=["kloutbot", "strategy_generation", "error"],
                    )
                    bridge.ingest_observation(obs)
            except Exception:
                pass

            return {
                "status": "error",
                "error_code": "STRATEGY_GENERATION_FAILED",
                "error_message": str(e)
            }

    async def handle_analyze_signals(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market signals without generating strategy

        This allows VISION to share signals for analysis without immediate action.
        """
        try:
            foresight = params.get("foresight")
            deltas = params.get("deltas")

            if not foresight or not deltas:
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "error_message": "Foresight and deltas required"
                }

            # Analyze signal strength
            signal_strength = sum(deltas.values()) / len(deltas) if deltas else 0.5
            confidence = foresight.get("affinity", 0.5)
            risk = foresight.get("drift_risk", 0.1)

            # Signal quality score - ensure denominator is not zero
            denominator = 1 + risk
            if denominator == 0:
                denominator = 1e-10  # Small epsilon to avoid division by zero
            quality = (signal_strength * confidence) / denominator

            return {
                "status": "success",
                "analysis": {
                    "signal_strength": signal_strength,
                    "confidence": confidence,
                    "risk": risk,
                    "quality_score": quality,
                    "action_recommended": "BUY" if quality > 0.5 else "HOLD"
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error_code": "ANALYSIS_FAILED",
                "error_message": str(e)
            }

    async def handle_optimize_decision(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply minimax optimization to an existing decision

        Allows TRUSTY or other agents to re-optimize a decision.
        """
        try:
            foresight = params.get("foresight")
            deltas = params.get("deltas")

            if not foresight or not deltas:
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "error_message": "Foresight and deltas required"
                }

            # Build initial tree
            streams = {
                "timestamp": datetime.utcnow().isoformat(),
                "deltas": deltas,
                "foresight": foresight
            }

            tree = self.compiler._build_fractal_tree(streams)
            tree = self.compiler._apply_minimax(tree)

            return {
                "status": "success",
                "optimized_tree": tree.to_dict(),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error_code": "OPTIMIZATION_FAILED",
                "error_message": str(e)
            }

    async def handle_improve_tree(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an improvement request via SIMP intent.

        Accepts: intent_type "improve_tree" with params:
            - target: which tree/component to improve (default: "decision_tree")
            - iterations: how many improvement iterations (default: 3)
        """
        target = params.get("target", "decision_tree")
        iterations = min(params.get("iterations", 3), 10)  # Cap at 10

        if self._optimizer is None:
            return {
                "type": "response",
                "status": "failed",
                "error": "StrategicOptimizer not initialized",
            }

        try:
            # Build a baseline tree if none provided
            streams = {
                "timestamp": datetime.utcnow().isoformat(),
                "deltas": params.get("deltas", {}),
                "foresight": params.get("foresight", {"affinity": 0.5, "drift_risk": 0.1}),
            }
            current_tree = self._optimizer._build_fractal_tree(streams)
            current_tree = self._optimizer._apply_minimax(current_tree)

            # Run improvement iterations
            results = []
            for i in range(iterations):
                current_tree = await self._optimizer._recursive_improve(current_tree, iterations=1)
                results.append({
                    "iteration": i,
                    "utility": self._optimizer._calculate_utility(current_tree),
                })

            return {
                "type": "response",
                "intent_id": params.get("intent_id", ""),
                "agent_id": self.agent_id,
                "status": "completed",
                "response": {
                    "target": target,
                    "iterations_run": len(results),
                    "results": results,
                    "improvement_history_size": len(self._optimizer.improvement_history),
                },
            }
        except Exception as exc:
            return {
                "type": "response",
                "status": "failed",
                "error": str(exc),
            }

    async def handle_get_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current status of Kloutbot agent"""
        spawner = self._get_spawner()
        spawner_status: Dict[str, Any] = {"active": False}
        if spawner:
            try:
                sr = spawner.get_all_statuses() if hasattr(spawner, "get_all_statuses") else {}
                spawner_status = {
                    "active": True,
                    "tasks": sr,
                    "active_count": sum(
                        1 for t in sr.values()
                        if t.get("status") in ("pending", "running")
                    ) if isinstance(sr, dict) else 0,
                }
            except Exception:
                spawner_status = {"active": True, "tasks": {}, "active_count": 0}

        return {
            "status": "success",
            "agent": {
                "id": self.agent_id,
                "organization": self.organization,
                "compiler_iterations": self.compiler.iteration_count,
                "strategies_generated": len(self.strategy_history),
                "improvement_history_length": len(self.compiler.improvement_history)
            },
            "recent_strategies": len(self.strategy_history),
            "compiler_state": {
                "max_iterations": self.compiler.max_iterations,
                "minimax_depth": self.compiler.minimax_depth
            },
            "spawner": spawner_status,
            "goals_tracked": len(self.goals),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def handle_strategy_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve strategy generation history

        Optional parameters:
        - limit: Maximum number of strategies to return
        - offset: Skip this many strategies
        """
        try:
            limit = params.get("limit", 10)
            offset = params.get("offset", 0)

            # Get slice of history
            history_slice = self.strategy_history[offset:offset + limit]

            return {
                "status": "success",
                "total_strategies": len(self.strategy_history),
                "returned": len(history_slice),
                "offset": offset,
                "limit": limit,
                "strategies": [t.to_dict() for t in history_slice],
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e)
            }

    # ------------------------------------------------------------------
    # Orchestration Handlers
    # ------------------------------------------------------------------

    async def handle_submit_goal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept a high-level goal, decompose into subtasks, and route them.

        Input parameters:
        {
            "goal": "Build a new data pipeline",
            "goal_type": "build",        # optional — auto-inferred if omitted
            "constraints": {...}          # optional
        }
        """
        try:
            goal_text = params.get("goal")
            if not goal_text:
                return {
                    "status": "error",
                    "error_code": "MISSING_GOAL",
                    "error_message": "A 'goal' parameter is required",
                }

            goal_type = params.get(
                "goal_type",
                self.task_decomposer.infer_goal_type(goal_text),
            )
            constraints = params.get("constraints", {})

            subtasks = self.task_decomposer.decompose(goal_text, goal_type, constraints)
            goal_id = subtasks[0]["goal_id"] if subtasks else str(uuid.uuid4())[:8]

            # BRP plan evaluation (shadow mode — never blocks goal decomposition)
            brp_plan_meta = {}
            try:
                bridge = _get_brp_bridge()
                if bridge is not None:
                    from simp.security.brp_models import BRPPlan, BRPMode
                    brp_plan = BRPPlan(
                        source_agent="kloutbot",
                        steps=[
                            {"action": st.get("task_type", "unknown"), "description": st.get("description", "")}
                            for st in subtasks
                        ],
                        context={"goal": goal_text, "goal_type": goal_type},
                        mode=BRPMode.SHADOW.value,
                        tags=["kloutbot", "goal_decomposition"],
                    )
                    brp_resp = bridge.evaluate_plan(brp_plan)
                    brp_plan_meta = {
                        "plan_id": brp_plan.plan_id,
                        "decision": brp_resp.decision,
                        "threat_score": brp_resp.threat_score,
                        "mode": brp_resp.mode,
                    }
            except Exception:
                pass

            # Store goal state
            self.goals[goal_id] = {
                "goal_id": goal_id,
                "goal": goal_text,
                "goal_type": goal_type,
                "status": "in_progress",
                "subtasks": subtasks,
                "constraints": constraints,
                "created_at": datetime.utcnow().isoformat(),
                "research_task_id": None,
                "brp": brp_plan_meta,
            }

            # Sprint 42: For research/analysis goals, self-spawn a deep-research
            # sub-agent to gather background context in parallel with decomposition.
            research_task_id = None
            spawner = self._get_spawner()
            if spawner and goal_type in ("research", "analysis", "market_analysis", "planning"):
                try:
                    research_task_id = spawner.spawn(
                        description=f"Research: {goal_text[:60]}",
                        prompt=(
                            f"You are a deep research specialist.\n\n"
                            f"Goal: {goal_text}\n\n"
                            f"Constraints: {constraints}\n\n"
                            f"Provide a comprehensive research brief covering:\n"
                            f"1. Key aspects of the goal\n"
                            f"2. Relevant market/technical context\n"
                            f"3. Risks and uncertainties\n"
                            f"4. Recommended approach\n\n"
                            f"Return structured output: SUMMARY, KEY_FINDINGS[], RISKS[], RECOMMENDATION"
                        ),
                        agent_type="general-purpose",
                        parent_task_id=goal_id,
                        spawning_allowed=False,
                    )
                    self.goals[goal_id]["research_task_id"] = research_task_id
                except Exception as spawn_exc:
                    # Non-fatal — goal decomposition succeeds regardless
                    self.logger.warning(
                        "KloutbotAgent: research spawn failed for goal %s: %s",
                        goal_id, spawn_exc,
                    ) if hasattr(self, "logger") else None

            return {
                "type": "response",
                "status": "decomposed",
                "goal_id": goal_id,
                "goal_type": goal_type,
                "subtask_count": len(subtasks),
                "subtasks": [
                    {"task_type": st["task_type"], "description": st.get("description", ""), "title": st.get("title", "Subtask"), "order": st.get("order", i)}
                    for i, st in enumerate(subtasks)
                ],
                "research_task_id": research_task_id,
                "research_spawned": research_task_id is not None,
                "brp": brp_plan_meta,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error_code": "GOAL_DECOMPOSITION_FAILED",
                "error_message": str(e),
            }

    async def handle_check_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check the status of a goal and its subtasks.

        Input parameters:
        {
            "goal_id": "abc12345"
        }
        """
        goal_id = params.get("goal_id")
        if not goal_id:
            return {
                "status": "error",
                "error_code": "MISSING_GOAL_ID",
                "error_message": "A 'goal_id' parameter is required",
            }

        goal_state = self.goals.get(goal_id)
        if not goal_state:
            return {
                "status": "error",
                "error_code": "GOAL_NOT_FOUND",
                "error_message": f"No goal found with id: {goal_id}",
            }

        subtasks = goal_state.get("subtasks", [])
        completed = sum(1 for s in subtasks if s.get("status") == "completed")
        failed = sum(1 for s in subtasks if s.get("status") == "failed")
        total = len(subtasks)

        overall = "completed" if completed == total else "failed" if failed > 0 else "in_progress"
        goal_state["status"] = overall

        return {
            "status": "success",
            "goal_id": goal_id,
            "goal": goal_state.get("goal"),
            "goal_status": overall,
            "progress": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "remaining": total - completed - failed,
            },
            "subtasks": subtasks,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def handle_replan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Re-evaluate and adjust the plan for a goal based on current state.

        Input parameters:
        {
            "goal_id": "abc12345",
            "reason": "optional reason for replanning"
        }
        """
        goal_id = params.get("goal_id")
        if not goal_id:
            return {
                "status": "error",
                "error_code": "MISSING_GOAL_ID",
                "error_message": "A 'goal_id' parameter is required",
            }

        goal_state = self.goals.get(goal_id)
        if not goal_state:
            return {
                "status": "error",
                "error_code": "GOAL_NOT_FOUND",
                "error_message": f"No goal found with id: {goal_id}",
            }

        # Re-decompose from the current point: keep completed, regenerate remaining
        old_subtasks = goal_state.get("subtasks", [])
        completed_tasks = [s for s in old_subtasks if s.get("status") == "completed"]

        new_subtasks = self.task_decomposer.decompose(
            goal_state["goal"],
            goal_state["goal_type"],
            goal_state.get("constraints"),
        )

        # Skip task types that are already completed
        completed_types = {s["task_type"] for s in completed_tasks}
        remaining = [s for s in new_subtasks if s["task_type"] not in completed_types]

        goal_state["subtasks"] = completed_tasks + remaining
        goal_state["status"] = "in_progress"
        goal_state["replanned_at"] = datetime.utcnow().isoformat()

        return {
            "status": "success",
            "goal_id": goal_id,
            "reason": params.get("reason", "manual replan"),
            "kept_completed": len(completed_tasks),
            "new_remaining": len(remaining),
            "subtasks": goal_state["subtasks"],
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Sprint 42: Self-Spawning Research Handler
    # ------------------------------------------------------------------

    async def handle_research(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Spawn a deep-research subagent for a given topic.

        Input parameters:
        {
            "description": "Short label for the task",
            "prompt": "Full research brief / question",
            "agent_type": "general-purpose",   # optional
            "parent_task_id": "goal-abc123",    # optional
            "await_result": false               # optional — if true, block until done
        }

        Returns immediately with task_id unless await_result=true.
        """
        spawner = self._get_spawner()
        if spawner is None:
            return {
                "status": "error",
                "error_code": "SPAWNER_UNAVAILABLE",
                "error_message": (
                    "DeerFlow spawner not yet active. "
                    "Start the orchestration loop first."
                ),
            }

        description = params.get("description", "Research sub-task")
        prompt = params.get("prompt", "")
        if not prompt:
            return {
                "status": "error",
                "error_code": "MISSING_PROMPT",
                "error_message": "A 'prompt' parameter is required for research tasks",
            }

        agent_type = params.get("agent_type", "general-purpose")
        parent_task_id = params.get("parent_task_id")
        should_await = params.get("await_result", False)

        try:
            task_id = spawner.spawn(
                description=description[:80],
                prompt=prompt,
                agent_type=agent_type,
                parent_task_id=parent_task_id,
                spawning_allowed=False,
            )

            if should_await:
                task = await spawner.await_result(task_id)
                return {
                    "status": "success",
                    "task_id": task_id,
                    "task_status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return {
                "status": "success",
                "task_id": task_id,
                "task_status": "spawned",
                "stream_url": f"/tasks/{task_id}/stream",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            return {
                "status": "error",
                "error_code": "SPAWN_FAILED",
                "error_message": str(exc),
            }

    def _add_to_history(self, tree: DecisionTree):
        """Add strategy to history, maintaining max size"""
        self.strategy_history.append(tree)
        if len(self.strategy_history) > self.max_history:
            self.strategy_history = self.strategy_history[-self.max_history:]


class MutationMemory:
    """
    Mutation Memory System for Kloutbot

    Tracks successful strategy mutations and learns from them.
    Enables self-improvement through recorded adaptations.
    """

    def __init__(self, max_memories: int = 1000):
        """Initialize mutation memory"""
        self.memories: List[Dict[str, Any]] = []
        self.max_memories = max_memories
        self.success_count = 0
        self.failure_count = 0
        self._knowledge_index = KnowledgeIndex()
        self._load_persisted_mutations()

    def _load_persisted_mutations(self):
        """Load mutation history from knowledge index."""
        try:
            entries = self._knowledge_index.search("mutation_memory")
            if entries:
                for entry in entries:
                    if isinstance(entry, dict):
                        self.memories.append(entry)
                        if entry.get("result") == "success" or entry.get("success"):
                            self.success_count += 1
                        elif entry.get("result") == "failure":
                            self.failure_count += 1
        except Exception:
            pass

    def record_mutation(
        self,
        original_tree: DecisionTree,
        mutated_tree: DecisionTree,
        result: str  # "success" or "failure"
    ):
        """Record a mutation and its result"""
        memory = {
            "timestamp": datetime.utcnow().isoformat(),
            "original_utility": self.calculate_utility(original_tree),
            "mutated_utility": self.calculate_utility(mutated_tree),
            "result": result,
            "success": result == "success",
            "improvement": self.calculate_utility(mutated_tree) - self.calculate_utility(original_tree)
        }

        self.memories.append(memory)

        if result == "success":
            self.success_count += 1
        else:
            self.failure_count += 1

        # Maintain max size
        if len(self.memories) > self.max_memories:
            self.memories = self.memories[-self.max_memories:]

        # Persist to knowledge index
        try:
            self._knowledge_index.add_entry(
                category="mutation_memory",
                data=memory,
            )
        except Exception:
            pass

    def get_success_rate(self) -> float:
        """Calculate mutation success rate"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    def get_average_improvement(self) -> float:
        """Calculate average utility improvement per successful mutation"""
        successes = [m for m in self.memories if m["result"] == "success"]
        if not successes:
            return 0.0
        return sum(m["improvement"] for m in successes) / len(successes)

    def get_status(self) -> Dict[str, Any]:
        """Get mutation memory status"""
        return {
            "memories_recorded": len(self.memories),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.get_success_rate(),
            "avg_improvement": self.get_average_improvement(),
            "max_capacity": self.max_memories
        }

    @staticmethod
    def calculate_utility(tree: DecisionTree) -> float:
        """Calculate utility of a tree"""
        if not tree.branches:
            return 0.0
        return sum(b.value * b.foresight for b in tree.branches) / len(tree.branches)
