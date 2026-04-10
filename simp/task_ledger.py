"""
SIMP Task Ledger — Append-only JSONL-backed durable task store.

Provides persistent task tracking with claim/lock semantics.
Thread-safe for use with the multi-threaded broker.
Storage: JSONL file at data/task_ledger.jsonl (append-only, in-memory index).
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Valid values for task fields
VALID_TASK_TYPES = frozenset({
    "spec", "architecture", "scaffold", "implementation",
    "test", "docs", "research", "analysis",
})
VALID_STATUSES = frozenset({
    "queued", "claimed", "in_progress", "completed",
    "failed", "deferred_by_capacity", "blocked",
})
VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low"})
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
VALID_FAILURE_CLASSES = frozenset({
    "rate_limited", "schema_invalid", "policy_denied",
    "agent_unavailable", "timeout", "execution_failed", "claim_conflict",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class TaskLedger:
    """Persistent task tracking with claim/lock semantics."""

    def __init__(self, ledger_path: Optional[str] = None):
        self._path = Path(ledger_path) if ledger_path else Path("data/task_ledger.jsonl")
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Replay JSONL log to rebuild in-memory index."""
        if not self._path.exists():
            return
        with open(self._path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    tid = entry.get("task_id")
                    if tid:
                        self._tasks[tid] = entry
                except (json.JSONDecodeError, KeyError):
                    continue

    def _append(self, task: Dict[str, Any]) -> None:
        """Append a task record to the JSONL file."""
        with open(self._path, "a") as f:
            f.write(json.dumps(task, default=str) + "\n")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_task(
        self,
        title: str,
        description: str = "",
        task_type: str = "implementation",
        priority: str = "medium",
        parent_task_id: Optional[str] = None,
        assigned_agent: Optional[str] = None,
        context_pack_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Create a new task and return its task_id."""
        task_id = str(uuid.uuid4())
        now = _now_iso()
        task: Dict[str, Any] = {
            "task_id": task_id,
            "parent_task_id": parent_task_id,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "description": description,
            "task_type": task_type if task_type in VALID_TASK_TYPES else "implementation",
            "status": "queued",
            "priority": priority if priority in VALID_PRIORITIES else "medium",
            "assigned_agent": assigned_agent,
            "claimed_at": None,
            "claimed_by": None,
            "result": None,
            "error": None,
            "failure_class": None,
            "retry_count": 0,
            "max_retries": 3,
            "context_pack_path": context_pack_path,
            "subtask_ids": [],
            "tags": tags or [],
        }
        with self._lock:
            self._tasks[task_id] = task
            self._append(task)
        return task_id

    def claim_task(self, task_id: str, agent_id: str) -> bool:
        """
        Atomically claim a task. Returns True on success.
        Fails if already claimed by a different agent or not in a claimable state.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task["status"] not in ("queued", "failed"):
                return False
            if task["claimed_by"] is not None and task["claimed_by"] != agent_id:
                return False
            now = _now_iso()
            task["status"] = "claimed"
            task["claimed_at"] = now
            task["claimed_by"] = agent_id
            task["assigned_agent"] = agent_id
            task["updated_at"] = now
            self._append(task)
            return True

    def release_task(self, task_id: str, agent_id: str) -> bool:
        """Release a claim, returning the task to queued."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task["claimed_by"] != agent_id:
                return False
            now = _now_iso()
            task["status"] = "queued"
            task["claimed_at"] = None
            task["claimed_by"] = None
            task["assigned_agent"] = None
            task["updated_at"] = now
            self._append(task)
            return True

    def update_status(
        self,
        task_id: str,
        status: str,
        error: Optional[Dict[str, Any]] = None,
        failure_class: Optional[str] = None,
    ) -> bool:
        """Transition a task to a new status."""
        if status not in VALID_STATUSES:
            return False
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            now = _now_iso()
            task["status"] = status
            task["updated_at"] = now
            if error is not None:
                task["error"] = error
            if failure_class is not None and failure_class in VALID_FAILURE_CLASSES:
                task["failure_class"] = failure_class
            self._append(task)
            return True

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """Mark a task as completed with an optional result payload."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            now = _now_iso()
            task["status"] = "completed"
            task["result"] = result
            task["updated_at"] = now
            self._append(task)

            # Check if completing this task unblocks siblings
            if task.get("parent_task_id"):
                self._check_unblock_siblings(task["parent_task_id"])

            return True

    def _check_unblock_siblings(self, parent_task_id: str) -> None:
        """Unblock sibling subtasks whose predecessors are now complete."""
        siblings = [t for t in self._tasks.values() if t.get("parent_task_id") == parent_task_id]
        for sibling in siblings:
            if sibling.get("status") == "blocked":
                order = sibling.get("order", 0)
                predecessors = [s for s in siblings if s.get("order", 0) < order]
                all_done = all(s.get("status") == "completed" for s in predecessors)
                if all_done:
                    sibling["status"] = "queued"
                    sibling["updated_at"] = _now_iso()
                    self._append(sibling)

    def fail_task(
        self,
        task_id: str,
        error: Any = None,
        failure_class: Optional[str] = None,
    ) -> bool:
        """Mark a task as failed with error info and failure classification."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            now = _now_iso()
            task["status"] = "failed"
            task["error"] = error
            if failure_class and failure_class in VALID_FAILURE_CLASSES:
                task["failure_class"] = failure_class
            task["retry_count"] = task.get("retry_count", 0) + 1
            task["updated_at"] = now
            self._append(task)
            return True

    def defer_task(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as deferred_by_capacity."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            now = _now_iso()
            task["status"] = "deferred_by_capacity"
            task["error"] = {"reason": reason}
            task["updated_at"] = now
            self._append(task)
            return True

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def list_tasks(
        self,
        status: Optional[str] = None,
        agent: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query tasks with optional filters."""
        with self._lock:
            results = []
            for task in self._tasks.values():
                if status and task["status"] != status:
                    continue
                if agent and task.get("assigned_agent") != agent:
                    continue
                if task_type and task["task_type"] != task_type:
                    continue
                results.append(dict(task))
        results.sort(key=lambda t: t.get("created_at", ""))
        return results

    def get_queue(self) -> List[Dict[str, Any]]:
        """Return unclaimed tasks ordered by priority (critical first)."""
        with self._lock:
            unclaimed = [
                dict(t) for t in self._tasks.values()
                if t["status"] == "queued" and t["claimed_by"] is None
            ]
        unclaimed.sort(key=lambda t: (
            PRIORITY_ORDER.get(t.get("priority", "low"), 99),
            t.get("created_at", ""),
        ))
        return unclaimed

    def decompose_task(
        self,
        parent_task_id: str,
        subtasks: List[Dict[str, Any]],
    ) -> List[str]:
        """Create subtasks linked to a parent task. Returns list of new task_ids.

        Subtasks with order > 0 start as "blocked"; order 0 starts as "queued".
        """
        with self._lock:
            parent = self._tasks.get(parent_task_id)
            if parent is None:
                return []
            new_ids = []
            for sub in subtasks:
                order = sub.get("order", 0)
                tid = self.create_task(
                    title=sub.get("title", "Subtask"),
                    description=sub.get("description", ""),
                    task_type=sub.get("task_type", parent["task_type"]),
                    priority=sub.get("priority", parent["priority"]),
                    parent_task_id=parent_task_id,
                    tags=sub.get("tags", []),
                )
                # Store the order on the task
                task = self._tasks[tid]
                task["order"] = order
                # Block subtasks that depend on predecessors
                if order > 0:
                    task["status"] = "blocked"
                task["updated_at"] = _now_iso()
                self._append(task)
                new_ids.append(tid)
            parent["subtask_ids"] = parent.get("subtask_ids", []) + new_ids
            parent["updated_at"] = _now_iso()
            self._append(parent)
            return new_ids

    def expire_stale_on_startup(self, max_age_seconds: float = 3600.0) -> int:
        """Expire queued/claimed tasks older than max_age_seconds.

        Called at broker startup to clear stale tasks from previous sessions.
        Returns the number of tasks expired.
        """
        from datetime import datetime, timezone
        import time as _time

        now = _time.time()
        expired = 0
        with self._lock:
            for task in list(self._tasks.values()):
                if task["status"] not in ("queued", "claimed", "in_progress"):
                    continue
                created = task.get("created_at", "")
                if not created:
                    continue
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age = now - dt.timestamp()
                except (ValueError, TypeError):
                    continue
                if age > max_age_seconds:
                    task["status"] = "failed"
                    task["error"] = {"reason": "Expired on startup — stale from previous session"}
                    task["failure_class"] = "timeout"
                    task["updated_at"] = _now_iso()
                    self._append(task)
                    expired += 1
        return expired

    def get_failure_stats(self) -> Dict[str, int]:
        """Return counts of each failure_class across all tasks."""
        stats: Dict[str, int] = {}
        with self._lock:
            for task in self._tasks.values():
                fc = task.get("failure_class")
                if fc:
                    stats[fc] = stats.get(fc, 0) + 1
        return stats

    def get_status_counts(self) -> Dict[str, int]:
        """Return counts of each status across all tasks."""
        counts: Dict[str, int] = {}
        with self._lock:
            for task in self._tasks.values():
                s = task.get("status", "unknown")
                counts[s] = counts.get(s, 0) + 1
        return counts
