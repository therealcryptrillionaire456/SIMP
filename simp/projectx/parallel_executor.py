"""
ProjectX Parallel Executor — Phase 5

Async-native task distribution layer that runs multiple agent subtasks
concurrently while enforcing resource limits and collecting results.

Design:
  - asyncio-based, compatible with existing synchronous callers via run_sync()
  - Each TaskSpec defines an action + params + timeout + priority
  - TaskBatch collects specs and returns a BatchResult
  - Resource budget: max concurrent tasks, max total wall-clock time
  - Fault isolation: one task failing never cancels siblings

Integration:
  - ProjectXComputer.safe_execute() is the default executor for shell/GUI tasks
  - Custom executors can be passed per-task for LLM/API calls
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default limits
DEFAULT_MAX_CONCURRENT = 8
DEFAULT_TASK_TIMEOUT = 60       # seconds per task
DEFAULT_BATCH_TIMEOUT = 300     # seconds for the whole batch


@dataclass
class TaskSpec:
    """A single unit of work for parallel execution."""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: float = DEFAULT_TASK_TIMEOUT
    priority: int = 5              # 1 (high) → 10 (low)
    executor: Optional[Callable] = None  # override per-task executor
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskOutcome:
    """Result of a single parallel task."""
    task_id: str
    name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    latency_ms: int = 0
    timed_out: bool = False


@dataclass
class BatchResult:
    """Aggregated results from a TaskBatch run."""
    batch_id: str
    outcomes: List[TaskOutcome]
    total_ms: int
    max_concurrent: int

    @property
    def success_count(self) -> int:
        return sum(1 for o in self.outcomes if o.success)

    @property
    def failure_count(self) -> int:
        return len(self.outcomes) - self.success_count

    @property
    def success_rate(self) -> float:
        return self.success_count / len(self.outcomes) if self.outcomes else 0.0

    def get(self, task_id: str) -> Optional[TaskOutcome]:
        return next((o for o in self.outcomes if o.task_id == task_id), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_ms": self.total_ms,
            "task_count": len(self.outcomes),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "outcomes": [
                {
                    "task_id": o.task_id,
                    "name": o.name,
                    "success": o.success,
                    "latency_ms": o.latency_ms,
                    "timed_out": o.timed_out,
                    "error": o.error,
                }
                for o in self.outcomes
            ],
        }


class ParallelExecutor:
    """
    Runs a batch of TaskSpecs concurrently using asyncio.

    Usage (async)::

        executor = ParallelExecutor(computer=my_computer)
        batch = [
            TaskSpec(name="health_check", action="check_protocol_health"),
            TaskSpec(name="screenshot",   action="get_screenshot"),
        ]
        result = await executor.run_batch_async(batch)

    Usage (sync)::

        result = executor.run_batch(batch)
    """

    def __init__(
        self,
        computer=None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        default_timeout: float = DEFAULT_TASK_TIMEOUT,
        batch_timeout: float = DEFAULT_BATCH_TIMEOUT,
    ) -> None:
        self._computer = computer
        self._max_concurrent = max_concurrent
        self._default_timeout = default_timeout
        self._batch_timeout = batch_timeout
        self._semaphore: Optional[asyncio.Semaphore] = None

    # ── Public API ────────────────────────────────────────────────────────

    def run_batch(self, tasks: List[TaskSpec]) -> BatchResult:
        """Synchronous wrapper — safe to call from non-async code."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an existing loop (e.g., Jupyter) — use a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self.run_batch_async(tasks))
                    return future.result()
            else:
                return loop.run_until_complete(self.run_batch_async(tasks))
        except RuntimeError:
            return asyncio.run(self.run_batch_async(tasks))

    async def run_batch_async(self, tasks: List[TaskSpec]) -> BatchResult:
        """Run a batch of tasks concurrently, respecting max_concurrent."""
        batch_id = uuid.uuid4().hex[:8]
        semaphore = asyncio.Semaphore(self._max_concurrent)
        t0 = time.time()

        # Sort by priority (lower number = higher priority)
        sorted_tasks = sorted(tasks, key=lambda t: t.priority)

        coros = [self._run_one(task, semaphore) for task in sorted_tasks]
        try:
            # return_exceptions=True: one failing coroutine never cancels siblings
            raw = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                timeout=self._batch_timeout,
            )
            outcomes = []
            for i, item in enumerate(raw):
                if isinstance(item, BaseException):
                    task = sorted_tasks[i]
                    outcomes.append(TaskOutcome(
                        task_id=task.task_id, name=task.name, success=False,
                        error=f"Unhandled exception: {item}",
                    ))
                else:
                    outcomes.append(item)
        except asyncio.TimeoutError:
            logger.warning("Batch %s timed out after %ss", batch_id, self._batch_timeout)
            outcomes = [
                TaskOutcome(task_id=t.task_id, name=t.name, success=False,
                            error="Batch timeout", timed_out=True)
                for t in sorted_tasks
            ]

        total_ms = int((time.time() - t0) * 1000)
        result = BatchResult(
            batch_id=batch_id,
            outcomes=list(outcomes),
            total_ms=total_ms,
            max_concurrent=self._max_concurrent,
        )
        logger.info(
            "Batch %s done: %d/%d ok in %dms",
            batch_id, result.success_count, len(tasks), total_ms,
        )
        return result

    async def run_one_async(self, task: TaskSpec) -> TaskOutcome:
        """Run a single task in isolation (no semaphore)."""
        return await self._run_one(task, semaphore=None)

    # ── Internal ──────────────────────────────────────────────────────────

    async def _run_one(
        self, task: TaskSpec, semaphore: Optional[asyncio.Semaphore]
    ) -> TaskOutcome:
        timeout = task.timeout or self._default_timeout

        async def _execute():
            t0 = time.time()
            try:
                result = await self._dispatch(task)
                latency = int((time.time() - t0) * 1000)
                return TaskOutcome(
                    task_id=task.task_id,
                    name=task.name,
                    success=True,
                    result=result,
                    latency_ms=latency,
                )
            except Exception as exc:
                latency = int((time.time() - t0) * 1000)
                logger.warning("Task %s (%s) failed: %s", task.task_id, task.name, exc)
                return TaskOutcome(
                    task_id=task.task_id,
                    name=task.name,
                    success=False,
                    error=str(exc),
                    latency_ms=latency,
                )

        if semaphore:
            async with semaphore:
                try:
                    return await asyncio.wait_for(_execute(), timeout=timeout)
                except asyncio.TimeoutError:
                    return TaskOutcome(
                        task_id=task.task_id,
                        name=task.name,
                        success=False,
                        error=f"Timed out after {timeout}s",
                        timed_out=True,
                    )
        else:
            try:
                return await asyncio.wait_for(_execute(), timeout=timeout)
            except asyncio.TimeoutError:
                return TaskOutcome(
                    task_id=task.task_id,
                    name=task.name,
                    success=False,
                    error=f"Timed out after {timeout}s",
                    timed_out=True,
                )

    async def _dispatch(self, task: TaskSpec) -> Any:
        """Dispatch a task to the right executor."""
        # Custom per-task executor
        if task.executor is not None:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: task.executor(task.action, task.params)
            )
            return result

        # ProjectXComputer executor
        if self._computer is not None and task.action:
            step = {"action": task.action, "params": task.params}
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: self._computer.safe_execute(step)
            )
            return result

        # Generic callable in params["fn"]
        if "fn" in task.params and callable(task.params["fn"]):
            fn = task.params.pop("fn")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: fn(**task.params))
            return result

        raise ValueError(f"No executor available for task '{task.name}' (action='{task.action}')")
