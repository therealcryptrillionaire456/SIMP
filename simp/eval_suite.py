"""
SIMP Evaluation Dataset Runner — eval_suite

Loads datasets of test intents, routes them through the SIMP broker (HTTP API or
file-based), collects responses, and scores them using configurable evaluators.

Supports:
  - EvaluationDataset / EvalResult / EvalReport dataclasses
  - JSON/JSONL dataset loading from data/eval_datasets/
  - Broker HTTP API routing or offline file-based routing
  - Pass/fail, score-based, and LLM-as-judge stub evaluators
  - Append-only JSONL results persistence in data/eval_results.jsonl
  - Module-level singleton via get_eval_suite()
  - CLI entry point when run as ``__main__``
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_DATASETS_DIR = Path("data/eval_datasets")
_RESULTS_PATH = Path("data/eval_results.jsonl")
_EVAL_LOCK = threading.Lock()

# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class EvaluationDataset:
    """A named collection of test intents for evaluation."""

    name: str
    description: str
    intents: List[Dict[str, Any]]
    expected_results: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("EvaluationDataset.name must be non-empty")
        if not self.intents:
            raise ValueError("EvaluationDataset.intents must be non-empty")


@dataclass
class EvalResult:
    """Outcome of evaluating a single intent."""

    intent_id: str
    passed: bool
    score: float
    latency_ms: float
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvalResult:
        return cls(**data)


@dataclass
class EvalReport:
    """Aggregate statistics from a full evaluation run."""

    suite_name: str
    total: int
    passed: int
    failed: int
    avg_score: float
    avg_latency: float
    results: List[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "avg_score": self.avg_score,
            "avg_latency": self.avg_latency,
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvalReport:
        results = [EvalResult.from_dict(r) for r in data.get("results", [])]
        return cls(
            suite_name=data["suite_name"],
            total=data["total"],
            passed=data["passed"],
            failed=data["failed"],
            avg_score=data["avg_score"],
            avg_latency=data["avg_latency"],
            results=results,
        )


# ── Evaluator protocol ────────────────────────────────────────────────────────

class BaseEvaluator:
    """Abstract evaluator that scores a response against expected results.

    Subclasses override ``evaluate()`` to implement custom scoring logic.
    """

    def evaluate(
        self,
        intent: Dict[str, Any],
        response: Optional[Dict[str, Any]],
        expected: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, List[str]]:
        """Return (passed, score, list_of_errors).

        *passed* is a boolean pass/fail.
        *score* is a float in [0.0, 1.0] where 1.0 = perfect.
        *errors* is a list of human-readable error messages.
        """
        raise NotImplementedError


class PassFailEvaluator(BaseEvaluator):
    """Simple pass/fail: passes if response is non-empty and contains no error keys."""

    ERROR_KEYS = frozenset({"error", "exception", "failure", "traceback"})

    def evaluate(
        self,
        intent: Dict[str, Any],
        response: Optional[Dict[str, Any]],
        expected: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, List[str]]:
        errors: List[str] = []
        if response is None:
            errors.append("No response received")
            return False, 0.0, errors

        # Check for error keys in response
        for key in self.ERROR_KEYS:
            val = _deep_get(response, key)
            if val is not None and val:
                errors.append(f"Response contains '{key}': {val}")

        # If expected results provided, validate exact match
        if expected is not None:
            if isinstance(expected, dict):
                for exp_key, exp_val in expected.items():
                    actual = _deep_get(response, exp_key)
                    if actual != exp_val:
                        errors.append(
                            f"Expected {exp_key}={exp_val!r}, got {actual!r}"
                        )
            else:
                # Scalar expected value — compare directly to response
                if response != expected:
                    errors.append(
                        f"Expected response={expected!r}, got {response!r}"
                    )

        passed = len(errors) == 0
        score = 1.0 if passed else 0.0
        return passed, score, errors


class ScoreBasedEvaluator(BaseEvaluator):
    """Evaluator that assigns a score based on a custom scoring function.

    The scoring function receives (intent, response, expected) and returns
    a float in [0.0, 1.0]. The pass threshold determines pass/fail.
    """

    def __init__(
        self,
        score_fn: Callable[[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]], float],
        pass_threshold: float = 0.7,
    ) -> None:
        self._score_fn = score_fn
        self._pass_threshold = pass_threshold

    def evaluate(
        self,
        intent: Dict[str, Any],
        response: Optional[Dict[str, Any]],
        expected: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, List[str]]:
        errors: List[str] = []
        if response is None:
            errors.append("No response received")
            return False, 0.0, errors

        try:
            score = self._score_fn(intent, response, expected)
        except Exception as exc:
            errors.append(f"Scoring function raised: {exc}")
            return False, 0.0, errors

        score = max(0.0, min(1.0, score))
        passed = score >= self._pass_threshold
        if not passed:
            errors.append(f"Score {score:.3f} below threshold {self._pass_threshold}")
        return passed, score, errors


class LLMAsJudgeStub(BaseEvaluator):
    """Stub LLM-as-judge evaluator for local testing.

    Simulates an LLM judge by checking keyword overlap between expected and
    response keys.  Replace with a real LLM call for production use.
    """

    def evaluate(
        self,
        intent: Dict[str, Any],
        response: Optional[Dict[str, Any]],
        expected: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, List[str]]:
        errors: List[str] = []
        if response is None:
            errors.append("No response received")
            return False, 0.0, errors
        if expected is None:
            # No ground truth — returns a neutral score
            return True, 0.5, []

        # Shallow key overlap + value match heuristic
        if not isinstance(expected, dict):
            # Scalar expected — treat as simple equality
            match = response == expected
            score = 1.0 if match else 0.0
            if not match:
                errors.append(f"LLM judge: expected {expected!r}, got {response!r}")
            return match, score, errors

        resp_keys = set(response.keys()) if isinstance(response, dict) else set()
        exp_keys = set(expected.keys())
        common = resp_keys & exp_keys

        if not common:
            errors.append("No overlapping keys between response and expected")
            return False, 0.0, errors

        exact_matches = sum(
            1 for k in common if isinstance(response, dict) and response.get(k) == expected.get(k)
        )
        score = exact_matches / len(common) if common else 0.0

        if score < 0.5:
            errors.append(f"LLM judge score {score:.3f} below 0.5 threshold")
            return False, score, errors

        return True, score, errors


# ── Dataset loader ────────────────────────────────────────────────────────────


def load_dataset_from_file(path: Path) -> EvaluationDataset:
    """Load a single dataset from a JSON or JSONL file.

    JSON files must contain either a single ``EvaluationDataset``-shaped object,
    or a list of intent dicts.  In the latter case the filename stem becomes
    the dataset name.

    JSONL files are treated as one intent per line; the filename stem becomes
    the dataset name and no expected results are loaded.
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    suffix = path.suffix.lower()
    name = path.stem

    if suffix == ".json":
        with open(path, "r") as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Full dataset object or single intent
            if "intents" in data:
                return EvaluationDataset(
                    name=data.get("name", name),
                    description=data.get("description", f"Loaded from {path.name}"),
                    intents=data["intents"],
                    expected_results=data.get("expected_results"),
                )
            else:
                # Single intent wrapped as a list
                return EvaluationDataset(
                    name=name,
                    description=f"Single intent from {path.name}",
                    intents=[data],
                )
        elif isinstance(data, list):
            return EvaluationDataset(
                name=name,
                description=f"List of {len(data)} intents from {path.name}",
                intents=data,
            )
        else:
            raise ValueError(f"Unexpected JSON structure in {path}")

    elif suffix == ".jsonl":
        intents: List[Dict[str, Any]] = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    intents.append(json.loads(line))
        return EvaluationDataset(
            name=name,
            description=f"{len(intents)} intents from {path.name}",
            intents=intents,
        )
    else:
        raise ValueError(f"Unsupported dataset format: {suffix} (supported: .json, .jsonl)")


def load_all_datasets(datasets_dir: Optional[Path] = None) -> Dict[str, EvaluationDataset]:
    """Load all datasets from ``datasets_dir`` (default: ``data/eval_datasets/``).

    Returns a dict keyed by dataset name.
    """
    directory = datasets_dir or _DATASETS_DIR
    if not directory.exists():
        logger.warning("Eval datasets directory does not exist: %s", directory)
        return {}

    datasets: Dict[str, EvaluationDataset] = {}
    for child in sorted(directory.iterdir()):
        if child.suffix.lower() in (".json", ".jsonl"):
            try:
                ds = load_dataset_from_file(child)
                datasets[ds.name] = ds
            except Exception as exc:
                logger.error("Failed to load dataset %s: %s", child.name, exc)
    return datasets


# ── Intent runner ─────────────────────────────────────────────────────────────


class IntentRunner:
    """Routes intents to the SIMP broker or runs them offline.

    Mode is determined by ``broker_url``:
      - If set → HTTP POST to ``{broker_url}/intents/route``
      - If ``None`` → file-based simulation returns the intent back as response
    """

    def __init__(self, broker_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self._broker_url = broker_url.rstrip("/") if broker_url else None
        self._api_key = api_key

    def run_intent(self, intent: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], float]:
        """Execute a single intent and return (response_dict, latency_ms).

        Returns ``(None, latency_ms)`` on failure.
        """
        start = time.perf_counter()
        try:
            if self._broker_url:
                response = self._run_http(intent)
            else:
                response = self._run_file_based(intent)
            elapsed = (time.perf_counter() - start) * 1000.0
            return response, elapsed
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            logger.error("Intent run failed: %s", exc)
            return None, elapsed

    def _run_http(self, intent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST the intent to the broker HTTP API."""
        import urllib.request
        import urllib.error

        url = f"{self._broker_url}/intents/route"
        payload = json.dumps({
            "intent_type": intent.get("intent_type", "ping"),
            "source_agent": intent.get("source_agent", "eval_suite"),
            "target_agent": intent.get("target_agent", "auto"),
            **{k: v for k, v in intent.items() if k not in ("intent_type", "source_agent", "target_agent")},
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)

    def _run_file_based(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate routing by returning a synthetic response.

        This is useful for offline testing of the evaluation framework itself
        without requiring a running broker.
        """
        return {
            "status": "ok",
            "echo": intent,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    def default_broker_url(self) -> Optional[str]:
        """Return the best-guess local broker URL or None."""
        if self._broker_url:
            return self._broker_url
        # Common local deployments
        for candidate in ("http://127.0.0.1:5555", "http://localhost:5555"):
            try:
                import urllib.request
                req = urllib.request.Request(f"{candidate}/health", method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        return candidate
            except Exception:
                continue
        return None


# ── EvalSuite ─────────────────────────────────────────────────────────────────


_CLI_DESCRIPTION = """
SIMP Evaluation Suite Runner

Options:
  --broker URL     SIMP broker HTTP URL (default: auto-detect localhost:5555)
  --api-key KEY    API key for broker auth
  --dataset NAME   Run only a specific dataset by name
  --list           List available datasets and exit
  --evaluator {passfail,score,llmstub}
                   Evaluator type (default: passfail)
  --pass-threshold FLOAT
                   Pass threshold for score-based evaluator (default: 0.7)
  --output FILE    Write report JSON to file
  --results-dir DIR
                   Directory to scan for datasets (default: data/eval_datasets)
"""


class EvalSuite:
    """Evaluation suite that loads datasets, runs intents, and scores results.

    Usage::

        suite = EvalSuite()
        suite.load_datasets()
        report = suite.run_all()
        print(report.to_dict())
    """

    def __init__(
        self,
        datasets_dir: Optional[Path] = None,
        broker_url: Optional[str] = None,
        api_key: Optional[str] = None,
        evaluator: Optional[BaseEvaluator] = None,
    ) -> None:
        self._datasets_dir = Path(datasets_dir) if datasets_dir else _DATASETS_DIR
        self._runner = IntentRunner(broker_url=broker_url, api_key=api_key)
        self._evaluator = evaluator or PassFailEvaluator()
        self._datasets: Dict[str, EvaluationDataset] = {}
        self._results_path = _RESULTS_PATH
        self._lock = threading.Lock()

    # ── Dataset management ───────────────────────────────────────────────

    def load_datasets(self, datasets_dir: Optional[Path] = None) -> Dict[str, EvaluationDataset]:
        """Scan datasets dir and load all JSON/JSONL files."""
        directory = datasets_dir or self._datasets_dir
        self._datasets = load_all_datasets(directory)
        logger.info("Loaded %d datasets from %s", len(self._datasets), directory)
        return self._datasets

    def get_dataset(self, name: str) -> Optional[EvaluationDataset]:
        """Retrieve a loaded dataset by name."""
        return self._datasets.get(name)

    def list_datasets(self) -> List[str]:
        """Return sorted names of all loaded datasets."""
        return sorted(self._datasets.keys())

    # ── Running ──────────────────────────────────────────────────────────

    def run_dataset(self, dataset: EvaluationDataset) -> EvalReport:
        """Evaluate all intents in a dataset and return a report."""
        results: List[EvalResult] = []
        for idx, intent in enumerate(dataset.intents):
            intent_id = intent.get("id", intent.get("intent_id", f"{dataset.name}:{idx}"))
            expected = None
            if dataset.expected_results:
                expected = dataset.expected_results.get(intent_id)

            response, latency_ms = self._runner.run_intent(intent)
            passed, score, errors = self._evaluator.evaluate(intent, response, expected)

            result = EvalResult(
                intent_id=str(intent_id),
                passed=passed,
                score=score,
                latency_ms=latency_ms,
                errors=errors,
                metadata={
                    "dataset": dataset.name,
                    "intent_type": intent.get("intent_type", "unknown"),
                    "target_agent": intent.get("target_agent", "auto"),
                },
            )
            results.append(result)

            logger.debug(
                "Intent %s: passed=%s score=%.3f latency=%.1fms errors=%d",
                intent_id, passed, score, latency_ms, len(errors),
            )

        passed_count = sum(1 for r in results if r.passed)
        failed_count = sum(1 for r in results if not r.passed)
        avg_score = (
            sum(r.score for r in results) / len(results) if results else 0.0
        )
        avg_latency = (
            sum(r.latency_ms for r in results) / len(results) if results else 0.0
        )

        report = EvalReport(
            suite_name=dataset.name,
            total=len(results),
            passed=passed_count,
            failed=failed_count,
            avg_score=avg_score,
            avg_latency=avg_latency,
            results=results,
        )

        self._persist_results(report)
        return report

    def run_all(self, dataset_names: Optional[List[str]] = None) -> Dict[str, EvalReport]:
        """Run all loaded datasets (or a subset by name) and return reports keyed by name."""
        if not self._datasets:
            self.load_datasets()

        targets = (
            [n for n in dataset_names if n in self._datasets]
            if dataset_names
            else list(self._datasets.keys())
        )

        reports: Dict[str, EvalReport] = {}
        for name in targets:
            ds = self._datasets[name]
            logger.info("Running dataset: %s (%d intents)", name, len(ds.intents))
            reports[name] = self.run_dataset(ds)

        return reports

    def run_single(self, intent: Dict[str, Any], dataset_name: str = "adhoc") -> EvalResult:
        """Evaluate a single ad-hoc intent."""
        intent_id = intent.get("id", intent.get("intent_id", f"{dataset_name}:single"))

        response, latency_ms = self._runner.run_intent(intent)
        passed, score, errors = self._evaluator.evaluate(intent, response, None)

        result = EvalResult(
            intent_id=str(intent_id),
            passed=passed,
            score=score,
            latency_ms=latency_ms,
            errors=errors,
            metadata={
                "dataset": dataset_name,
                "intent_type": intent.get("intent_type", "unknown"),
                "target_agent": intent.get("target_agent", "auto"),
            },
        )
        return result

    # ── Results persistence ──────────────────────────────────────────────

    def _persist_results(self, report: EvalReport) -> None:
        """Append results to the JSONL results file."""
        try:
            with self._lock:
                self._results_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._results_path, "a") as f:
                    record = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        **report.to_dict(),
                    }
                    f.write(json.dumps(record) + "\n")
        except Exception as exc:
            logger.error("Failed to persist results: %s", exc)

    def load_results_history(self) -> List[Dict[str, Any]]:
        """Load all past eval results from the JSONL file."""
        if not self._results_path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with open(self._results_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def generate_summary_report(self, reports: Dict[str, EvalReport]) -> Dict[str, Any]:
        """Generate an aggregate summary across all datasets."""
        total_intents = sum(r.total for r in reports.values())
        total_passed = sum(r.passed for r in reports.values())
        total_failed = sum(r.failed for r in reports.values())
        all_scores = [r.avg_score for r in reports.values()]
        all_latencies = [r.avg_latency for r in reports.values()]

        return {
            "suit_name": "summary",
            "total_datasets": len(reports),
            "total_intents": total_intents,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "overall_pass_rate": total_passed / total_intents if total_intents > 0 else 0.0,
            "avg_score_across_datasets": (
                sum(all_scores) / len(all_scores) if all_scores else 0.0
            ),
            "avg_latency_across_datasets": (
                sum(all_latencies) / len(all_latencies) if all_latencies else 0.0
            ),
            "datasets": {name: r.to_dict() for name, r in reports.items()},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ── Helper ────────────────────────────────────────────────────────────────────


def _deep_get(d: Any, key: str, default: Any = None) -> Any:
    """Dot-notation access into nested dicts, e.g. ``_deep_get(d, "a.b.c")``."""
    if not d:
        return default
    parts = key.split(".")
    current = d
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, default)
        else:
            return default
    return current


# ── Module-level singleton ────────────────────────────────────────────────────

_suite: Optional[EvalSuite] = None
_SUITE_LOCK = threading.Lock()


def get_eval_suite(
    datasets_dir: Optional[Path] = None,
    broker_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> EvalSuite:
    """Return the module-level ``EvalSuite`` singleton.

    Thread-safe double-checked locking.  Subsequent calls ignore arguments;
    use :func:`reconfigure_eval_suite` to change settings.
    """
    global _suite
    if _suite is None:
        with _SUITE_LOCK:
            if _suite is None:
                _suite = EvalSuite(
                    datasets_dir=datasets_dir,
                    broker_url=broker_url,
                    api_key=api_key,
                )
    return _suite


def reconfigure_eval_suite(
    datasets_dir: Optional[Path] = None,
    broker_url: Optional[str] = None,
    api_key: Optional[str] = None,
    evaluator: Optional[BaseEvaluator] = None,
) -> EvalSuite:
    """Replace the singleton suite with a new configuration.

    Use this when you need to change the broker URL or evaluator after init.
    """
    global _suite
    with _SUITE_LOCK:
        _suite = EvalSuite(
            datasets_dir=datasets_dir,
            broker_url=broker_url,
            api_key=api_key,
            evaluator=evaluator,
        )
    return _suite


# ── CLI entry point ───────────────────────────────────────────────────────────


def _parse_cli_args(args: Optional[List[str]] = None) -> Dict[str, Any]:
    """Minimal CLI parser.  Accepts --key value style arguments."""
    import sys

    argv = args if args is not None else sys.argv[1:]
    opts: Dict[str, Any] = {}

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--broker" and i + 1 < len(argv):
            opts["broker_url"] = argv[i + 1]
            i += 2
        elif arg == "--api-key" and i + 1 < len(argv):
            opts["api_key"] = argv[i + 1]
            i += 2
        elif arg == "--dataset" and i + 1 < len(argv):
            opts.setdefault("dataset_names", []).append(argv[i + 1])
            i += 2
        elif arg == "--list":
            opts["list_only"] = True
            i += 1
        elif arg == "--evaluator" and i + 1 < len(argv):
            opts["evaluator_type"] = argv[i + 1]
            i += 2
        elif arg == "--pass-threshold" and i + 1 < len(argv):
            opts["pass_threshold"] = float(argv[i + 1])
            i += 2
        elif arg == "--output" and i + 1 < len(argv):
            opts["output"] = argv[i + 1]
            i += 2
        elif arg == "--results-dir" and i + 1 < len(argv):
            opts["results_dir"] = argv[i + 1]
            i += 2
        elif arg == "--help":
            print(_CLI_DESCRIPTION)
            raise SystemExit(0)
        else:
            print(f"Unknown option: {arg}")
            print(_CLI_DESCRIPTION)
            raise SystemExit(1)
    return opts


def main(args: Optional[List[str]] = None) -> None:
    """CLI entry point for ``python3.10 -m simp.eval_suite``."""
    import sys

    opts = _parse_cli_args(args)

    # Resolve datasets dir
    datasets_dir = Path(opts.get("results_dir", _DATASETS_DIR))

    # Resolve evaluator
    evaluator_type = opts.get("evaluator_type", "passfail")
    pass_threshold = opts.get("pass_threshold", 0.7)
    if evaluator_type == "score":
        evaluator = ScoreBasedEvaluator(
            score_fn=lambda i, r, e: random.uniform(0.0, 1.0),  # placeholder
            pass_threshold=pass_threshold,
        )
    elif evaluator_type == "llmstub":
        evaluator = LLMAsJudgeStub()
    else:
        evaluator = PassFailEvaluator()

    # Build suite
    suite = get_eval_suite(
        datasets_dir=datasets_dir,
        broker_url=opts.get("broker_url"),
        api_key=opts.get("api_key"),
    )
    suite._evaluator = evaluator

    # Load datasets
    suite.load_datasets()

    if opts.get("list_only"):
        print("Available datasets:")
        for name in suite.list_datasets():
            ds = suite.get_dataset(name)
            count = len(ds.intents) if ds else 0
            print(f"  {name}: {count} intents")
        return

    # Run
    dataset_names = opts.get("dataset_names")
    reports = suite.run_all(dataset_names=dataset_names)

    if not reports:
        print("No datasets available to run.")
        return

    summary = suite.generate_summary_report(reports)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Eval Suite Summary")
    print(f"{'='*60}")
    print(f"  Datasets run:      {summary['total_datasets']}")
    print(f"  Total intents:     {summary['total_intents']}")
    print(f"  Total passed:      {summary['total_passed']}")
    print(f"  Total failed:      {summary['total_failed']}")
    print(f"  Overall pass rate: {summary['overall_pass_rate']:.1%}")
    print(f"  Avg score:         {summary['avg_score_across_datasets']:.3f}")
    print(f"  Avg latency:       {summary['avg_latency_across_datasets']:.1f}ms")

    for ds_name, report in reports.items():
        print(f"\n  Dataset: {ds_name}")
        print(f"    Passed:  {report.passed}/{report.total}")
        print(f"    Score:   {report.avg_score:.3f}")
        print(f"    Latency: {report.avg_latency:.1f}ms")

    # Write output file if requested
    output_path = opts.get("output")
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, indent=2))
        print(f"\nReport written to {output_path}")

    # Exit with non-zero if any dataset had failures
    if summary["total_failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
