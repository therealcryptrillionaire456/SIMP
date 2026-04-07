"""
SIMP Orchestration Manager — Sprint 54

Creates and executes multi-step orchestration plans.
Each step emits an A2A event and writes to the orchestration log.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SIMP.Orchestration")

_LOG_PATH = Path("data/orchestration_log.jsonl")


# ---------------------------------------------------------------------------
# Enums / dataclasses
# ---------------------------------------------------------------------------

class OrchestrationStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class OrchestrationStep:
    step_id: str = ""
    name: str = ""
    intent_type: str = ""
    target_agent: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = OrchestrationStepStatus.PENDING.value
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "intent_type": self.intent_type,
            "target_agent": self.target_agent,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class OrchestrationPlan:
    plan_id: str = ""
    name: str = ""
    description: str = ""
    steps: List[OrchestrationStep] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    created_at: str = ""
    completed_at: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# OrchestrationManager
# ---------------------------------------------------------------------------

class OrchestrationManager:
    """
    Creates and executes multi-step orchestration plans.

    Execution is sequential: each step runs in order, emits an A2A
    event, and stops on the first failure.
    """

    def __init__(self, broker=None):
        self._plans: Dict[str, OrchestrationPlan] = {}
        self._broker = broker
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    def create_plan(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
    ) -> OrchestrationPlan:
        """Create a new orchestration plan (does not execute)."""
        plan = OrchestrationPlan(
            plan_id=str(uuid.uuid4()),
            name=name,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        for i, s in enumerate(steps):
            plan.steps.append(OrchestrationStep(
                step_id=s.get("step_id", f"step-{i}"),
                name=s.get("name", f"Step {i}"),
                intent_type=s.get("intent_type", ""),
                target_agent=s.get("target_agent", "auto"),
                params=s.get("params", {}),
            ))
        self._plans[plan.plan_id] = plan
        return plan

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute_plan(self, plan_id: str) -> OrchestrationPlan:
        """
        Execute all steps in sequence.  Stops on first failure.
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise KeyError(f"Plan {plan_id} not found")

        plan.status = "running"
        self._log_event(plan, "plan_started")

        for step in plan.steps:
            step.status = OrchestrationStepStatus.RUNNING.value
            step.started_at = datetime.now(timezone.utc).isoformat()
            self._log_event(plan, "step_started", step=step)

            try:
                result = self._execute_step(step)
                step.status = OrchestrationStepStatus.COMPLETED.value
                step.result = result
                step.completed_at = datetime.now(timezone.utc).isoformat()
                self._log_event(plan, "step_completed", step=step)
            except Exception as exc:
                step.status = OrchestrationStepStatus.FAILED.value
                step.error = str(exc)
                step.completed_at = datetime.now(timezone.utc).isoformat()
                self._log_event(plan, "step_failed", step=step)

                plan.status = "failed"
                plan.error = f"Step {step.step_id} failed: {exc}"
                plan.completed_at = datetime.now(timezone.utc).isoformat()
                self._log_event(plan, "plan_failed")
                return plan

        plan.status = "completed"
        plan.completed_at = datetime.now(timezone.utc).isoformat()
        self._log_event(plan, "plan_completed")
        return plan

    def _execute_step(self, step: OrchestrationStep) -> Dict[str, Any]:
        """Execute a single step by routing an intent through the broker."""
        if self._broker is None:
            # No broker wired — simulate success
            return {"simulated": True, "step_id": step.step_id}

        import asyncio

        intent_data = {
            "intent_id": f"orch-{step.step_id}-{uuid.uuid4().hex[:8]}",
            "source_agent": "orchestrator",
            "target_agent": step.target_agent,
            "intent_type": step.intent_type,
            "params": step.params,
        }

        # Run async route_intent synchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run, self._broker.route_intent(intent_data)
                    ).result(timeout=30)
            else:
                result = loop.run_until_complete(self._broker.route_intent(intent_data))
        except RuntimeError:
            result = asyncio.run(self._broker.route_intent(intent_data))

        if result.get("status") == "error":
            raise RuntimeError(result.get("error_message", "Routing failed"))
        return result

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def get_plan(self, plan_id: str) -> Optional[OrchestrationPlan]:
        return self._plans.get(plan_id)

    def list_plans(self) -> List[Dict[str, Any]]:
        return [
            {
                "plan_id": p.plan_id,
                "name": p.name,
                "status": p.status,
                "created_at": p.created_at,
                "step_count": len(p.steps),
            }
            for p in self._plans.values()
        ]

    # ------------------------------------------------------------------
    # plan templates
    # ------------------------------------------------------------------

    def make_maintenance_plan(self) -> OrchestrationPlan:
        """Pre-built maintenance plan template."""
        return self.create_plan(
            name="System Maintenance",
            description="Standard system health check and maintenance routine",
            steps=[
                {"name": "Health Check", "intent_type": "ping", "target_agent": "auto"},
                {"name": "Log Analysis", "intent_type": "analysis", "target_agent": "auto", "params": {"scope": "logs"}},
                {"name": "Report", "intent_type": "notification", "target_agent": "auto", "params": {"type": "maintenance_report"}},
            ],
        )

    def make_analysis_plan(self) -> OrchestrationPlan:
        """Pre-built analysis plan template."""
        return self.create_plan(
            name="Market Analysis",
            description="Multi-step market analysis pipeline",
            steps=[
                {"name": "Data Collection", "intent_type": "research", "target_agent": "auto", "params": {"scope": "market_data"}},
                {"name": "Signal Analysis", "intent_type": "prediction_signal", "target_agent": "auto", "params": {"scope": "signals"}},
                {"name": "Risk Assessment", "intent_type": "risk_assessment", "target_agent": "auto", "params": {"scope": "portfolio"}},
                {"name": "Strategy Generation", "intent_type": "generate_strategy", "target_agent": "auto"},
            ],
        )

    def make_full_demo_plan(self) -> OrchestrationPlan:
        """Pre-built demo plan that exercises multiple agent types."""
        return self.create_plan(
            name="Full Demo",
            description="End-to-end demonstration of orchestrated multi-agent workflow",
            steps=[
                {"name": "Ping All", "intent_type": "ping", "target_agent": "auto"},
                {"name": "Research Phase", "intent_type": "research", "target_agent": "auto", "params": {"topic": "demo"}},
                {"name": "Analysis Phase", "intent_type": "analysis", "target_agent": "auto", "params": {"scope": "demo"}},
                {"name": "Planning Phase", "intent_type": "planning", "target_agent": "auto", "params": {"goal": "demo"}},
                {"name": "Notification", "intent_type": "notification", "target_agent": "auto", "params": {"type": "demo_complete"}},
            ],
        )

    # ------------------------------------------------------------------
    # logging
    # ------------------------------------------------------------------

    def _log_event(
        self,
        plan: OrchestrationPlan,
        event_kind: str,
        step: Optional[OrchestrationStep] = None,
    ) -> None:
        """Append an event to orchestration_log.jsonl."""
        entry: Dict[str, Any] = {
            "event_kind": event_kind,
            "plan_id": plan.plan_id,
            "plan_name": plan.name,
            "plan_status": plan.status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if step:
            entry["step_id"] = step.step_id
            entry["step_name"] = step.name
            entry["step_status"] = step.status
            if step.error:
                entry["error"] = step.error
        try:
            with open(_LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
                fh.flush()
        except Exception as exc:
            logger.error("Orchestration log write failed: %s", exc)
