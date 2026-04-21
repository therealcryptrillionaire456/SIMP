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
_PLANS_PATH = Path("data/orchestration_plans.jsonl")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class OrchestrationManagerConfig:
    """Configuration for OrchestrationManager persistence."""
    log_path: Path = _LOG_PATH
    plans_path: Path = _PLANS_PATH
    max_plans: int = 1000  # Maximum number of plans to keep in persistence
    persistence_enabled: bool = True  # Whether to persist plans to disk


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationStep":
        """Create an OrchestrationStep from serialized data."""
        return cls(
            step_id=data.get("step_id", ""),
            name=data.get("name", ""),
            intent_type=data.get("intent_type", ""),
            target_agent=data.get("target_agent", ""),
            params=data.get("params", {}),
            status=data.get("status", OrchestrationStepStatus.PENDING.value),
            result=data.get("result"),
            error=data.get("error", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
        )


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationPlan":
        """Create an OrchestrationPlan from serialized data."""
        steps_data = data.get("steps", [])
        steps = [OrchestrationStep.from_dict(step_data) for step_data in steps_data]
        
        return cls(
            plan_id=data.get("plan_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=steps,
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error", ""),
        )


# ---------------------------------------------------------------------------
# OrchestrationManager
# ---------------------------------------------------------------------------

class OrchestrationManager:
    """
    Creates and executes multi-step orchestration plans.

    Execution is sequential: each step runs in order, emits an A2A
    event, and stops on the first failure.
    """

    def __init__(self, broker=None, config: Optional[OrchestrationManagerConfig] = None):
        self._plans: Dict[str, OrchestrationPlan] = {}
        self._broker = broker
        self.config = config or OrchestrationManagerConfig()
        
        # Ensure directories exist
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.plans_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing plans from disk
        self._load_plans()

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def _load_plans(self) -> None:
        """Load all plans from disk."""
        if not self.config.persistence_enabled:
            return
        if not self.config.plans_path.exists():
            logger.info("Orchestration plans file not found: %s", self.config.plans_path)
            return
        
        try:
            with open(self.config.plans_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        plan_data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("OrchestrationManager: skipping corrupt line in plans file")
                        continue
                    
                    try:
                        plan = OrchestrationPlan.from_dict(plan_data)
                        self._plans[plan.plan_id] = plan
                    except Exception as exc:
                        logger.error("Failed to load plan from disk: %s", exc)
            
            logger.info("Loaded %d plans from %s", len(self._plans), self.config.plans_path)
        except Exception as exc:
            logger.error("OrchestrationManager._load_plans failed: %s", exc)

    def _save_plan(self, plan: OrchestrationPlan) -> None:
        """Save a plan to disk (append to JSONL file)."""
        if not self.config.persistence_enabled:
            return
        try:
            plan_data = plan.to_dict()
            with open(self.config.plans_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(plan_data, default=str) + "\n")
                fh.flush()
            
            # Check if we need to rotate the file
            self._rotate_plans_file_if_needed()
        except Exception as exc:
            logger.error("Failed to save plan to disk: %s", exc)

    def _rotate_plans_file_if_needed(self) -> None:
        """Rotate plans file if it exceeds size limit."""
        try:
            if self.config.plans_path.exists():
                size_mb = self.config.plans_path.stat().st_size / (1024 * 1024)
                if size_mb > 10.0:  # 10MB limit
                    logger.warning("Orchestration plans file exceeds 10MB, rotating...")
                    # In production, we'd rotate the file
                    # For now, just log a warning
        except Exception as exc:
            logger.error("Failed to check plans file size: %s", exc)

    def _update_plan_in_storage(self, plan: OrchestrationPlan) -> None:
        """
        Update a plan in persistent storage.
        
        Since we're using append-only JSONL, we can't update in place.
        Instead, we rewrite the entire file with current plans.
        This is inefficient for large files but simple and correct.
        """
        if not self.config.persistence_enabled:
            return
        try:
            # Write all plans to a temporary file
            temp_path = self.config.plans_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as fh:
                for p in self._plans.values():
                    plan_data = p.to_dict()
                    fh.write(json.dumps(plan_data, default=str) + "\n")
            
            # Replace the original file
            temp_path.replace(self.config.plans_path)
            logger.debug("Updated plan %s in persistent storage", plan.plan_id)
        except Exception as exc:
            logger.error("Failed to update plan in storage: %s", exc)

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
        # Save to disk
        self._save_plan(plan)
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
        self._update_plan_in_storage(plan)  # Update storage

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
                self._update_plan_in_storage(plan)  # Update storage after step completes
            except Exception as exc:
                step.status = OrchestrationStepStatus.FAILED.value
                step.error = str(exc)
                step.completed_at = datetime.now(timezone.utc).isoformat()
                self._log_event(plan, "step_failed", step=step)

                plan.status = "failed"
                plan.error = f"Step {step.step_id} failed: {exc}"
                plan.completed_at = datetime.now(timezone.utc).isoformat()
                self._log_event(plan, "plan_failed")
                self._update_plan_in_storage(plan)  # Update storage after plan fails
                return plan

        plan.status = "completed"
        plan.completed_at = datetime.now(timezone.utc).isoformat()
        self._log_event(plan, "plan_completed")
        self._update_plan_in_storage(plan)  # Update storage after plan completes
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
        if not self.config.persistence_enabled:
            return
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
            with open(self.config.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
                fh.flush()
        except Exception as exc:
            logger.error("Orchestration log write failed: %s", exc)
