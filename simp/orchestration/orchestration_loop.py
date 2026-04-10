"""
SIMP Orchestration Loop

Autonomous work loop that polls the task queue, assigns work to builders,
tracks results, and handles failures via retry/fallback policies.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from simp.task_ledger import TaskLedger
from simp.models.failure_taxonomy import FailureHandler
from simp.routing.builder_pool import BuilderPool

# ── BRP integration (shadow mode — never blocks task assignment by default) ────
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


# ── DeerFlow upgrades: lazy-loaded, non-blocking if scaffolding absent ────────
_deerflow_runtime = None

def _get_deerflow_runtime():
    """
    Lazy-load the DeerFlowUpgradeRuntime (LoopGuard + SkillLoader + Spawner).
    Called once on first use; result cached.  Non-fatal if unavailable.
    """
    global _deerflow_runtime
    if _deerflow_runtime is not None:
        return _deerflow_runtime
    try:
        import sys, pathlib, logging
        _scaffold = str(pathlib.Path(__file__).resolve().parents[4] /
                        "ProjectX" / "proposals" / "scaffolding")
        if _scaffold not in sys.path:
            sys.path.insert(0, _scaffold)
        from draft_projectx_deerflow_upgrades_init import initialize_deerflow_upgrades
        _deerflow_runtime = initialize_deerflow_upgrades(
            start_skill_hot_reload=True,
            dry_run_bash=False,
        )
        logging.getLogger("SIMP.Orchestration").info(
            "✅ DeerFlow upgrades loaded: skills=%d",
            len(_deerflow_runtime.skill_loader.registry),
        )
    except Exception as exc:
        logging.getLogger("SIMP.Orchestration").debug(
            "DeerFlow upgrades not available (non-critical): %s", exc
        )
    return _deerflow_runtime


class OrchestrationLoop:
    """
    Autonomous orchestration loop.

    Polls the task queue, assigns work to the best available builder,
    tracks results, and handles failures via FailureHandler + BuilderPool.
    """

    def __init__(
        self,
        broker,
        task_ledger: Optional[TaskLedger] = None,
        builder_pool: Optional[BuilderPool] = None,
        failure_handler: Optional[FailureHandler] = None,
    ):
        self.broker = broker
        self.task_ledger = task_ledger or broker.task_ledger
        self.builder_pool = builder_pool or broker.builder_pool
        self.failure_handler = failure_handler or broker.failure_handler

        self.logger = logging.getLogger("SIMP.Orchestration")
        self.logger.setLevel(logging.INFO)

        self.running = False
        self.tasks_assigned = 0
        self.tasks_completed = 0
        self.tasks_failed = 0

    async def run_once(self) -> Dict[str, Any]:
        """
        Single iteration: check queue, assign, collect results.

        Returns:
            Summary dict of what happened this iteration.
        """
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "tasks_checked": 0,
            "tasks_assigned": 0,
            "tasks_failed": 0,
        }

        # Sprint 22: Check for routing policy hot-reload
        if self.builder_pool:
            self.builder_pool.check_reload()

        # Sprint 40: DeerFlow upgrades — skill hot-reload check
        _df = _get_deerflow_runtime()
        if _df:
            try:
                _df.skill_loader.check_reload()
            except Exception:
                pass

        # Get unclaimed tasks from the queue (sorted by priority: critical first)
        queue = self.task_ledger.get_queue()
        summary["tasks_checked"] = len(queue)

        if not queue:
            return summary

        for task in queue:
            task_id = task.get("task_id")
            task_type = task.get("task_type", "implementation")
            priority = task.get("priority", "medium")

            # Enforce task dependency ordering for subtasks
            parent_id = task.get("parent_task_id")
            order = task.get("order", 0)
            if parent_id and order > 0:
                all_tasks = self.task_ledger.list_tasks()
                predecessors = [
                    s for s in all_tasks
                    if s.get("parent_task_id") == parent_id and s.get("order", 0) < order
                ]
                incomplete = [s for s in predecessors if s.get("status") not in ("completed",)]
                if incomplete:
                    if task.get("status") != "blocked":
                        self.task_ledger.update_status(task_id, "blocked")
                    continue

            if not self.builder_pool:
                self.logger.warning("No builder pool configured — cannot assign tasks")
                break

            # Find best builder for this task type
            builder = self.builder_pool.get_builder(task_type)
            if not builder:
                self.logger.debug(f"No available builder for task type: {task_type}")
                continue

            # Check that the builder is a registered agent
            agent = self.broker.get_agent(builder)
            if not agent:
                self.logger.debug(f"Builder {builder} not registered as agent")
                continue

            # Sprint 22: Track task assignment in builder pool
            self.builder_pool.report_task_assigned(builder)

            # Sprint 40: DeerFlow upgrades — inject skill context for this task type
            _skill_context = ""
            if _df:
                try:
                    _skill_context = _df.skill_loader.registry.get_prompt_context(task_type)
                except Exception:
                    pass

            # Route intent to the builder — forward task_id so broker reuses it
            intent_data = {
                "intent_id": f"orch:{uuid.uuid4()}",
                "source_agent": "orchestration_loop",
                "target_agent": builder,
                "intent_type": task_type,
                "task_id": task_id,
                "params": {
                    "task_id": task_id,
                    "title": task.get("title", ""),
                    "description": task.get("description", ""),
                    "priority": priority,
                    # DeerFlow skill context injected here — agents consume via params
                    "skill_context": _skill_context,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            # BRP pre-action event: evaluate task assignment
            brp_event_id = ""
            brp_blocked = False
            try:
                bridge = _get_brp_bridge()
                if bridge is not None:
                    from simp.security.brp_models import (
                        BRPEvent, BRPEventType, BRPMode, BRPDecision,
                    )
                    brp_event = BRPEvent(
                        source_agent=builder,
                        event_type=BRPEventType.TASK_ASSIGNMENT.value,
                        action=task_type,
                        context={
                            "task_id": task_id,
                            "priority": priority,
                            "builder": builder,
                            "title": task.get("title", ""),
                        },
                        mode=BRPMode.SHADOW.value,
                        tags=["orchestration_loop", "task_assignment", task_type],
                    )
                    brp_event_id = brp_event.event_id
                    brp_resp = bridge.evaluate_event(brp_event)
                    intent_data["brp"] = {
                        "event_id": brp_event_id,
                        "decision": brp_resp.decision,
                        "threat_score": brp_resp.threat_score,
                    }

                    # In enforced mode, DENY blocks the task assignment
                    if brp_resp.mode == BRPMode.ENFORCED.value and brp_resp.decision == BRPDecision.DENY.value:
                        self.logger.warning(
                            "BRP DENY (enforced) for task %s — marking blocked", task_id,
                        )
                        self.task_ledger.update_status(task_id, "blocked")
                        brp_blocked = True
            except Exception:
                pass

            if brp_blocked:
                continue

            result = await self.broker.route_intent(intent_data)
            delivery_status = result.get("delivery_status", "")

            # BRP post-action observation
            try:
                bridge = _get_brp_bridge()
                if bridge is not None:
                    from simp.security.brp_models import BRPObservation, BRPMode
                    obs = BRPObservation(
                        source_agent="orchestration_loop",
                        event_id=brp_event_id,
                        action=task_type,
                        outcome="success" if delivery_status in ("delivered", "queued", "queued_no_endpoint") else "failure",
                        result_data={
                            "delivery_status": delivery_status,
                            "task_id": task_id,
                            "builder": builder,
                        },
                        mode=BRPMode.SHADOW.value,
                        tags=["orchestration_loop", "task_assignment"],
                    )
                    bridge.ingest_observation(obs)
            except Exception:
                pass

            if delivery_status in ("delivered", "queued", "queued_no_endpoint"):
                self.tasks_assigned += 1
                summary["tasks_assigned"] += 1
                self.logger.info(
                    f"Assigned task {task_id} [{priority}] to {builder} ({delivery_status})"
                )
            else:
                # Sprint 22: Track task completion on failure (undo the assignment)
                self.builder_pool.report_task_completed(builder)

                # Delivery failed — classify and attempt fallback
                error_resp = {
                    "error_code": result.get("error_code", "DELIVERY_FAILED"),
                    "error_message": result.get("error_message", ""),
                }
                fc = self.failure_handler.classify_failure(error_resp)
                policy = self.failure_handler.get_retry_policy(fc)

                if policy.get("should_retry"):
                    fallback = self.failure_handler.get_fallback_agent(
                        fc, task_type, self.builder_pool, exclude=[builder]
                    )
                    if fallback and self.broker.get_agent(fallback):
                        self.builder_pool.report_task_assigned(fallback)
                        intent_data["target_agent"] = fallback
                        retry_result = await self.broker.route_intent(intent_data)
                        retry_status = retry_result.get("delivery_status", "")
                        if retry_status in ("delivered", "queued", "queued_no_endpoint"):
                            self.tasks_assigned += 1
                            summary["tasks_assigned"] += 1
                            self.logger.info(
                                f"Fallback: assigned task {task_id} [{priority}] to {fallback}"
                            )
                            continue
                        else:
                            self.builder_pool.report_task_completed(fallback)

                self.tasks_failed += 1
                summary["tasks_failed"] += 1

                # Track assignment failures — expire task after max retries
                retry_count = task.get("retry_count", 0) + 1
                max_retries = task.get("max_retries", 3)
                self.task_ledger.fail_task(
                    task_id,
                    error={"reason": f"Assignment failed: {delivery_status}"},
                    failure_class="agent_unavailable",
                )
                if retry_count >= max_retries:
                    self.logger.warning(
                        f"Task {task_id} [{priority}] permanently failed after {retry_count} retries"
                    )
                else:
                    self.logger.warning(
                        f"Failed to assign task {task_id} [{priority}]: {delivery_status} "
                        f"(attempt {retry_count}/{max_retries})"
                    )

        return summary

    async def run(self, interval_seconds: float = 10.0) -> None:
        """Run the orchestration loop continuously."""
        self.running = True
        self.logger.info(
            f"Orchestration loop started (interval={interval_seconds}s)"
        )

        while self.running:
            try:
                await self.run_once()
            except Exception as exc:
                self.logger.error(f"Orchestration loop error: {exc}")
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        """Stop the orchestration loop."""
        self.running = False
        self.logger.info("Orchestration loop stopped")

    def get_status(self) -> Dict[str, Any]:
        """Return current orchestration loop status."""
        return {
            "running": self.running,
            "tasks_assigned": self.tasks_assigned,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "timestamp": datetime.utcnow().isoformat(),
        }
