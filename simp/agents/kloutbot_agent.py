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
from simp.agents.q_intent_compiler import QIntentCompiler, DecisionTree
from simp.orchestration.task_decomposer import TaskDecomposer


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
        self.strategy_history: List[DecisionTree] = []
        self.max_history = 100

        # Orchestration state
        self.task_decomposer = TaskDecomposer()
        self.goals: Dict[str, Dict[str, Any]] = {}  # goal_id -> goal state

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

            # Convert to actionable parameters
            action_params = self.compiler.get_action_params(tree)

            return {
                "status": "success",
                "strategy": tree.to_dict(),
                "action_params": action_params,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
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
                    "error_message": "Foresight and deltas required"
                }

            # Analyze signal strength
            signal_strength = sum(deltas.values()) / len(deltas) if deltas else 0.5
            confidence = foresight.get("affinity", 0.5)
            risk = foresight.get("drift_risk", 0.1)

            # Signal quality score
            quality = (signal_strength * confidence) / (1 + risk)

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
                "error_message": str(e)
            }

    async def handle_improve_tree(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively improve an existing decision tree

        This handles mutation/memory operations for incremental optimization.
        """
        try:
            tree_data = params.get("tree")
            iterations = params.get("iterations", 3)

            if not tree_data:
                return {
                    "status": "error",
                    "error_message": "Tree data required"
                }

            # Note: In production, would reconstruct DecisionTree from data
            # For now, return analysis
            return {
                "status": "success",
                "message": f"Tree improvement iterations: {iterations}",
                "estimated_improvement": iterations * 0.15,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e)
            }

    async def handle_get_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current status of Kloutbot agent"""
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

            # Store goal state
            self.goals[goal_id] = {
                "goal_id": goal_id,
                "goal": goal_text,
                "goal_type": goal_type,
                "status": "in_progress",
                "subtasks": subtasks,
                "constraints": constraints,
                "created_at": datetime.utcnow().isoformat(),
            }

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
