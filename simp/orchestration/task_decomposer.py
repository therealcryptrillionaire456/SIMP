"""
SIMP Task Decomposer

Breaks high-level goals into ordered lists of agent-routable subtasks
using goal-type templates.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class TaskDecomposer:
    """Decomposes high-level goals into agent-routable subtasks."""

    TEMPLATES: Dict[str, List[str]] = {
        "build": ["spec", "architecture", "scaffold", "implementation", "test", "docs"],
        "research": ["research", "analysis", "docs"],
        "fix": ["analysis", "implementation", "test"],
        "optimize": ["analysis", "architecture", "implementation", "test"],
        "document": ["research", "docs"],
    }

    # Human-readable descriptions per task type
    _TASK_DESCRIPTIONS: Dict[str, str] = {
        "spec": "Define requirements and acceptance criteria",
        "architecture": "Design the architecture and component layout",
        "scaffold": "Create project scaffolding and boilerplate",
        "implementation": "Implement the core functionality",
        "test": "Write and run tests to validate the implementation",
        "docs": "Write documentation and usage guides",
        "research": "Research existing solutions and best practices",
        "analysis": "Analyze the current state and identify changes needed",
    }

    def decompose(
        self,
        goal: str,
        goal_type: str = "build",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Decompose a high-level goal into ordered subtasks.

        Args:
            goal: Human-readable goal description.
            goal_type: One of the template keys (build, research, fix, optimize, document).
            constraints: Optional constraints passed through to each subtask.

        Returns:
            Ordered list of subtask dicts ready for the task ledger.
        """
        template = self.TEMPLATES.get(goal_type, self.TEMPLATES["build"])
        goal_id = str(uuid.uuid4())[:8]
        subtasks: List[Dict[str, Any]] = []

        for order, task_type in enumerate(template):
            subtask = {
                "subtask_id": f"{goal_id}-{order:02d}",
                "goal_id": goal_id,
                "task_type": task_type,
                "title": f"[{goal_type.upper()}] {task_type}: {goal}",
                "description": self._TASK_DESCRIPTIONS.get(task_type, task_type),
                "order": order,
                "status": "queued",
                "constraints": constraints or {},
                "created_at": datetime.utcnow().isoformat(),
            }
            subtasks.append(subtask)

        return subtasks

    @classmethod
    def available_goal_types(cls) -> List[str]:
        """Return the list of supported goal types."""
        return list(cls.TEMPLATES.keys())

    @classmethod
    def infer_goal_type(cls, goal: str) -> str:
        """Infer the goal type from the goal text using keyword matching."""
        lower = goal.lower()
        if any(kw in lower for kw in ("build", "create", "add", "implement", "make")):
            return "build"
        if any(kw in lower for kw in ("research", "investigate", "explore", "find")):
            return "research"
        if any(kw in lower for kw in ("fix", "bug", "repair", "patch", "resolve")):
            return "fix"
        if any(kw in lower for kw in ("optimize", "improve", "speed", "perf", "faster")):
            return "optimize"
        if any(kw in lower for kw in ("document", "docs", "write up", "readme")):
            return "document"
        return "build"
