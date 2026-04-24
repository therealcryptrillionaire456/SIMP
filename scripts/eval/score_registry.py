"""
ProjectX Eval Score Registry — Tranche 2 Phase 10

Tracks eval scores over time with delta detection and regression gates.
Hook into existing benchmark.py patterns with JSONL output compatible
with eval_results.jsonl.

Usage::

    registry = ScoreRegistry(base_dir="data/evals")
    registry.record_suite_run("coding", 0.85, metadata={"commit": "abc123"})
    
    delta = registry.get_delta("coding")
    if delta and delta.regression_detected:
        print("REGRESSION: score dropped", delta.absolute_delta)
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import logging

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_REGISTRY_DIR = Path("data/evals")
DEFAULT_RESULTS_FILE = "eval_results.jsonl"
DEFAULT_BASELINE_FILE = "baselines.json"
DEFAULT_HISTORY_DIR = "history"

REGRESSION_THRESHOLD_DEFAULT = 0.05  # 5% drop triggers regression gate


# ── Enums ─────────────────────────────────────────────────────────────────────

class SuiteType(str, Enum):
    REGRESSION = "regression"
    REPLAY = "replay"
    ADVERSARIAL = "adversarial"
    CUSTOM = "custom"


class RegressionStatus(str, Enum):
    PASS = "pass"
    REGRESSION = "regression"
    IMPROVEMENT = "improvement"
    INSUFFICIENT_DATA = "insufficient_data"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class EvalScore:
    """Single evaluation score record."""
    suite_name: str
    suite_type: SuiteType
    score: float
    timestamp: float
    run_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    domain_scores: Dict[str, float] = field(default_factory=dict)
    latency_ms: int = 0
    error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "suite_type": self.suite_type.value,
            "score": self.score,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "metadata": self.metadata,
            "task_results": self.task_results,
            "domain_scores": self.domain_scores,
            "latency_ms": self.latency_ms,
            "error_count": self.error_count,
        }


@dataclass
class Baseline:
    """Baseline score for a suite."""
    suite_name: str
    score: float
    established_at: float
    established_by: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeltaResult:
    """Delta between current and baseline."""
    suite_name: str
    current_score: float
    baseline_score: float
    absolute_delta: float
    relative_delta: float
    regression_detected: bool
    status: RegressionStatus
    runs_since_baseline: int


@dataclass
class RegistrySummary:
    """Summary of all tracked suites."""
    suite_names: List[str]
    total_runs: int
    latest_scores: Dict[str, float]
    regression_alerts: List[DeltaResult]
    improvements: List[DeltaResult]


# ── Score Registry ─────────────────────────────────────────────────────────────

class ScoreRegistry:
    """
    Thread-safe registry for tracking eval scores over time.
    
    Features:
    - Append-only JSONL results storage
    - Baseline establishment and comparison
    - Delta detection with configurable thresholds
    - Regression gate checking (fail if drop > threshold)
    - Per-suite history retrieval
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        results_file: str = DEFAULT_RESULTS_FILE,
        baseline_file: str = DEFAULT_BASELINE_FILE,
        regression_threshold: float = REGRESSION_THRESHOLD_DEFAULT,
    ) -> None:
        self._base_dir = (base_dir or DEFAULT_REGISTRY_DIR).resolve()
        self._results_file = self._base_dir / results_file
        self._baseline_file = self._base_dir / baseline_file
        self._history_dir = self._base_dir / DEFAULT_HISTORY_DIR
        self._regression_threshold = regression_threshold
        self._lock = threading.RLock()
        
        self._baselines: Dict[str, Baseline] = {}
        self._load_baselines()
        
        # Ensure directories exist
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir.mkdir(parents=True, exist_ok=True)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_baselines(self) -> None:
        """Load baselines from disk."""
        if self._baseline_file.exists():
            try:
                data = json.loads(self._baseline_file.read_text())
                for suite_name, baseline_data in data.items():
                    self._baselines[suite_name] = Baseline(**baseline_data)
            except Exception as exc:
                logger.warning("Failed to load baselines: %s", exc)

    def _save_baselines(self) -> None:
        """Persist baselines to disk."""
        data = {
            suite_name: baseline.to_dict()
            for suite_name, baseline in self._baselines.items()
        }
        self._baseline_file.write_text(json.dumps(data, indent=2))

    def _append_result(self, score: EvalScore) -> None:
        """Append score to JSONL results file."""
        with self._lock:
            with open(self._results_file, "a") as f:
                f.write(json.dumps(score.to_dict()) + "\n")

    # ── Recording ─────────────────────────────────────────────────────────────

    def record_suite_run(
        self,
        suite_name: str,
        score: float,
        suite_type: SuiteType = SuiteType.REGRESSION,
        metadata: Optional[Dict[str, Any]] = None,
        task_results: Optional[List[Dict[str, Any]]] = None,
        domain_scores: Optional[Dict[str, float]] = None,
        latency_ms: int = 0,
        error_count: int = 0,
        run_id: Optional[str] = None,
    ) -> EvalScore:
        """Record a single evaluation run."""
        import uuid
        score_record = EvalScore(
            suite_name=suite_name,
            suite_type=suite_type,
            score=max(0.0, min(1.0, score)),
            timestamp=time.time(),
            run_id=run_id or uuid.uuid4().hex[:8],
            metadata=metadata or {},
            task_results=task_results or [],
            domain_scores=domain_scores or {},
            latency_ms=latency_ms,
            error_count=error_count,
        )
        
        self._append_result(score_record)
        self._prune_history(suite_name)
        
        logger.info(
            "Recorded %s score for '%s': %.3f (run=%s)",
            suite_type.value, suite_name, score, score_record.run_id
        )
        return score_record

    def _prune_history(self, suite_name: str) -> None:
        """Prune history files to last 100 runs per suite."""
        hist_file = self._history_dir / f"{suite_name}.jsonl"
        if hist_file.exists():
            try:
                lines = hist_file.read_text().splitlines()
                if len(lines) > 100:
                    pruned = lines[-100:]
                    hist_file.write_text("\n".join(pruned) + "\n")
            except Exception as exc:
                logger.warning("Failed to prune history for %s: %s", suite_name, exc)

    # ── Baseline Management ───────────────────────────────────────────────────

    def establish_baseline(
        self,
        suite_name: str,
        score: float,
        established_by: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Baseline:
        """Establish or update baseline for a suite."""
        baseline = Baseline(
            suite_name=suite_name,
            score=max(0.0, min(1.0, score)),
            established_at=time.time(),
            established_by=established_by,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._baselines[suite_name] = baseline
            self._save_baselines()
        
        logger.info("Established baseline for '%s': %.3f by %s", suite_name, score, established_by)
        return baseline

    def get_baseline(self, suite_name: str) -> Optional[Baseline]:
        """Get baseline for a suite."""
        return self._baselines.get(suite_name)

    def auto_baseline_from_runs(
        self,
        suite_name: str,
        min_runs: int = 3,
        percentile: float = 0.5,
        established_by: str = "auto",
    ) -> Optional[Baseline]:
        """Establish baseline from historical runs (median by default)."""
        scores = self.get_scores(suite_name, limit=20)
        if len(scores) < min_runs:
            logger.warning(
                "Cannot auto-baseline '%s': only %d runs, need %d",
                suite_name, len(scores), min_runs
            )
            return None
        
        sorted_scores = sorted(s["score"] for s in scores)
        idx = int(len(sorted_scores) * percentile)
        baseline_score = sorted_scores[min(idx, len(sorted_scores) - 1)]
        
        return self.establish_baseline(suite_name, baseline_score, established_by)

    # ── Delta Detection ───────────────────────────────────────────────────────

    def get_delta(self, suite_name: str, limit: int = 1) -> Optional[DeltaResult]:
        """Get delta between latest score and baseline."""
        baseline = self._baselines.get(suite_name)
        scores = self.get_scores(suite_name, limit=limit)
        
        if not scores:
            return None
        
        current_score = scores[0]["score"]
        
        if baseline is None:
            return DeltaResult(
                suite_name=suite_name,
                current_score=current_score,
                baseline_score=0.0,
                absolute_delta=0.0,
                relative_delta=0.0,
                regression_detected=False,
                status=RegressionStatus.INSUFFICIENT_DATA,
                runs_since_baseline=len(scores),
            )
        
        abs_delta = current_score - baseline.score
        rel_delta = abs_delta / baseline.score if baseline.score > 0 else 0.0
        regression = abs_delta < -self._regression_threshold
        
        status = RegressionStatus.REGRESSION if regression else (
            RegressionStatus.IMPROVEMENT if abs_delta > self._regression_threshold
            else RegressionStatus.PASS
        )
        
        return DeltaResult(
            suite_name=suite_name,
            current_score=current_score,
            baseline_score=baseline.score,
            absolute_delta=abs_delta,
            relative_delta=rel_delta,
            regression_detected=regression,
            status=status,
            runs_since_baseline=len(scores),
        )

    def check_regression_gates(
        self,
        suite_names: Optional[List[str]] = None,
    ) -> Dict[str, DeltaResult]:
        """Check regression gates for all suites, return dict of results."""
        suites = suite_names or list(self._baselines.keys())
        results = {}
        
        for suite_name in suites:
            delta = self.get_delta(suite_name)
            if delta:
                results[suite_name] = delta
        
        return results

    # ── Querying ──────────────────────────────────────────────────────────────

    def get_scores(
        self,
        suite_name: str,
        limit: int = 10,
        since: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent scores for a suite."""
        hist_file = self._history_dir / f"{suite_name}.jsonl"
        
        if not self._results_file.exists():
            return []
        
        scores = []
        try:
            with open(self._results_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if record.get("suite_name") == suite_name:
                        if since is None or record.get("timestamp", 0) >= since:
                            scores.append(record)
            
            # Also read dedicated history file if exists
            if hist_file.exists():
                with open(hist_file) as f:
                    for line in f:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        if record.get("suite_name") == suite_name:
                            if since is None or record.get("timestamp", 0) >= since:
                                scores.append(record)
            
            scores.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return scores[:limit]
        except Exception as exc:
            logger.warning("Failed to get scores for '%s': %s", suite_name, exc)
            return []

    def get_trend(
        self,
        suite_name: str,
        last_n: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """Calculate trend over last N runs."""
        scores = self.get_scores(suite_name, limit=last_n)
        if len(scores) < 2:
            return None
        
        values = [s["score"] for s in scores]
        import statistics
        return {
            "suite_name": suite_name,
            "run_count": len(values),
            "latest": values[0],
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "delta_from_first": values[0] - values[-1],
        }

    def get_summary(self) -> RegistrySummary:
        """Get summary of all tracked suites."""
        suite_names = list(set(
            r.get("suite_name") 
            for r in self._read_all_results() 
            if r.get("suite_name")
        ))
        
        latest_scores = {}
        regression_alerts = []
        improvements = []
        
        for suite_name in suite_names:
            delta = self.get_delta(suite_name)
            if delta:
                latest_scores[suite_name] = delta.current_score
                if delta.status == RegressionStatus.REGRESSION:
                    regression_alerts.append(delta)
                elif delta.status == RegressionStatus.IMPROVEMENT:
                    improvements.append(delta)
        
        return RegistrySummary(
            suite_names=suite_names,
            total_runs=len(self._read_all_results()),
            latest_scores=latest_scores,
            regression_alerts=regression_alerts,
            improvements=improvements,
        )

    def _read_all_results(self) -> List[Dict[str, Any]]:
        """Read all results from JSONL file."""
        if not self._results_file.exists():
            return []
        
        results = []
        try:
            with open(self._results_file) as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
        except Exception as exc:
            logger.warning("Failed to read results: %s", exc)
        return results

    # ── Gate Enforcement ──────────────────────────────────────────────────────

    def enforce_regression_gate(
        self,
        suite_name: str,
        raise_on_regression: bool = True,
    ) -> bool:
        """
        Enforce regression gate for a suite.
        
        Returns True if gate passes (no regression), False otherwise.
        Raises RegressionError if raise_on_regression=True and regression detected.
        """
        delta = self.get_delta(suite_name)
        
        if delta is None:
            logger.warning("No delta available for '%s' - skipping gate", suite_name)
            return True
        
        if delta.regression_detected:
            msg = (
                f"REGRESSION DETECTED in '{suite_name}': "
                f"score dropped {delta.absolute_delta:.3f} "
                f"({delta.current_score:.3f} vs baseline {delta.baseline_score:.3f})"
            )
            logger.error(msg)
            if raise_on_regression:
                raise RegressionError(msg)
            return False
        
        logger.info("Regression gate passed for '%s' (score: %.3f)", suite_name, delta.current_score)
        return True

    def enforce_all_gates(
        self,
        suite_names: Optional[List[str]] = None,
        raise_on_regression: bool = True,
    ) -> Dict[str, bool]:
        """
        Enforce regression gates for multiple suites.
        
        Returns dict mapping suite_name to pass/fail.
        Raises RegressionError if any gate fails and raise_on_regression=True.
        """
        results = {}
        failures = []
        
        for suite_name, delta in self.check_regression_gates(suite_names).items():
            passed = not delta.regression_detected
            results[suite_name] = passed
            if not passed:
                failures.append(delta)
        
        if failures and raise_on_regression:
            msgs = "\n".join(
                f"  - {d.suite_name}: {d.current_score:.3f} (baseline: {d.baseline_score:.3f})"
                for d in failures
            )
            raise RegressionError(f"Regression gates failed:\n{msgs}")
        
        return results

    # ── Export ────────────────────────────────────────────────────────────────

    def export_summary(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """Export summary as JSON."""
        summary = self.get_summary()
        data = {
            "timestamp": time.time(),
            "suites": list(summary.suite_names),
            "total_runs": summary.total_runs,
            "latest_scores": summary.latest_scores,
            "regression_alerts": [asdict(d) for d in summary.regression_alerts],
            "improvements": [asdict(d) for d in summary.improvements],
            "baselines": {
                name: b.to_dict() for name, b in self._baselines.items()
            },
        }
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(data, indent=2))
        
        return data

    def import_baselines(self, data: Dict[str, Any]) -> None:
        """Import baselines from dict."""
        for suite_name, baseline_data in data.items():
            baseline = Baseline(**baseline_data)
            self._baselines[suite_name] = baseline
        self._save_baselines()


# ── Exceptions ────────────────────────────────────────────────────────────────

class RegressionError(Exception):
    """Raised when a regression gate fails."""
    pass


# ── Convenience Factory ───────────────────────────────────────────────────────

_registry: Optional[ScoreRegistry] = None
_registry_lock = threading.Lock()


def get_registry(
    base_dir: Optional[Path] = None,
    regression_threshold: float = REGRESSION_THRESHOLD_DEFAULT,
) -> ScoreRegistry:
    """Get singleton registry instance."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ScoreRegistry(
                    base_dir=base_dir,
                    regression_threshold=regression_threshold,
                )
    return _registry


def reset_registry() -> None:
    """Reset singleton (useful for testing)."""
    global _registry
    _registry = None
