"""
ProjectX Replay Harness — Tranche 2 Phase 10

Replay real SIMP tasks and score against established baselines.
Hook into existing benchmark.py patterns with JSONL output compatible with eval_results.jsonl.

Usage::

    harness = ReplayHarness(broker_url="http://127.0.0.1:5555")
    baseline = harness.load_baseline("data/simp_tasks/baseline_run_2024_01.json")
    
    results = harness.replay(baseline, executor=my_llm)
    report = harness.score_results(results, baseline)
"""

from __future__ import annotations

import json
import logging
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

SUITE_NAME = "projectx_replay"
DEFAULT_BASELINES_DIR = Path("data/replay_baselines")
DEFAULT_REPLAY_DIR = Path("data/replay_results")


# ── Enums ─────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ComparisonMode(str, Enum):
    STRICT = "strict"      # Exact match required
    RELAXED = "relaxed"    # Partial match allowed
    SEMANTIC = "semantic"  # LLM-based comparison


# ── Baseline Models ────────────────────────────────────────────────────────────

@dataclass
class BaselineTask:
    """A task from a baseline run."""
    task_id: str
    intent: Dict[str, Any]
    expected_response: Dict[str, Any]
    expected_fields: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaselineTask":
        return cls(**data)


@dataclass
class BaselineRun:
    """A complete baseline run to replay."""
    run_id: str
    name: str
    created_at: float
    task_count: int
    tasks: List[BaselineTask]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def task_ids(self) -> List[str]:
        return [t.task_id for t in self.tasks]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "created_at": self.created_at,
            "task_count": self.task_count,
            "tasks": [t.to_dict() for t in self.tasks],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaselineRun":
        tasks = [BaselineTask.from_dict(t) for t in data.get("tasks", [])]
        return cls(
            run_id=data["run_id"],
            name=data["name"],
            created_at=data["created_at"],
            task_count=data["task_count"],
            tasks=tasks,
            metadata=data.get("metadata", {}),
        )


# ── Replay Results ─────────────────────────────────────────────────────────────

@dataclass
class ReplayTaskResult:
    """Result of replaying a single task."""
    task_id: str
    status: TaskStatus
    baseline_task: BaselineTask
    actual_response: Dict[str, Any]
    score: float
    field_scores: Dict[str, float]
    latency_ms: int
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.score >= 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "actual_response": self.actual_response,
            "score": self.score,
            "field_scores": self.field_scores,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ReplayResults:
    """Results from replaying a full baseline."""
    run_id: str
    baseline_name: str
    baseline_id: str
    timestamp: float
    task_results: List[ReplayTaskResult]
    total_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def overall_score(self) -> float:
        if not self.task_results:
            return 0.0
        scores = [r.score for r in self.task_results if r.status == TaskStatus.COMPLETED]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.task_results if r.passed)

    @property
    def completion_rate(self) -> float:
        completed = sum(1 for r in self.task_results if r.status == TaskStatus.COMPLETED)
        return completed / len(self.task_results) if self.task_results else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "baseline_name": self.baseline_name,
            "baseline_id": self.baseline_id,
            "timestamp": self.timestamp,
            "overall_score": self.overall_score,
            "passed_count": self.passed_count,
            "total_tasks": len(self.task_results),
            "completion_rate": self.completion_rate,
            "total_ms": self.total_ms,
            "task_results": [r.to_dict() for r in self.task_results],
            "metadata": self.metadata,
        }

    def save(self, path: Path) -> None:
        """Save replay results to JSONL."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(self.to_dict()) + "\n")


# ── Score Comparator ────────────────────────────────────────────────────────────

class ResponseComparator:
    """
    Compare actual responses against expected baselines.
    
    Supports multiple comparison modes:
    - STRICT: Exact match on all expected fields
    - RELAXED: Partial match with thresholds
    - SEMANTIC: LLM-based semantic comparison
    """

    def __init__(
        self,
        mode: ComparisonMode = ComparisonMode.RELAXED,
        field_thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        self._mode = mode
        self._thresholds = field_thresholds or {
            "status": 0.9,
            "result": 0.7,
            "data": 0.7,
            "message": 0.5,
        }

    def compare(
        self,
        actual: Dict[str, Any],
        expected: BaselineTask,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compare actual response against expected baseline.
        
        Returns (overall_score, field_scores).
        """
        field_scores: Dict[str, float] = {}
        
        if not expected.expected_fields:
            # If no specific fields, check for any overlap
            return self._compare_any(actual, expected), field_scores

        for field_name in expected.expected_fields:
            field_scores[field_name] = self._compare_field(
                actual, expected, field_name
            )

        if not field_scores:
            return 0.0, {}

        # Weighted average
        weights = {k: 1.0 for k in field_scores}
        overall = sum(
            field_scores[k] * weights[k] for k in field_scores
        ) / sum(weights.values())
        
        return overall, field_scores

    def _compare_field(
        self,
        actual: Dict[str, Any],
        expected: BaselineTask,
        field_name: str,
    ) -> float:
        """Compare a single field."""
        actual_val = self._deep_get(actual, field_name)
        expected_val = self._deep_get(expected.expected_response, field_name)
        
        if actual_val is None and expected_val is None:
            return 1.0
        
        if actual_val is None or expected_val is None:
            return 0.0

        if isinstance(expected_val, (str, int, float, bool)):
            if self._mode == ComparisonMode.STRICT:
                return 1.0 if actual_val == expected_val else 0.0
            elif self._mode == ComparisonMode.RELAXED:
                return self._relaxed_match(str(actual_val), str(expected_val))
            else:
                # Semantic mode would use LLM - fall back to relaxed
                return self._relaxed_match(str(actual_val), str(expected_val))

        if isinstance(expected_val, dict):
            return self._compare_dict(actual_val, expected_val)

        if isinstance(expected_val, list):
            return self._compare_list(actual_val, expected_val)

        return self._relaxed_match(str(actual_val), str(expected_val))

    def _relaxed_match(self, actual: str, expected: str) -> float:
        """Fuzzy string matching."""
        actual_lower = actual.lower().strip()
        expected_lower = expected.lower().strip()
        
        if actual_lower == expected_lower:
            return 1.0
        
        # Check substring
        if expected_lower in actual_lower or actual_lower in expected_lower:
            return 0.7
        
        # Token overlap
        actual_tokens = set(actual_lower.split())
        expected_tokens = set(expected_lower.split())
        
        if not expected_tokens:
            return 1.0
        
        overlap = len(actual_tokens & expected_tokens) / len(expected_tokens)
        return overlap * 0.6  # Max 0.6 for token overlap

    def _compare_dict(self, actual: Dict, expected: Dict) -> float:
        """Compare dictionaries recursively."""
        if not expected:
            return 1.0 if actual else 0.0
        
        if not actual:
            return 0.0

        scores = []
        for key in expected:
            if key in actual:
                scores.append(self._relaxed_match(str(actual[key]), str(expected[key])))
        
        return sum(scores) / len(scores) if scores else 0.0

    def _compare_list(self, actual: List, expected: List) -> float:
        """Compare lists."""
        if not expected:
            return 1.0 if not actual else 0.5
        
        if not actual:
            return 0.0

        # Check if expected items are in actual
        hits = sum(1 for item in expected if item in actual)
        return hits / len(expected)

    def _compare_any(
        self,
        actual: Dict[str, Any],
        expected: BaselineTask,
    ) -> float:
        """Compare when no specific fields specified."""
        expected_str = json.dumps(expected.expected_response, sort_keys=True).lower()
        actual_str = json.dumps(actual, sort_keys=True).lower()
        return self._relaxed_match(actual_str, expected_str)

    def _deep_get(self, obj: Any, key: str) -> Any:
        """Get nested key from dict using dot notation."""
        parts = key.split(".")
        current = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return current


# ── Replay Harness ─────────────────────────────────────────────────────────────

class ReplayHarness:
    """
    Harness for replaying SIMP task baselines.
    
    Features:
    - Load baselines from JSON files
    - Replay tasks against current executor
    - Score results against baseline
    - Track in ScoreRegistry
    - JSONL output compatible with eval_results.jsonl
    """

    def __init__(
        self,
        baselines_dir: Optional[Path] = None,
        results_dir: Optional[Path] = None,
        broker_url: Optional[str] = None,
        api_key: Optional[str] = None,
        comparison_mode: ComparisonMode = ComparisonMode.RELAXED,
    ) -> None:
        self._baselines_dir = baselines_dir or DEFAULT_BASELINES_DIR
        self._results_dir = results_dir or DEFAULT_REPLAY_DIR
        self._broker_url = broker_url
        self._api_key = api_key
        self._comparator = ResponseComparator(mode=comparison_mode)
        
        # Ensure directories exist
        self._baselines_dir.mkdir(parents=True, exist_ok=True)
        self._results_dir.mkdir(parents=True, exist_ok=True)

    # ── Baseline Management ───────────────────────────────────────────────────

    def load_baseline(self, path: Path) -> Optional[BaselineRun]:
        """Load a baseline run from file."""
        try:
            data = json.loads(path.read_text())
            return BaselineRun.from_dict(data)
        except Exception as exc:
            logger.error("Failed to load baseline from %s: %s", path, exc)
            return None

    def save_baseline(self, baseline: BaselineRun, path: Optional[Path] = None) -> Path:
        """Save a baseline run to file."""
        path = path or self._baselines_dir / f"{baseline.name}_{baseline.run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(baseline.to_dict(), indent=2))
        logger.info("Saved baseline to %s", path)
        return path

    def list_baselines(self) -> List[Path]:
        """List available baseline files."""
        return list(self._baselines_dir.glob("*.json"))

    def capture_baseline(
        self,
        name: str,
        tasks: List[Dict[str, Any]],
        executor: Callable[[Dict[str, Any]], Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BaselineRun:
        """
        Capture a baseline by running tasks against an executor.
        
        This creates a new baseline from current behavior.
        """
        run_id = uuid.uuid4().hex[:8]
        baseline_tasks: List[BaselineTask] = []
        
        for i, task in enumerate(tasks):
            task_id = task.get("task_id", f"task_{i}")
            
            # Run task
            try:
                response = executor(task)
            except Exception as exc:
                logger.warning("Baseline capture task %s failed: %s", task_id, exc)
                response = {"error": str(exc)}
            
            # Extract expected fields
            expected_fields = list(response.keys()) if isinstance(response, dict) else []
            
            baseline_tasks.append(BaselineTask(
                task_id=task_id,
                intent=task,
                expected_response=response,
                expected_fields=expected_fields,
                metadata=task.get("metadata", {}),
            ))

        baseline = BaselineRun(
            run_id=run_id,
            name=name,
            created_at=time.time(),
            task_count=len(baseline_tasks),
            tasks=baseline_tasks,
            metadata=metadata or {},
        )

        self.save_baseline(baseline)
        return baseline

    # ── Replay ────────────────────────────────────────────────────────────────

    def replay(
        self,
        baseline: BaselineRun,
        executor: Callable[[Dict[str, Any]], Dict[str, Any]],
        task_filter: Optional[Callable[[BaselineTask], bool]] = None,
        skip_existing: bool = False,
    ) -> ReplayResults:
        """
        Replay a baseline against a new executor.
        
        Args:
            baseline: The baseline run to replay
            executor: Callable(task_dict) → response_dict
            task_filter: Optional filter for which tasks to run
            skip_existing: Skip tasks that already have results

        Returns:
            ReplayResults with scored comparisons
        """
        run_id = uuid.uuid4().hex[:8]
        tasks = baseline.tasks
        
        if task_filter:
            tasks = [t for t in tasks if task_filter(t)]

        results: List[ReplayTaskResult] = []
        t0_total = time.time()

        for task in tasks:
            t0 = time.time()
            status = TaskStatus.RUNNING
            actual_response: Dict[str, Any] = {}
            error = None

            try:
                actual_response = executor(task.intent)
                status = TaskStatus.COMPLETED
            except Exception as exc:
                error = str(exc)
                status = TaskStatus.FAILED
                logger.warning("Replay task %s failed: %s", task.task_id, exc)

            latency = int((time.time() - t0) * 1000)

            # Score if completed
            score = 0.0
            field_scores: Dict[str, float] = {}
            if status == TaskStatus.COMPLETED:
                score, field_scores = self._comparator.compare(actual_response, task)

            results.append(ReplayTaskResult(
                task_id=task.task_id,
                status=status,
                baseline_task=task,
                actual_response=actual_response,
                score=score,
                field_scores=field_scores,
                latency_ms=latency,
                error=error,
            ))

        total_ms = int((time.time() - t0_total) * 1000)

        replay_results = ReplayResults(
            run_id=run_id,
            baseline_name=baseline.name,
            baseline_id=baseline.run_id,
            timestamp=time.time(),
            task_results=results,
            total_ms=total_ms,
        )

        logger.info(
            "Replay completed: score=%.1f%% pass=%d/%d in %dms",
            replay_results.overall_score * 100,
            replay_results.passed_count,
            len(results),
            total_ms
        )
        return replay_results

    def replay_with_broker(
        self,
        baseline: BaselineRun,
        broker_url: Optional[str] = None,
        task_filter: Optional[Callable[[BaselineTask], bool]] = None,
    ) -> ReplayResults:
        """
        Replay baseline using SIMP broker HTTP API.
        
        Args:
            baseline: The baseline run to replay
            broker_url: Broker URL (uses self._broker_url if not provided)
            task_filter: Optional filter for which tasks to run
        """
        import urllib.request
        import urllib.error

        url = broker_url or self._broker_url or "http://127.0.0.1:5555"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        def broker_executor(intent: Dict[str, Any]) -> Dict[str, Any]:
            req = urllib.request.Request(
                f"{url}/api/execute",
                data=json.dumps(intent).encode(),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                return {"error": f"HTTP {exc.code}: {exc.reason}"}
            except Exception as exc:
                return {"error": str(exc)}

        return self.replay(baseline, broker_executor, task_filter)

    # ── Scoring & Comparison ──────────────────────────────────────────────────

    def score_results(
        self,
        results: ReplayResults,
        baseline: BaselineRun,
    ) -> Dict[str, Any]:
        """
        Generate detailed scoring report comparing results to baseline.
        """
        baseline_dict = {t.task_id: t for t in baseline.tasks}
        
        task_scores = []
        degraded_tasks = []
        improved_tasks = []

        for result in results.task_results:
            baseline_task = baseline_dict.get(result.task_id)
            if not baseline_task:
                continue

            task_scores.append(result.score)

            # Calculate delta from baseline
            baseline_score = self._get_baseline_score(baseline_task)
            delta = result.score - baseline_score

            task_report = {
                "task_id": result.task_id,
                "current_score": result.score,
                "baseline_score": baseline_score,
                "delta": delta,
                "passed": result.passed,
                "status": result.status.value,
            }

            if delta < -0.1:
                degraded_tasks.append(task_report)
            elif delta > 0.1:
                improved_tasks.append(task_report)

        return {
            "overall_score": results.overall_score,
            "baseline_score": sum(self._get_baseline_score(t) for t in baseline.tasks) / len(baseline.tasks),
            "delta": results.overall_score - sum(self._get_baseline_score(t) for t in baseline.tasks) / len(baseline.tasks),
            "passed_count": results.passed_count,
            "total_tasks": len(results.task_results),
            "completion_rate": results.completion_rate,
            "degraded_tasks": degraded_tasks,
            "improved_tasks": improved_tasks,
            "regression_detected": len(degraded_tasks) > len(improved_tasks),
        }

    def _get_baseline_score(self, task: BaselineTask) -> float:
        """Get baseline score for a task (currently just 1.0 for completed tasks)."""
        return 1.0  # Simplified - in reality would track historical performance

    # ── Registry Integration ───────────────────────────────────────────────────

    def run_with_tracking(
        self,
        baseline: BaselineRun,
        executor: Callable[[Dict[str, Any]], Dict[str, Any]],
        registry: Optional[ScoreRegistry] = None,
        task_filter: Optional[Callable[[BaselineTask], bool]] = None,
        enforce_gates: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ReplayResults, Dict[str, Any], Dict[str, DeltaResult]]:
        """
        Run replay with registry tracking and gate enforcement.
        
        Returns:
            Tuple of (results, scoring_report, gate_results)
        """
        registry = registry or get_registry()
        
        # Run replay
        results = self.replay(baseline, executor, task_filter)
        
        # Save results
        results.save(self._results_dir / "replay_results.jsonl")
        
        # Record in registry
        registry.record_suite_run(
            suite_name=SUITE_NAME,
            score=results.overall_score,
            suite_type=SuiteType.REPLAY,
            metadata={
                **(metadata or {}),
                "baseline_name": baseline.name,
                "baseline_id": baseline.run_id,
                "run_id": results.run_id,
            },
            task_results=[r.to_dict() for r in results.task_results],
            latency_ms=results.total_ms,
        )
        
        # Score against baseline
        scoring = self.score_results(results, baseline)
        
        # Check gates
        gate_results = {}
        if enforce_gates:
            gate_results = registry.enforce_all_gates(
                suite_names=[SUITE_NAME],
                raise_on_regression=False,
            )

        return results, scoring, gate_results

    # ── CLI Helpers ───────────────────────────────────────────────────────────

    def import_from_jsonl(
        self,
        path: Path,
        name: str,
        intent_extractor: Optional[Callable[[Dict], Dict]] = None,
        response_extractor: Optional[Callable[[Dict], Dict]] = None,
    ) -> Optional[BaselineRun]:
        """
        Import baseline from existing JSONL results file.
        
        Args:
            path: Path to JSONL file with historical results
            name: Name for the baseline
            intent_extractor: Function to extract intent from record
            response_extractor: Function to extract response from record
        """
        if intent_extractor is None:
            intent_extractor = lambda r: r.get("intent", {})
        if response_extractor is None:
            response_extractor = lambda r: r.get("response", r)
        
        tasks: List[BaselineTask] = []
        
        try:
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                
                tasks.append(BaselineTask(
                    task_id=record.get("task_id", record.get("id", uuid.uuid4().hex[:8])),
                    intent=intent_extractor(record),
                    expected_response=response_extractor(record),
                    expected_fields=list(response_extractor(record).keys()) if isinstance(response_extractor(record), dict) else [],
                ))
        except Exception as exc:
            logger.error("Failed to import from JSONL: %s", exc)
            return None

        if not tasks:
            return None

        baseline = BaselineRun(
            run_id=uuid.uuid4().hex[:8],
            name=name,
            created_at=time.time(),
            task_count=len(tasks),
            tasks=tasks,
        )
        
        self.save_baseline(baseline)
        return baseline


# ── Stub executor for testing ─────────────────────────────────────────────────

def stub_executor(task: Dict[str, Any]) -> Dict[str, Any]:
    """Simple stub executor for testing."""
    return {
        "status": "success",
        "result": f"[stub response for: {task.get('prompt', task.get('intent', {}).get('prompt', 'unknown'))[:50]}...]",
    }


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main(args: Optional[List[str]] = None) -> None:
    """CLI entry point for replay harness."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ProjectX Replay Harness")
    parser.add_argument("--baseline", type=Path, help="Path to baseline JSON file")
    parser.add_argument("--list-baselines", action="store_true", help="List available baselines")
    parser.add_argument("--broker", type=str, help="SIMP broker URL")
    parser.add_argument("--output", type=Path, help="Output path for results")
    parser.add_argument("--import-jsonl", type=Path, help="Import baseline from JSONL")
    parser.add_argument("--import-name", type=str, help="Name for imported baseline")
    args = parser.parse_args(args)

    harness = ReplayHarness()

    # List baselines
    if args.list_baselines:
        baselines = harness.list_baselines()
        print("Available baselines:")
        for b in baselines:
            print(f"  {b.name}")
        return

    # Import from JSONL
    if args.import_jsonl:
        name = args.import_name or args.import_jsonl.stem
        baseline = harness.import_from_jsonl(args.import_jsonl, name)
        if baseline:
            print(f"Imported baseline '{baseline.name}' with {baseline.task_count} tasks")
        else:
            print("Failed to import baseline")
            sys.exit(1)
        return

    # Load baseline
    if not args.baseline:
        print("Error: --baseline required")
        sys.exit(1)
    
    baseline = harness.load_baseline(args.baseline)
    if not baseline:
        print(f"Failed to load baseline from {args.baseline}")
        sys.exit(1)

    print(f"Loaded baseline '{baseline.name}' with {baseline.task_count} tasks")

    # Replay with broker
    if args.broker:
        print(f"Replaying against broker: {args.broker}")
        results = harness.replay_with_broker(baseline, args.broker)
    else:
        print("Using stub executor (specify --broker for real replay)")
        results = harness.replay(baseline, stub_executor)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Replay Results")
    print(f"{'='*60}")
    print(f"  Overall Score:   {results.overall_score:.1%}")
    print(f"  Passed:          {results.passed_count}/{len(results.task_results)}")
    print(f"  Completion:     {results.completion_rate:.1%}")
    print(f"  Total Time:      {results.total_ms}ms")

    # Show task details
    print(f"\n  Task Results:")
    for result in results.task_results:
        status_icon = "✓" if result.passed else "✗" if result.status == TaskStatus.FAILED else "○"
        print(f"    {status_icon} {result.task_id}: {result.score:.1%}")

    # Save results
    if args.output:
        results.save(args.output)
        print(f"\nResults saved to {args.output}")

    sys.exit(0 if results.overall_score >= 0.7 else 1)


if __name__ == "__main__":
    main()
