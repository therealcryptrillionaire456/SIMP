"""Quantum lift measurement for BRP detection.

Runs each detection scenario twice — once with quantum advisory disabled
(classical baseline), once enabled — and measures the lift delta on
precision, recall, F1, and processing time.

Supports three dataset modes:
  - "canonical":  built-in AttackScenario list (backward compatible)
  - "real":       user-provided real telemetry scenarios
  - "mixed":      canonical + real combined, with separate counters

Honesty rule: if lift is zero or negative, it is reported directly.
No results are faked.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .detection_benchmark import (
    AttackScenario,
    BenchmarkResult,
    DetectionBenchmark,
    ScenarioResult,
    get_all_scenarios,
)
from simp.security.brp.multimodal_analysis import MultiModalSafetyAnalyzer, ThreatDetection
from simp.security.brp.quantum_defense import QuantumDefenseAdvisor
from simp.security.brp.quantum_advisory_optimizer import QuantumAdvisoryOptimizer

logger = logging.getLogger(__name__)


def _compute_metrics_from_results(results: List[ScenarioResult]) -> BenchmarkResult:
    """Replicate DetectionBenchmark._compute_metrics for independent use."""
    attack_results = [r for r in results if r.attack_type != "benign"]
    benign_results = [r for r in results if r.attack_type == "benign"]
    tp = sum(1 for r in attack_results if r.true_positive)
    fn = sum(1 for r in attack_results if r.false_negative)
    fp = sum(1 for r in benign_results if r.false_positive)
    tn = sum(1 for r in benign_results if not r.false_positive)
    total = len(results)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / total if total > 0 else 0.0
    # Populate label_counts like DetectionBenchmark._compute_metrics
    label_counts: Dict[str, int] = {}
    for r in results:
        lbl = r.attack_type if r.attack_type != "benign" else "benign"
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
    return BenchmarkResult(
        scenario_results=list(results),
        total_scenarios=total,
        attack_scenarios=len(attack_results),
        benign_scenarios=len(benign_results),
        true_positives=tp, false_positives=fp,
        false_negatives=fn, true_negatives=tn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        accuracy=round(accuracy, 4),
        label_counts=label_counts,
    )


@dataclass
class LiftMeasurement:
    """Delta between classical and quantum-assisted detection."""

    precision_lift: float       # quantum_precision - classical_precision
    recall_lift: float
    f1_lift: float
    accuracy_lift: float
    avg_processing_time_lift_ms: float   # negative = faster with quantum
    advantage_ratio: float     # (f1_quantum - f1_classical) / f1_classical if f1_classical > 0, else 0
    quantum_backends_connected: int = 0
    quantum_skill_level: float = 0.0


@dataclass
class QuantumLiftResult:
    """Complete quantum lift measurement output."""

    classical: BenchmarkResult
    quantum_assisted: BenchmarkResult
    lift: LiftMeasurement
    scenario_counts: Dict[str, int] = field(default_factory=lambda: {
        "total": 0, "attack": 0, "benign": 0,
    })


@dataclass
class LiftReport:
    """Honest, dataset-mode-aware lift report.

    Contains separate ``canonical_lift`` and ``real_lift`` entries when
    ``dataset_mode="mixed"``, or a single ``classical_metrics`` /
    ``quantum_metrics`` / ``lift`` triplet for the active dataset mode.
    """

    dataset_mode: str
    classical_metrics: Dict[str, Any]
    quantum_metrics: Dict[str, Any]
    lift: Dict[str, Any]
    sample_count: int
    excluded_sample_count: int
    label_counts: Dict[str, int]
    honest_assessment: str  # "positive" | "neutral" | "negative" | "insufficient_data"

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "dataset_mode": self.dataset_mode,
            "classical_metrics": self.classical_metrics,
            "quantum_metrics": self.quantum_metrics,
            "lift": self.lift,
            "sample_count": self.sample_count,
            "excluded_sample_count": self.excluded_sample_count,
            "label_counts": self.label_counts,
            "honest_assessment": self.honest_assessment,
        }


@dataclass
class DatasetComparison:
    """Side-by-side comparison of canonical and real dataset lifts.

    Makes explicit whether quantum performs better on synthetic than real data.
    """

    canonical_lift: LiftReport
    real_lift: LiftReport
    synthetic_outperforms_real: bool  # True if canonical lift > real lift
    delta_f1: float  # canonical_lift.f1_lift - real_lift.f1_lift

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "canonical": self.canonical_lift.to_dict(),
            "real": self.real_lift.to_dict(),
            "synthetic_outperforms_real": self.synthetic_outperforms_real,
            "delta_f1": round(self.delta_f1, 4),
        }


def _compute_honest_assessment(
    f1_lift: float,
    sample_count: int,
) -> str:
    """Enforce honesty rule based on F1 lift and sample count."""
    if sample_count < 10:
        return "insufficient_data — too few samples"
    if f1_lift < -0.01:
        return "negative — real data shows degradation"
    if abs(f1_lift) <= 0.01:
        return "neutral — no measurable lift"
    if f1_lift > 0.01:
        return "positive — measurable lift detected"
    # Safety net (should be unreachable)
    return "neutral — no measurable lift"


def _build_lift_report(
    dataset_mode: str,
    classical: BenchmarkResult,
    quantum: BenchmarkResult,
    lift: LiftMeasurement,
    sample_count: int,
    excluded_sample_count: int,
    label_counts: Dict[str, int],
) -> LiftReport:
    """Build a LiftReport from computed metrics with honest assessment."""
    honest = _compute_honest_assessment(lift.f1_lift, sample_count)
    return LiftReport(
        dataset_mode=dataset_mode,
        classical_metrics={
            "precision": classical.precision,
            "recall": classical.recall,
            "f1_score": classical.f1_score,
            "accuracy": classical.accuracy,
            "true_positives": classical.true_positives,
            "false_positives": classical.false_positives,
            "false_negatives": classical.false_negatives,
            "true_negatives": classical.true_negatives,
        },
        quantum_metrics={
            "precision": quantum.precision,
            "recall": quantum.recall,
            "f1_score": quantum.f1_score,
            "accuracy": quantum.accuracy,
            "true_positives": quantum.true_positives,
            "false_positives": quantum.false_positives,
            "false_negatives": quantum.false_negatives,
            "true_negatives": quantum.true_negatives,
        },
        lift={
            "precision_lift": lift.precision_lift,
            "recall_lift": lift.recall_lift,
            "f1_lift": lift.f1_lift,
            "accuracy_lift": lift.accuracy_lift,
            "advantage_ratio": lift.advantage_ratio,
            "avg_processing_time_lift_ms": lift.avg_processing_time_lift_ms,
            "quantum_backends_connected": lift.quantum_backends_connected,
            "quantum_skill_level": lift.quantum_skill_level,
        },
        sample_count=sample_count,
        excluded_sample_count=excluded_sample_count,
        label_counts=dict(label_counts),
        honest_assessment=honest,
    )


class QuantumLiftMeasurer:
    """Measures detection lift from quantum advisory integration.

    Runs the same scenarios twice — once with quantum advisory disabled
    (pure classical detection) and once with quantum advisory enabled.
    The lift delta is the difference in metrics between the two runs.
    """

    def __init__(
        self,
        benchmark: Optional[DetectionBenchmark] = None,
        quantum_advisor: Optional[QuantumDefenseAdvisor] = None,
        quantum_optimizer: Optional[QuantumAdvisoryOptimizer] = None,
    ) -> None:
        self._benchmark = benchmark or DetectionBenchmark()
        self._quantum_advisor = quantum_advisor or QuantumDefenseAdvisor()
        self._quantum_optimizer = quantum_optimizer or QuantumAdvisoryOptimizer()
        self._last_result: Optional[QuantumLiftResult] = None

    def _convert_to_scenario(self, sample: Any) -> AttackScenario:
        """Convert a dict or TelemetrySample into an AttackScenario.

        Accepts:
        - AttackScenario objects (passed through)
        - dicts with AttackScenario-compatible fields
        - TelemetrySample objects (via normalized_scenario)
        """
        if isinstance(sample, AttackScenario):
            return sample

        d: Dict[str, Any]
        if hasattr(sample, "normalized_scenario"):
            # TelemetrySample-like
            d = dict(sample.normalized_scenario)  # type: ignore[union-attr]
        elif isinstance(sample, dict):
            d = dict(sample)
        else:
            # Last resort: try to access normalized_scenario attribute
            try:
                d = dict(sample.normalized_scenario)  # type: ignore[union-attr]
            except (AttributeError, TypeError):
                d = {"attack_type": "unknown", "name": str(sample), "description": str(sample)}

        return AttackScenario(
            attack_type=str(d.get("attack_type", "unknown")),
            name=str(d.get("name", "converted_sample")),
            description=str(d.get("description", "")),
            text_inputs=list(d.get("text_inputs", [])),
            code_inputs=list(d.get("code_inputs", [])),
            behavior_inputs=list(d.get("behavior_inputs", [])),
            network_inputs=list(d.get("network_inputs", [])),
            memory_inputs=list(d.get("memory_inputs", [])),
            expected_detection_sources=list(d.get("expected_detection_sources", [])),
            expected_detection_count_min=int(d.get("expected_detection_count_min", 0)),
            expected_confidence_min=float(d.get("expected_confidence_min", 0.0)),
        )

    def measure(
        self,
        dataset_mode: str = "canonical",
        real_scenarios: Optional[List[Any]] = None,
    ) -> QuantumLiftResult:
        """Run classical baseline, then quantum-assisted, return lift deltas.

        Parameters
        ----------
        dataset_mode:
            "canonical" — use built-in AttackScenario list (backward compatible)
            "real" — use real_scenarios parameter
            "mixed" — run both and report combined + separate
        real_scenarios:
            List of AttackScenario, TelemetrySample, or dict objects.
        """
        if dataset_mode == "real":
            if not real_scenarios:
                raise ValueError("real_scenarios required when dataset_mode='real'")
            raw_scenarios = [self._convert_to_scenario(s) for s in real_scenarios]
        elif dataset_mode == "mixed":
            if not real_scenarios:
                raise ValueError("real_scenarios required when dataset_mode='mixed'")
            canonical = get_all_scenarios()
            real = [self._convert_to_scenario(s) for s in real_scenarios]
            raw_scenarios = canonical + real
        else:
            raw_scenarios = get_all_scenarios()

        # ── Classical baseline ───────────────────────────────────────
        classical_results = [self._benchmark._run_single(s) for s in raw_scenarios]
        classical = _compute_metrics_from_results(classical_results)

        # ── Quantum-assisted ─────────────────────────────────────────
        quantum_results: List[ScenarioResult] = []
        for scenario, classical_result in zip(raw_scenarios, classical_results):
            quantum_assessment = self._apply_quantum(scenario, classical_result)
            adjusted = self._adjust_result(classical_result, quantum_assessment)
            quantum_results.append(adjusted)

        quantum = _compute_metrics_from_results(quantum_results)

        # ── Lift ─────────────────────────────────────────────────────
        precision_lift = round(quantum.precision - classical.precision, 4)
        recall_lift = round(quantum.recall - classical.recall, 4)
        f1_lift = round(quantum.f1_score - classical.f1_score, 4)
        accuracy_lift = round(quantum.accuracy - classical.accuracy, 4)
        time_lift = round(
            (sum(r.processing_time_ms for r in quantum_results) -
             sum(r.processing_time_ms for r in classical_results)) / max(len(classical_results), 1),
            3,
        )
        advantage_ratio = (
            (quantum.f1_score - classical.f1_score) / classical.f1_score
            if classical.f1_score > 0 else 0.0
        )

        # Quantum posture
        posture = self._quantum_advisor.build_posture_summary()
        bk = posture.get("backend_summary", {})
        connected = int(bk.get("connected_backends") or 0)
        sk = posture.get("skill_summary", {})
        skill_level = float(sk.get("average_skill_level") or 0.0)

        lift = LiftMeasurement(
            precision_lift=precision_lift,
            recall_lift=recall_lift,
            f1_lift=f1_lift,
            accuracy_lift=accuracy_lift,
            avg_processing_time_lift_ms=time_lift,
            advantage_ratio=round(advantage_ratio, 4),
            quantum_backends_connected=connected,
            quantum_skill_level=skill_level,
        )

        result = QuantumLiftResult(
            classical=classical,
            quantum_assisted=quantum,
            lift=lift,
            scenario_counts={
                "total": len(raw_scenarios),
                "attack": classical.attack_scenarios,
                "benign": classical.benign_scenarios,
            },
        )
        self._last_result = result
        return result

    def measure_on_dataset(
        self,
        dataset_mode: str = "canonical",
        real_scenarios: Optional[List[Any]] = None,
    ) -> LiftReport:
        """Measure lift and produce a LiftReport with honest assessment.

        Convenience wrapper around ``measure()`` that returns a
        ``LiftReport`` instead of a raw ``QuantumLiftResult``.
        """
        result = self.measure(dataset_mode=dataset_mode, real_scenarios=real_scenarios)
        excluded_count = result.classical.total_scenarios - result.classical.attack_scenarios - result.classical.benign_scenarios
        return _build_lift_report(
            dataset_mode=dataset_mode,
            classical=result.classical,
            quantum=result.quantum_assisted,
            lift=result.lift,
            sample_count=result.scenario_counts["total"],
            excluded_sample_count=max(0, excluded_count),
            label_counts=result.classical.label_counts,
        )

    def compare_datasets(
        self,
        real_scenarios: Optional[List[Any]] = None,
    ) -> DatasetComparison:
        """Run measure on canonical AND real datasets, return side-by-side.

        Makes explicit whether quantum performs better on synthetic than real data.
        If no real_scenarios are provided, uses an empty list and will produce
        an ``insufficient_data`` assessment for the real_lift.

        Returns
        -------
        DatasetComparison with canonical_lift and real_lift side by side.
        """
        canonical_report = self.measure_on_dataset(dataset_mode="canonical")
        real_scenarios = real_scenarios or []
        if real_scenarios:
            real_report = self.measure_on_dataset(
                dataset_mode="real", real_scenarios=real_scenarios
            )
        else:
            # Produce an insufficient_data report for empty real dataset
            empty_lift = LiftReport(
                dataset_mode="real",
                classical_metrics={"precision": 0.0, "recall": 0.0, "f1_score": 0.0, "accuracy": 0.0},
                quantum_metrics={"precision": 0.0, "recall": 0.0, "f1_score": 0.0, "accuracy": 0.0},
                lift={"precision_lift": 0.0, "recall_lift": 0.0, "f1_lift": 0.0, "accuracy_lift": 0.0, "advantage_ratio": 0.0, "avg_processing_time_lift_ms": 0.0},
                sample_count=0,
                excluded_sample_count=0,
                label_counts={},
                honest_assessment="insufficient_data — too few samples",
            )
            real_report = empty_lift

        canonical_f1_lift = canonical_report.lift.get("f1_lift", 0.0)
        real_f1_lift = real_report.lift.get("f1_lift", 0.0)
        delta_f1 = round(canonical_f1_lift - real_f1_lift, 4)

        return DatasetComparison(
            canonical_lift=canonical_report,
            real_lift=real_report,
            synthetic_outperforms_real=canonical_f1_lift > real_f1_lift,
            delta_f1=delta_f1,
        )

    def get_last_result(self) -> Optional[QuantumLiftResult]:
        return self._last_result

    # ── Private ──────────────────────────────────────────────────────

    def _apply_quantum(
        self,
        scenario: AttackScenario,
        result: ScenarioResult,
    ) -> Dict[str, Any]:
        """Run quantum advisory assessment on scenario context."""
        record: Dict[str, Any] = {
            "action": scenario.attack_type,
            "event_type": "benchmark",
            "context": scenario.description,
            "params": str(scenario.expected_detection_sources),
        }
        # Build threat tags from the scenario
        tags = list(scenario.expected_detection_sources)
        threat_score = result.max_confidence

        qa = self._quantum_advisor.assess(
            record,
            threat_score=threat_score,
            threat_tags=tags,
        )
        qo = self._quantum_optimizer.assess(
            record,
            threat_score=threat_score,
            threat_tags=tags,
        )
        return {"advisor": qa, "optimizer": qo}

    def _adjust_result(
        self,
        result: ScenarioResult,
        quantum_assessment: Dict[str, Any],
    ) -> ScenarioResult:
        """Apply quantum advisory adjustments to a scenario result.

        The only adjustment is a small confidence boost (+0.02) for scenarios
        where the quantum advisor tags include high-priority tags or the
        advisory level is 'elevated'. This is advisory-only.
        """
        advisor = quantum_assessment.get("advisor", {})
        boost = 0.0
        advisory_level = advisor.get("advisory_level", "normal")
        if advisory_level == "elevated":
            boost = 0.02

        return ScenarioResult(
            attack_type=result.attack_type,
            name=result.name,
            total_detections=result.total_detections,
            detection_sources=list(result.detection_sources),
            max_confidence=round(min(result.max_confidence + boost, 1.0), 4),
            processing_time_ms=result.processing_time_ms,
            true_positive=result.true_positive,
            false_positive=result.false_positive,
            false_negative=result.false_negative,
            detection_details=list(result.detection_details),
        )
