"""
ProjectX Subsystem Registry — Phase 2

Provides a registry of specialized sub-agents that can be spawned
on-demand to handle specific task categories. Each subsystem has:
  - A role description used for routing
  - A system prompt injected at call time
  - Rate limits and resource quotas

Subsystem types (mirroring the roadmap specialisations):
  code_gen     — code generation and review
  research     — web research and summarisation
  analysis     — data analysis and reasoning
  creative     — ideation and creative tasks
  planning     — decomposition and scheduling

The registry is intentionally thin — it does NOT spawn OS processes.
Instead it wraps the InternetClient + APO + RAGMemory into focused
task handlers that any caller can invoke synchronously.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubsystemConfig:
    name: str
    role: str
    system_prompt: str
    max_calls_per_minute: int = 10
    memory_enabled: bool = True
    web_enabled: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class SubsystemResult:
    subsystem: str
    task: str
    output: str
    latency_ms: int
    sources: List[str] = field(default_factory=list)
    memory_hits: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


# ── Built-in subsystem definitions ────────────────────────────────────────────

_BUILTIN_CONFIGS: Dict[str, SubsystemConfig] = {
    "code_gen": SubsystemConfig(
        name="code_gen",
        role="Expert software engineer specialising in Python, async patterns, and system design.",
        system_prompt=(
            "You are a senior software engineer. When asked to write or review code:\n"
            "1. Write clean, well-typed Python unless another language is specified.\n"
            "2. Include only necessary comments.\n"
            "3. Prefer stdlib over third-party libraries where practical.\n"
            "4. Always handle exceptions and log errors."
        ),
        max_calls_per_minute=20,
        memory_enabled=True,
        web_enabled=False,
        tags=["code", "python", "review", "debug"],
    ),
    "research": SubsystemConfig(
        name="research",
        role="Research analyst capable of web search, summarisation, and fact extraction.",
        system_prompt=(
            "You are a research analyst. When given a topic:\n"
            "1. Identify the key questions to answer.\n"
            "2. Search for and synthesise relevant sources.\n"
            "3. Cite sources explicitly.\n"
            "4. Flag uncertainty and conflicting information."
        ),
        max_calls_per_minute=5,
        memory_enabled=True,
        web_enabled=True,
        tags=["research", "web", "summarise", "facts"],
    ),
    "analysis": SubsystemConfig(
        name="analysis",
        role="Data analyst with expertise in statistics, metrics, and structured reasoning.",
        system_prompt=(
            "You are a data analyst. When given data or a question:\n"
            "1. Identify the key metrics and relationships.\n"
            "2. Reason step-by-step.\n"
            "3. Quantify uncertainty where possible.\n"
            "4. Present conclusions clearly with supporting evidence."
        ),
        max_calls_per_minute=15,
        memory_enabled=True,
        web_enabled=False,
        tags=["data", "metrics", "statistics", "reasoning"],
    ),
    "creative": SubsystemConfig(
        name="creative",
        role="Creative thinker for ideation, brainstorming, and novel solution generation.",
        system_prompt=(
            "You are a creative strategist. When given a challenge:\n"
            "1. Generate multiple divergent ideas before converging.\n"
            "2. Challenge assumptions.\n"
            "3. Think in analogies and cross-domain patterns.\n"
            "4. Rank ideas by feasibility and impact."
        ),
        max_calls_per_minute=10,
        memory_enabled=False,
        web_enabled=False,
        tags=["ideas", "brainstorm", "creative", "strategy"],
    ),
    "planning": SubsystemConfig(
        name="planning",
        role="Task planner that decomposes goals into executable steps.",
        system_prompt=(
            "You are a project planner. When given a goal:\n"
            "1. Break it into concrete, ordered steps.\n"
            "2. Identify dependencies and risks.\n"
            "3. Estimate effort and flag blockers.\n"
            "4. Output a structured plan with acceptance criteria."
        ),
        max_calls_per_minute=10,
        memory_enabled=True,
        web_enabled=False,
        tags=["plan", "decompose", "schedule", "tasks"],
    ),
}


class _RateLimiter:
    def __init__(self, rpm: int) -> None:
        self._rpm = rpm
        self._calls: List[float] = []

    def check(self) -> bool:
        now = time.time()
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= self._rpm:
            return False
        self._calls.append(now)
        return True

    @property
    def remaining(self) -> int:
        now = time.time()
        active = [t for t in self._calls if now - t < 60]
        return max(0, self._rpm - len(active))


class SubsystemHandle:
    """
    A handle to a registered subsystem.

    Callers inject an ``executor`` callable::

        def executor(system_prompt: str, user_message: str) -> str:
            # call your LLM here
            ...

    Then invoke the subsystem::

        result = handle.run("Explain asyncio event loops", executor=my_executor)
    """

    def __init__(self, config: SubsystemConfig) -> None:
        self._config = config
        self._limiter = _RateLimiter(config.max_calls_per_minute)
        self._call_count = 0

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def config(self) -> SubsystemConfig:
        return self._config

    @property
    def remaining_calls(self) -> int:
        return self._limiter.remaining

    def run(
        self,
        task: str,
        executor: Callable[[str, str], str],
        context: Optional[str] = None,
        memory=None,
        web_client=None,
    ) -> SubsystemResult:
        """
        Execute a task through this subsystem.

        Args:
            task:      The user-facing task description.
            executor:  Callable(system_prompt, user_message) → response string.
            context:   Optional extra context prepended to the task.
            memory:    Optional RAGMemory instance for retrieval.
            web_client: Optional InternetClient for web research.

        Returns:
            SubsystemResult
        """
        t0 = time.time()

        if not self._limiter.check():
            return SubsystemResult(
                subsystem=self._config.name,
                task=task,
                output="",
                latency_ms=0,
                error=f"Rate limit exceeded ({self._config.max_calls_per_minute} rpm)",
            )

        sources: List[str] = []
        memory_hits = 0
        user_message = task

        # Augment with memory hits
        if memory and self._config.memory_enabled:
            try:
                hits = memory.query(task, top_k=3)
                if hits:
                    memory_hits = len(hits)
                    snippets = "\n".join(
                        f"[Memory] {r.entry.content[:300]}" for r in hits
                    )
                    user_message = f"Relevant context:\n{snippets}\n\nTask: {task}"
            except Exception as exc:
                logger.debug("%s memory retrieval failed: %s", self._config.name, exc)

        # Augment with web search for research subsystem
        if web_client and self._config.web_enabled:
            try:
                resp = web_client.fetch(f"https://en.wikipedia.org/w/api.php?action=opensearch&search={task[:60]}&limit=2&format=json")
                if resp.ok:
                    data = resp.json()
                    if len(data) > 3 and data[3]:
                        sources = data[3][:2]
                        summaries = data[2][:2] if len(data) > 2 else []
                        if summaries:
                            web_ctx = "\n".join(f"- {s}" for s in summaries)
                            user_message += f"\n\nWeb context:\n{web_ctx}"
            except Exception as exc:
                logger.debug("%s web augmentation failed: %s", self._config.name, exc)

        if context:
            user_message = f"{context}\n\n{user_message}"

        try:
            output = executor(self._config.system_prompt, user_message)
            error = None
        except Exception as exc:
            output = ""
            error = str(exc)
            logger.warning("%s executor failed: %s", self._config.name, exc)

        self._call_count += 1
        latency = int((time.time() - t0) * 1000)
        return SubsystemResult(
            subsystem=self._config.name,
            task=task,
            output=output,
            latency_ms=latency,
            sources=sources,
            memory_hits=memory_hits,
            error=error,
        )

    def status(self) -> Dict[str, Any]:
        return {
            "name": self._config.name,
            "role": self._config.role,
            "call_count": self._call_count,
            "remaining_rpm": self.remaining_calls,
            "tags": self._config.tags,
        }


class SubsystemRegistry:
    """
    Central registry for ProjectX specialized subsystems.

    Usage::

        registry = SubsystemRegistry()
        result = registry.route("Write a Python function to parse JSON", executor=my_llm)
    """

    def __init__(self) -> None:
        self._subsystems: Dict[str, SubsystemHandle] = {
            name: SubsystemHandle(cfg)
            for name, cfg in _BUILTIN_CONFIGS.items()
        }

    def get(self, name: str) -> Optional[SubsystemHandle]:
        return self._subsystems.get(name)

    def register(self, config: SubsystemConfig) -> SubsystemHandle:
        """Register a custom subsystem."""
        handle = SubsystemHandle(config)
        self._subsystems[config.name] = handle
        logger.info("Registered subsystem: %s", config.name)
        return handle

    def route(
        self,
        task: str,
        executor: Callable[[str, str], str],
        preferred: Optional[str] = None,
        **kwargs,
    ) -> SubsystemResult:
        """
        Route a task to the best-matching subsystem.

        Args:
            task:      The task string.
            executor:  LLM executor callable.
            preferred: Force a specific subsystem name.
            **kwargs:  Passed through to SubsystemHandle.run().

        Returns:
            SubsystemResult from the selected subsystem.
        """
        if preferred and preferred in self._subsystems:
            return self._subsystems[preferred].run(task, executor, **kwargs)

        subsystem = self._select(task)
        logger.debug("Routing task to subsystem '%s'", subsystem.name)
        return subsystem.run(task, executor, **kwargs)

    def _select(self, task: str) -> SubsystemHandle:
        """Keyword-based routing (fast, no LLM call needed)."""
        task_lower = task.lower()
        scores: Dict[str, int] = {}
        for name, handle in self._subsystems.items():
            score = sum(1 for tag in handle.config.tags if tag in task_lower)
            scores[name] = score
        best_name = max(scores, key=lambda n: scores[n])
        return self._subsystems[best_name]

    def all_status(self) -> List[Dict[str, Any]]:
        return [h.status() for h in self._subsystems.values()]


# Module-level singleton
_registry: Optional[SubsystemRegistry] = None


def get_subsystem_registry() -> SubsystemRegistry:
    global _registry
    if _registry is None:
        _registry = SubsystemRegistry()
    return _registry
