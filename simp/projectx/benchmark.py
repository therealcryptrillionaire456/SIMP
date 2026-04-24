"""
ProjectX Benchmark Suite — Step 1

Standardized task battery that gives APO a real, reproducible scorer.
Without fixed golden-answer tasks, APO optimization has no stable signal —
every re-run evaluates different inputs, hiding real improvement.

Suite structure:
  BenchmarkTask — one task with expected answer and a scoring rubric
  BenchmarkSuite — ordered collection of tasks
  BenchmarkRunner — runs a suite against an executor, returns BenchmarkReport
  ScoringRubric — pluggable scoring (exact, contains, regex, semantic, fn)

Built-in tasks cover the five roadmap capability domains:
  reasoning, code_gen, research, planning, analysis

Usage::

    runner = BenchmarkRunner()
    report = runner.run(executor=my_llm)
    print(report.overall_score, report.passed_count)
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ScoringMethod(str, Enum):
    EXACT       = "exact"        # case-insensitive full match
    CONTAINS    = "contains"     # answer contains all expected strings
    REGEX       = "regex"        # answer matches regex pattern
    NUMERIC     = "numeric"      # answer contains expected number ±tolerance
    FN          = "fn"           # custom callable scorer
    SEMANTIC    = "semantic"     # keyword overlap (no LLM dependency)


@dataclass
class BenchmarkTask:
    task_id:        str
    domain:         str               # reasoning|code_gen|research|planning|analysis
    prompt:         str               # the user-facing question
    expected:       Any               # expected answer (str, list, number, regex, callable)
    scoring:        ScoringMethod     = ScoringMethod.CONTAINS
    max_score:      float             = 1.0
    weight:         float             = 1.0
    timeout:        int               = 30
    tags:           List[str]         = field(default_factory=list)
    metadata:       Dict[str, Any]    = field(default_factory=dict)

    def score(self, response: str) -> Tuple[float, str]:
        """
        Score a response. Returns (score_0_to_max, reason_string).
        """
        try:
            return self._score(response)
        except Exception as exc:
            return 0.0, f"Scoring error: {exc}"

    def _score(self, response: str) -> Tuple[float, str]:
        r = response.strip().lower()

        if self.scoring == ScoringMethod.EXACT:
            expected = str(self.expected).strip().lower()
            ok = r == expected
            return (self.max_score if ok else 0.0), ("exact match" if ok else "no match")

        if self.scoring == ScoringMethod.CONTAINS:
            items = self.expected if isinstance(self.expected, list) else [self.expected]
            found = [str(x).lower() in r for x in items]
            ratio = sum(found) / len(found)
            score = self.max_score * ratio
            return score, f"{sum(found)}/{len(found)} required terms found"

        if self.scoring == ScoringMethod.REGEX:
            match = bool(re.search(str(self.expected), response, re.IGNORECASE | re.DOTALL))
            return (self.max_score if match else 0.0), ("regex matched" if match else "no regex match")

        if self.scoring == ScoringMethod.NUMERIC:
            nums = re.findall(r"-?\d+\.?\d*", response)
            target = float(self.expected)
            tol = abs(target) * 0.05 + 0.01
            for n in nums:
                if abs(float(n) - target) <= tol:
                    return self.max_score, f"numeric match {n} ≈ {target}"
            return 0.0, f"no numeric match for {target} in response"

        if self.scoring == ScoringMethod.FN:
            sc = float(self.expected(response))
            return min(self.max_score, max(0.0, sc)), "custom fn"

        if self.scoring == ScoringMethod.SEMANTIC:
            keywords = self.expected if isinstance(self.expected, list) else str(self.expected).split()
            resp_words = set(re.findall(r"\b\w+\b", r))
            hits = sum(1 for k in keywords if k.lower() in resp_words)
            ratio = hits / (len(keywords) or 1)
            return self.max_score * min(1.0, ratio * 1.5), f"{hits}/{len(keywords)} keywords"

        return 0.0, f"unknown scoring method: {self.scoring}"


@dataclass
class TaskResult:
    task_id:    str
    domain:     str
    prompt:     str
    response:   str
    score:      float
    max_score:  float
    reason:     str
    latency_ms: int
    error:      Optional[str] = None

    @property
    def normalized(self) -> float:
        return self.score / (self.max_score or 1.0)

    @property
    def passed(self) -> bool:
        return self.normalized >= 0.5


@dataclass
class BenchmarkReport:
    run_id:       str
    timestamp:    float
    executor_id:  str
    results:      List[TaskResult]
    total_ms:     int

    @property
    def overall_score(self) -> float:
        if not self.results:
            return 0.0
        total_w = sum(r.max_score for r in self.results)
        if total_w == 0:
            return 0.0
        return sum(r.score for r in self.results) / total_w

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / (len(self.results) or 1)

    def by_domain(self) -> Dict[str, Dict[str, float]]:
        domains: Dict[str, List[TaskResult]] = {}
        for r in self.results:
            domains.setdefault(r.domain, []).append(r)
        return {
            d: {
                "score": sum(t.normalized for t in tasks) / len(tasks),
                "pass_rate": sum(1 for t in tasks if t.passed) / len(tasks),
                "count": len(tasks),
            }
            for d, tasks in domains.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "executor_id": self.executor_id,
            "overall_score": round(self.overall_score, 4),
            "pass_rate": round(self.pass_rate, 4),
            "passed": self.passed_count,
            "total": len(self.results),
            "total_ms": self.total_ms,
            "by_domain": self.by_domain(),
        }

    def save(self, path: str) -> None:
        from simp.projectx.hardening import AtomicWriter
        AtomicWriter.append_line(path, json.dumps(self.to_dict(), default=str))


@dataclass
class BenchmarkHistorySummary:
    history_path: str
    run_count: int
    latest_score: float
    best_score: float
    trend_ratio: Optional[float]
    latest_executor_id: str = ""
    recent_runs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "history_path": self.history_path,
            "run_count": self.run_count,
            "latest_score": round(self.latest_score, 4),
            "best_score": round(self.best_score, 4),
            "trend_ratio": round(self.trend_ratio, 4) if self.trend_ratio is not None else None,
            "latest_executor_id": self.latest_executor_id,
            "recent_runs": self.recent_runs,
        }


# ── Built-in task battery ──────────────────────────────────────────────────────

_BUILTIN_TASKS: List[BenchmarkTask] = [
    # ── Reasoning ─────────────────────────────────────────────────────────
    BenchmarkTask(
        task_id="r001", domain="reasoning",
        prompt="What is 17 multiplied by 23?",
        expected=391, scoring=ScoringMethod.NUMERIC,
        tags=["arithmetic"],
    ),
    BenchmarkTask(
        task_id="r002", domain="reasoning",
        prompt="If all A are B, and all B are C, are all A also C?",
        expected=["yes", "correct", "true"],
        scoring=ScoringMethod.CONTAINS, tags=["logic"],
    ),
    BenchmarkTask(
        task_id="r003", domain="reasoning",
        prompt="A train travels 120 km in 1.5 hours. What is its average speed in km/h?",
        expected=80, scoring=ScoringMethod.NUMERIC, tags=["word_problem"],
    ),
    BenchmarkTask(
        task_id="r004", domain="reasoning",
        prompt="What comes next in this sequence: 2, 4, 8, 16, __?",
        expected=32, scoring=ScoringMethod.NUMERIC, tags=["pattern"],
    ),

    # ── Code Generation ────────────────────────────────────────────────────
    BenchmarkTask(
        task_id="c001", domain="code_gen",
        prompt="Write a Python function that returns the factorial of n using recursion.",
        expected=["def ", "factorial", "return", "n *"],
        scoring=ScoringMethod.CONTAINS, tags=["python", "recursion"],
    ),
    BenchmarkTask(
        task_id="c002", domain="code_gen",
        prompt="Write a Python one-liner that reverses a list named 'lst'.",
        expected=[r"lst\[::-1\]|reversed\(lst\)|lst\.reverse"],
        scoring=ScoringMethod.REGEX, tags=["python", "oneliner"],
    ),
    BenchmarkTask(
        task_id="c003", domain="code_gen",
        prompt="Write a Python function to check if a string is a palindrome.",
        expected=["def ", "return", "=="],
        scoring=ScoringMethod.CONTAINS, tags=["python", "string"],
    ),
    BenchmarkTask(
        task_id="c004", domain="code_gen",
        prompt="Write a Python context manager that times a block of code.",
        expected=["__enter__", "__exit__", "time"],
        scoring=ScoringMethod.CONTAINS, tags=["python", "context_manager"],
    ),

    # ── Research / Knowledge ───────────────────────────────────────────────
    BenchmarkTask(
        task_id="k001", domain="research",
        prompt="What does CPU stand for?",
        expected=["central", "processing", "unit"],
        scoring=ScoringMethod.CONTAINS, tags=["computing"],
    ),
    BenchmarkTask(
        task_id="k002", domain="research",
        prompt="What is the time complexity of binary search?",
        expected=["log", "o(log"],
        scoring=ScoringMethod.CONTAINS, tags=["algorithms"],
    ),
    BenchmarkTask(
        task_id="k003", domain="research",
        prompt="Name three major Python web frameworks.",
        expected=["django", "flask", "fastapi"],
        scoring=ScoringMethod.CONTAINS, tags=["python", "web"],
    ),

    # ── Planning ───────────────────────────────────────────────────────────
    BenchmarkTask(
        task_id="p001", domain="planning",
        prompt="List the steps to deploy a Python web application to production.",
        expected=["test", "docker", "deploy"],
        scoring=ScoringMethod.SEMANTIC, tags=["devops"],
    ),
    BenchmarkTask(
        task_id="p002", domain="planning",
        prompt="What are the phases of the software development lifecycle?",
        expected=["requirements", "design", "implementation", "testing"],
        scoring=ScoringMethod.SEMANTIC, tags=["sdlc"],
    ),

    # ── Analysis ───────────────────────────────────────────────────────────
    BenchmarkTask(
        task_id="a001", domain="analysis",
        prompt="A dataset has mean=50, median=45. What does this suggest about the distribution?",
        expected=["skew", "right", "positive"],
        scoring=ScoringMethod.SEMANTIC, tags=["statistics"],
    ),
    BenchmarkTask(
        task_id="a002", domain="analysis",
        prompt="If a model has 99% accuracy on imbalanced data (1% positive class), is it good?",
        expected=["no", "not", "imbalance", "precision", "recall", "mislead"],
        scoring=ScoringMethod.SEMANTIC, tags=["ml", "imbalanced"],
    ),
]


class BenchmarkSuite:
    """An ordered, filterable collection of BenchmarkTasks."""

    def __init__(self, tasks: Optional[List[BenchmarkTask]] = None) -> None:
        self._tasks: List[BenchmarkTask] = tasks or list(_BUILTIN_TASKS)

    def add(self, task: BenchmarkTask) -> None:
        self._tasks.append(task)

    def filter_domain(self, domain: str) -> "BenchmarkSuite":
        return BenchmarkSuite([t for t in self._tasks if t.domain == domain])

    def filter_tags(self, *tags: str) -> "BenchmarkSuite":
        tag_set = set(tags)
        return BenchmarkSuite([t for t in self._tasks if tag_set.intersection(t.tags)])

    def __len__(self) -> int:
        return len(self._tasks)

    def __iter__(self):
        return iter(self._tasks)


class BenchmarkRunner:
    """
    Runs a BenchmarkSuite against an executor function.

    Usage::

        runner = BenchmarkRunner(history_path="projectx_logs/benchmark_history.jsonl")
        report = runner.run(executor=my_llm)
        print(f"Score: {report.overall_score:.1%}")
    """

    def __init__(
        self,
        suite: Optional[BenchmarkSuite] = None,
        history_path: str = "projectx_logs/benchmark_history.jsonl",
        executor_id: str = "default",
    ) -> None:
        self._suite = suite or BenchmarkSuite()
        self._history_path = history_path
        self._executor_id = executor_id

    def run(
        self,
        executor: Callable[[str, str], str],
        executor_id: Optional[str] = None,
        domains: Optional[List[str]] = None,
    ) -> BenchmarkReport:
        """
        Run the full suite and return a BenchmarkReport.

        Args:
            executor: Callable(system_prompt, user_message) → response string.
            executor_id: Label for this executor (stored in history).
            domains: Optionally restrict to specific domains.
        """
        run_id = uuid.uuid4().hex[:8]
        exec_id = executor_id or self._executor_id
        tasks = list(self._suite)
        if domains:
            tasks = [t for t in tasks if t.domain in domains]

        results: List[TaskResult] = []
        t0_total = time.time()

        for task in tasks:
            t0 = time.time()
            error = None
            response = ""
            try:
                system_prompt = (
                    f"You are a {task.domain} expert. Answer concisely and precisely."
                )
                response = executor(system_prompt, task.prompt)
            except Exception as exc:
                error = str(exc)
                logger.warning("Benchmark task %s executor failed: %s", task.task_id, exc)

            score, reason = task.score(response) if not error else (0.0, f"executor error: {error}")
            latency = int((time.time() - t0) * 1000)

            results.append(TaskResult(
                task_id=task.task_id,
                domain=task.domain,
                prompt=task.prompt,
                response=response[:500],
                score=score,
                max_score=task.max_score,
                reason=reason,
                latency_ms=latency,
                error=error,
            ))

        report = BenchmarkReport(
            run_id=run_id,
            timestamp=time.time(),
            executor_id=exec_id,
            results=results,
            total_ms=int((time.time() - t0_total) * 1000),
        )

        report.save(self._history_path)
        logger.info(
            "Benchmark %s: score=%.1f%% pass=%d/%d in %dms",
            run_id, report.overall_score * 100, report.passed_count, len(results), report.total_ms,
        )
        return report

    def improvement_trend(self, last_n: int = 10) -> Optional[float]:
        """
        Return the score improvement ratio over the last N runs.
        Returns None if insufficient history.
        """
        path = Path(self._history_path)
        if not path.exists():
            return None
        try:
            lines = [l for l in path.read_text().splitlines() if l.strip()][-last_n:]
            if len(lines) < 2:
                return None
            scores = [json.loads(l).get("overall_score", 0) for l in lines]
            if scores[0] <= 0:
                return None
            return round(scores[-1] / scores[0], 4)
        except Exception:
            return None

    def recent_runs(self, limit: int = 5) -> List[Dict[str, Any]]:
        path = Path(self._history_path)
        if not path.exists():
            return []
        try:
            lines = [l for l in path.read_text().splitlines() if l.strip()][-max(1, min(limit, 50)):]
            return [json.loads(line) for line in lines]
        except Exception:
            return []

    def history_summary(self, limit: int = 5) -> BenchmarkHistorySummary:
        recent = self.recent_runs(limit=limit)
        scores = [float(run.get("overall_score", 0.0)) for run in recent]
        latest = recent[-1] if recent else {}
        return BenchmarkHistorySummary(
            history_path=self._history_path,
            run_count=len(recent),
            latest_score=scores[-1] if scores else 0.0,
            best_score=max(scores) if scores else 0.0,
            trend_ratio=self.improvement_trend(last_n=max(limit, 2)),
            latest_executor_id=str(latest.get("executor_id") or ""),
            recent_runs=recent,
        )


def make_apo_scorer(runner: BenchmarkRunner) -> Callable[[str], float]:
    """
    Return a closure that runs the benchmark suite for APO optimization.
    The prompt template is rendered as the system prompt prefix.
    """
    def _score(prompt_template: str) -> float:
        def _executor(sys: str, user: str) -> str:
            return f"[stub: {user[:80]}]"
        report = runner.run(_executor)
        return report.overall_score
    return _score
