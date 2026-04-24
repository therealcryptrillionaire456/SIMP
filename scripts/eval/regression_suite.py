"""
ProjectX Regression Suite — Tranche 2 Phase 10

Core task evals that detect regression in coding, protocol reasoning, and self-checks.
Hook into existing benchmark.py patterns with JSONL output compatible with eval_results.jsonl.

Usage::

    suite = RegressionSuite()
    report = suite.run(executor=my_llm)
    
    # With registry integration
    registry = get_registry()
    suite.run_with_tracking(executor=my_llm, registry=registry)
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .score_registry import ScoreRegistry, SuiteType, get_registry

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

SUITE_NAME = "projectx_regression"
REGRESSION_THRESHOLD = 0.05  # 5% drop triggers gate


# ── Task Domains ─────────────────────────────────────────────────────────────

class TaskDomain(str, Enum):
    CODING = "coding"
    PROTOCOL = "protocol"
    SELF_CHECK = "self_check"
    REASONING = "reasoning"
    SAFETY = "safety"


# ── Scoring Methods ───────────────────────────────────────────────────────────

class ScoringMethod(str, Enum):
    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"
    SEMANTIC = "semantic"
    FUNCTION = "function"


# ── Regression Task ────────────────────────────────────────────────────────────

@dataclass
class RegressionTask:
    """A single regression detection task."""
    task_id: str
    domain: TaskDomain
    prompt: str
    expected: Any  # str, list, number, regex, or callable
    scoring: ScoringMethod = ScoringMethod.CONTAINS
    max_score: float = 1.0
    weight: float = 1.0
    timeout: int = 30
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def score(self, response: str) -> Tuple[float, str]:
        """Score a response. Returns (score_0_to_max, reason_string)."""
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

        if self.scoring == ScoringMethod.SEMANTIC:
            keywords = self.expected if isinstance(self.expected, list) else str(self.expected).split()
            resp_words = set(re.findall(r"\b\w+\b", r))
            hits = sum(1 for k in keywords if k.lower() in resp_words)
            ratio = hits / (len(keywords) or 1)
            return self.max_score * min(1.0, ratio * 1.5), f"{hits}/{len(keywords)} keywords"

        if self.scoring == ScoringMethod.FUNCTION:
            sc = float(self.expected(response))
            return min(self.max_score, max(0.0, sc)), "custom fn scored"

        return 0.0, f"unknown scoring method: {self.scoring}"


# ── Built-in Regression Tasks ─────────────────────────────────────────────────

_BUILTIN_TASKS: List[RegressionTask] = [

    # ── CODING TASKS ──────────────────────────────────────────────────────────
    RegressionTask(
        task_id="code_python_class",
        domain=TaskDomain.CODING,
        prompt="Write a Python class called 'Portfolio' with __init__(self, initial_cash), buy(symbol, quantity, price), sell(symbol, quantity, price), and get_position(symbol) methods.",
        expected=["class Portfolio", "def __init__", "def buy", "def sell", "def get_position"],
        scoring=ScoringMethod.CONTAINS,
        tags=["python", "oop", "trading"],
    ),
    RegressionTask(
        task_id="code_async_context",
        domain=TaskDomain.CODING,
        prompt="Write an async context manager in Python that handles database connection pooling with proper cleanup on exit.",
        expected=["async with", "__aenter__", "__aexit__", "await"],
        scoring=ScoringMethod.CONTAINS,
        tags=["python", "async", "database"],
    ),
    RegressionTask(
        task_id="code_type_hints",
        domain=TaskDomain.CODING,
        prompt="Write a typed Python function that calculates compound interest: def compound_interest(principal: float, rate: float, periods: int) -> float:",
        expected=["def compound_interest", ": float", "-> float"],
        scoring=ScoringMethod.CONTAINS,
        tags=["python", "types", "finance"],
    ),
    RegressionTask(
        task_id="code_error_handling",
        domain=TaskDomain.CODING,
        prompt="Write a Python function with proper error handling that reads a JSON file and returns parsed data, handling FileNotFoundError, JSONDecodeError, and generic Exception.",
        expected=["try:", "except", "FileNotFoundError", "JSONDecodeError"],
        scoring=ScoringMethod.CONTAINS,
        tags=["python", "exceptions", "io"],
    ),
    RegressionTask(
        task_id="code_list_comprehension",
        domain=TaskDomain.CODING,
        prompt="Convert this loop to a list comprehension: result = []\\nfor x in range(10):\\n    if x % 2 == 0:\\n        result.append(x * 2)",
        expected=["[", "for x in", "if x % 2", "]"],
        scoring=ScoringMethod.CONTAINS,
        tags=["python", "comprehensions"],
    ),

    # ── PROTOCOL REASONING TASKS ──────────────────────────────────────────────
    RegressionTask(
        task_id="proto_risk_params",
        domain=TaskDomain.PROTOCOL,
        prompt="A trading strategy executes 100 trades. Each trade risks 1% of portfolio. What's the maximum drawdown if all trades lose? Express answer as a percentage.",
        expected=["63%", "63", "1%", "100"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["risk", "probability"],
    ),
    RegressionTask(
        task_id="proto_position_sizing",
        domain=TaskDomain.PROTOCOL,
        prompt="With $10,000 portfolio and 2% max risk per trade, and entry at $100 with stop loss at $95, what position size maximizes risk while staying within limits?",
        expected=["200", "2", "10000", "2"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["position_sizing", "risk_management"],
    ),
    RegressionTask(
        task_id="proto_spread_calc",
        domain=TaskDomain.PROTOCOL,
        prompt="Bid is $100.00, Ask is $100.05. What is the spread in basis points? Show your calculation.",
        expected=["5", "5 bps", "0.05", "basis point"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["spread", "market_data"],
    ),
    RegressionTask(
        task_id="proto_order_types",
        domain=TaskDomain.PROTOCOL,
        prompt="Explain the difference between a market order, limit order, and stop-loss order in terms of execution certainty and price control.",
        expected=["market", "limit", "stop", "certainty", "price"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["orders", "exchanges"],
    ),
    RegressionTask(
        task_id="proto_slippage",
        domain=TaskDomain.PROTOCOL,
        prompt="You place a market order for 1000 shares when the bid-ask is $10.00-$10.02. Estimated slippage if order moves the market 3 ticks?",
        expected=["6", "0.06", "0.6", "slippage"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["slippage", "execution"],
    ),

    # ── SELF-CHECK TASKS ──────────────────────────────────────────────────────
    RegressionTask(
        task_id="selfcheck_confidence_calibration",
        domain=TaskDomain.SELF_CHECK,
        prompt="Rate your confidence that you can correctly add two 5-digit numbers. Be precise about your uncertainty range.",
        expected=["70%", "80%", "90%", "95%", "99%", "certain"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["calibration", "uncertainty"],
    ),
    RegressionTask(
        task_id="selfcheck_error_detection",
        domain=TaskDomain.SELF_CHECK,
        prompt="Review this calculation: 2 + 2 = 5. Is there an error? If yes, identify it and provide the correct answer.",
        expected=["yes", "error", "4", "incorrect", "wrong"],
        scoring=ScoringMethod.CONTAINS,
        tags=["error_detection", "verification"],
    ),
    RegressionTask(
        task_id="selfcheck_assumption_check",
        domain=TaskDomain.SELF_CHECK,
        prompt="I'm implementing a feature that requires data from an external API. List 3 assumptions you're making that could cause failure.",
        expected=["availability", "rate limit", "format", "authentication", "latency", "quota"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["assumptions", "risk"],
    ),
    RegressionTask(
        task_id="selfcheck_boundary_case",
        domain=TaskDomain.SELF_CHECK,
        prompt="Write a function that processes a list. List 5 edge cases that would cause bugs if not handled.",
        expected=["empty", "null", "None", "single", "duplicate", "negative", "overflow"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["edge_cases", "testing"],
    ),
    RegressionTask(
        task_id="selfcheck_knowledge_limit",
        domain=TaskDomain.SELF_CHECK,
        prompt="What is the current Fed funds rate? Be honest about your knowledge cutoff and provide your best estimate with uncertainty.",
        expected=["uncertainty", "knowledge cutoff", "not know", "approx", "~"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["knowledge", "calibration"],
    ),

    # ── REASONING TASKS ───────────────────────────────────────────────────────
    RegressionTask(
        task_id="reason_hypothesis",
        domain=TaskDomain.REASONING,
        prompt="If strategy returns are normally distributed with mean 1% and std dev 2%, what's the probability of a negative return?",
        expected=["16%", "15%", "32%", "one sigma", "1.96", "sigma"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["statistics", "probability"],
    ),
    RegressionTask(
        task_id="reason_correlation",
        domain=TaskDomain.REASONING,
        prompt="Two assets have 0.7 correlation. When one goes up, what can you infer about the other? What's the limitation?",
        expected=["likely", "positive", "correlation", "not", "cause", "0.7"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["correlation", "statistics"],
    ),
    RegressionTask(
        task_id="reason_logic",
        domain=TaskDomain.REASONING,
        prompt="All portfolio managers are risk-aware. Some risk-aware people are conservative. Can we conclude some portfolio managers are conservative?",
        expected=["not", "conclude", "cannot", "unknown", "uncertain"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["logic", "syllogism"],
    ),

    # ── SAFETY TASKS ──────────────────────────────────────────────────────────
    RegressionTask(
        task_id="safety_risk_limits",
        domain=TaskDomain.SAFETY,
        prompt="A trading system has no max drawdown limit configured. List 3 failure modes and recommended safeguards.",
        expected=["loss", "circuit breaker", "max drawdown", "stop loss", "monitor", "alert"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["risk_management", "failsafe"],
    ),
    RegressionTask(
        task_id="safety_api_key",
        domain=TaskDomain.SAFETY,
        prompt="What are the security risks of hardcoding API keys in source code? Recommend alternatives.",
        expected=["expose", "git", "revoke", "env", "secret", "rotate"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["security", "api"],
    ),
    RegressionTask(
        task_id="safety_data_validation",
        domain=TaskDomain.SAFETY,
        prompt="An external feed provides prices. What validation steps are needed before using in trading decisions?",
        expected=["sanity", "stale", "range", "null", "validate", "verify"],
        scoring=ScoringMethod.SEMANTIC,
        tags=["validation", "data_quality"],
    ),
]


# ── Task Result ───────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    """Result of a single task evaluation."""
    task_id: str
    domain: str
    prompt: str
    response: str
    score: float
    max_score: float
    reason: str
    latency_ms: int
    error: Optional[str] = None

    @property
    def normalized(self) -> float:
        return self.score / (self.max_score or 1.0)

    @property
    def passed(self) -> bool:
        return self.normalized >= 0.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Regression Report ─────────────────────────────────────────────────────────

@dataclass
class RegressionReport:
    """Aggregate report for a regression suite run."""
    run_id: str
    suite_name: str
    timestamp: float
    executor_id: str
    results: List[TaskResult]
    total_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)

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
            "suite_name": self.suite_name,
            "timestamp": self.timestamp,
            "executor_id": self.executor_id,
            "overall_score": self.overall_score,
            "passed_count": self.passed_count,
            "total_count": len(self.results),
            "pass_rate": self.pass_rate,
            "total_ms": self.total_ms,
            "domain_scores": self.by_domain(),
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }

    def save(self, path: Path) -> None:
        """Append to JSONL file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(self.to_dict()) + "\n")


# ── Regression Suite ───────────────────────────────────────────────────────────

class RegressionSuite:
    """
    Regression detection suite for ProjectX.
    
    Features:
    - Built-in tasks covering coding, protocol, self-check, reasoning, safety
    - Pluggable executor (LLM, function, etc.)
    - Integration with ScoreRegistry for tracking
    - JSONL output compatible with eval_results.jsonl
    - Regression gate checking

    Usage::

        suite = RegressionSuite()
        report = suite.run(executor=my_llm)
        
        # With registry
        suite.run_with_tracking(executor=my_llm, registry=registry)
    """

    def __init__(
        self,
        tasks: Optional[List[RegressionTask]] = None,
        suite_name: str = SUITE_NAME,
        executor_id: str = "default",
    ) -> None:
        self._tasks: List[RegressionTask] = tasks or list(_BUILTIN_TASKS)
        self._suite_name = suite_name
        self._executor_id = executor_id

    def add(self, task: RegressionTask) -> None:
        """Add a custom task to the suite."""
        self._tasks.append(task)

    def add_tasks(self, tasks: List[RegressionTask]) -> None:
        """Add multiple custom tasks."""
        self._tasks.extend(tasks)

    def filter_domain(self, domain: TaskDomain) -> "RegressionSuite":
        """Return new suite filtered to domain."""
        return RegressionSuite(
            tasks=[t for t in self._tasks if t.domain == domain],
            suite_name=self._suite_name,
        )

    def filter_tags(self, *tags: str) -> "RegressionSuite":
        """Return new suite filtered by tags."""
        tag_set = set(tags)
        return RegressionSuite(
            tasks=[t for t in self._tasks if tag_set.intersection(t.tags)],
            suite_name=self._suite_name,
        )

    def __len__(self) -> int:
        return len(self._tasks)

    def __iter__(self):
        return iter(self._tasks)

    # ── Execution ─────────────────────────────────────────────────────────────

    def run(
        self,
        executor: Callable[[str, str], str],
        executor_id: Optional[str] = None,
        domains: Optional[List[TaskDomain]] = None,
        timeout_per_task: Optional[int] = None,
    ) -> RegressionReport:
        """
        Run the full suite against an executor.

        Args:
            executor: Callable(system_prompt, user_message) → response string
            executor_id: Label for this executor (stored in history)
            domains: Optionally restrict to specific domains
            timeout_per_task: Override default timeout per task

        Returns:
            RegressionReport with scores and statistics
        """
        run_id = uuid.uuid4().hex[:8]
        exec_id = executor_id or self._executor_id

        tasks = list(self._tasks)
        if domains:
            tasks = [t for t in tasks if t.domain in domains]

        results: List[TaskResult] = []
        t0_total = time.time()

        for task in tasks:
            t0 = time.time()
            error = None
            response = ""

            try:
                system_prompt = f"You are a {task.domain.value} expert. Answer concisely and precisely."
                timeout = timeout_per_task or task.timeout
                # Simple timeout via time check (actual timeout depends on executor)
                response = executor(system_prompt, task.prompt)
            except Exception as exc:
                error = str(exc)
                logger.warning("Regression task %s failed: %s", task.task_id, exc)

            score, reason = task.score(response) if not error else (0.0, f"error: {error}")
            latency = int((time.time() - t0) * 1000)

            results.append(TaskResult(
                task_id=task.task_id,
                domain=task.domain.value,
                prompt=task.prompt,
                response=response[:500] if response else "",
                score=score,
                max_score=task.max_score,
                reason=reason,
                latency_ms=latency,
                error=error,
            ))

        total_ms = int((time.time() - t0_total) * 1000)

        report = RegressionReport(
            run_id=run_id,
            suite_name=self._suite_name,
            timestamp=time.time(),
            executor_id=exec_id,
            results=results,
            total_ms=total_ms,
        )

        logger.info(
            "Regression suite %s: score=%.1f%% pass=%d/%d in %dms",
            run_id, report.overall_score * 100, report.passed_count, len(results), total_ms
        )
        return report

    def run_with_tracking(
        self,
        executor: Callable[[str, str], str],
        registry: Optional[ScoreRegistry] = None,
        executor_id: Optional[str] = None,
        domains: Optional[List[TaskDomain]] = None,
        enforce_gates: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[RegressionReport, Dict[str, Any]]:
        """
        Run suite and track scores in registry.

        Returns:
            Tuple of (report, gate_results)
        """
        registry = registry or get_registry()
        report = self.run(executor, executor_id, domains)

        # Record in registry
        score_record = registry.record_suite_run(
            suite_name=self._suite_name,
            score=report.overall_score,
            suite_type=SuiteType.REGRESSION,
            metadata={
                **(metadata or {}),
                "executor_id": report.executor_id,
                "run_id": report.run_id,
            },
            task_results=[r.to_dict() for r in report.results],
            domain_scores={d: s["score"] for d, s in report.by_domain().items()},
            latency_ms=report.total_ms,
        )

        # Check gates
        gate_results = {}
        if enforce_gates:
            gate_results = registry.enforce_all_gates(
                suite_names=[self._suite_name],
                raise_on_regression=False,
            )

        return report, gate_results


# ── Domain-specific suites ─────────────────────────────────────────────────────

def coding_suite() -> RegressionSuite:
    """Pre-built suite for coding tasks only."""
    return RegressionSuite().filter_domain(TaskDomain.CODING)


def protocol_suite() -> RegressionSuite:
    """Pre-built suite for protocol reasoning tasks."""
    return RegressionSuite().filter_domain(TaskDomain.PROTOCOL)


def self_check_suite() -> RegressionSuite:
    """Pre-built suite for self-check tasks."""
    return RegressionSuite().filter_domain(TaskDomain.SELF_CHECK)


def safety_suite() -> RegressionSuite:
    """Pre-built suite for safety tasks."""
    return RegressionSuite().filter_domain(TaskDomain.SAFETY)


# ── Stub executor for testing ─────────────────────────────────────────────────

def stub_executor(system: str, user: str) -> str:
    """Simple stub executor that returns a fixed response for testing."""
    return f"[stub response for: {user[:60]}...]"


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main(args: Optional[List[str]] = None) -> None:
    """CLI entry point for regression suite."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ProjectX Regression Suite")
    parser.add_argument("--domain", choices=[d.value for d in TaskDomain], help="Filter by domain")
    parser.add_argument("--tags", nargs="+", help="Filter by tags")
    parser.add_argument("--output", type=Path, help="Output JSONL path")
    parser.add_argument("--executor-id", default="cli", help="Executor identifier")
    parser.add_argument("--no-gates", action="store_true", help="Skip regression gate checks")
    parser.add_argument("--establish-baseline", action="store_true", help="Establish baseline from this run")
    args = parser.parse_args(args)

    # Build suite
    suite = RegressionSuite()
    if args.domain:
        suite = suite.filter_domain(TaskDomain(args.domain))
    if args.tags:
        suite = suite.filter_tags(*args.tags)

    print(f"Running regression suite: {len(suite)} tasks")

    # Run with stub executor (replace with real LLM in production)
    report = suite.run(executor=stub_executor, executor_id=args.executor_id)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Regression Suite Results")
    print(f"{'='*60}")
    print(f"  Overall Score:  {report.overall_score:.1%}")
    print(f"  Pass Rate:       {report.pass_rate:.1%}")
    print(f"  Passed:          {report.passed_count}/{len(report.results)}")
    print(f"  Total Time:      {report.total_ms}ms")

    print(f"\n  By Domain:")
    for domain, scores in report.by_domain().items():
        print(f"    {domain:12s}: {scores['score']:.1%} ({scores['count']} tasks)")

    # Save if output specified
    if args.output:
        report.save(args.output)
        print(f"\nResults saved to {args.output}")

    # Registry integration
    registry = get_registry()
    
    if args.establish_baseline:
        registry.establish_baseline(
            suite_name=SUITE_NAME,
            score=report.overall_score,
            established_by="cli",
        )
        print(f"\nBaseline established: {report.overall_score:.1%}")

    # Check for regressions
    delta = registry.get_delta(SUITE_NAME)
    if delta:
        print(f"\n{'='*60}")
        if delta.regression_detected:
            print(f"  REGRESSION DETECTED: {delta.absolute_delta:+.3f}")
            sys.exit(1)
        else:
            print(f"  Gate Status: PASS (score: {delta.current_score:.1%})")

    sys.exit(0 if report.pass_rate >= 0.7 else 1)


if __name__ == "__main__":
    main()
