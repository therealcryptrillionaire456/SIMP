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

        # Get unclaimed tasks from the queue
        queue = self.task_ledger.get_queue()
        summary["tasks_checked"] = len(queue)

        if not queue:
            return summary

        for task in queue:
            task_id = task.get("task_id")
            task_type = task.get("task_type", "implementation")

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

            # Route intent to the builder
            intent_data = {
                "intent_id": f"orch:{uuid.uuid4()}",
                "source_agent": "orchestration_loop",
                "target_agent": builder,
                "intent_type": task_type,
                "params": {
                    "task_id": task_id,
                    "title": task.get("title", ""),
                    "description": task.get("description", ""),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            result = await self.broker.route_intent(intent_data)
            delivery_status = result.get("delivery_status", "")

            if delivery_status in ("delivered", "queued", "queued_no_endpoint"):
                self.tasks_assigned += 1
                summary["tasks_assigned"] += 1
                self.logger.info(
                    f"Assigned task {task_id} to {builder} ({delivery_status})"
                )
            else:
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
                        intent_data["target_agent"] = fallback
                        retry_result = await self.broker.route_intent(intent_data)
                        retry_status = retry_result.get("delivery_status", "")
                        if retry_status in ("delivered", "queued", "queued_no_endpoint"):
                            self.tasks_assigned += 1
                            summary["tasks_assigned"] += 1
                            self.logger.info(
                                f"Fallback: assigned task {task_id} to {fallback}"
                            )
                            continue

                self.tasks_failed += 1
                summary["tasks_failed"] += 1
                self.logger.warning(
                    f"Failed to assign task {task_id}: {delivery_status}"
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
