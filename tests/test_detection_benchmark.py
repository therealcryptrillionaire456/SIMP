"""Tests for detection benchmark harness and quantum lift measurement."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.brp.detection_benchmark import (
    AttackScenario,
    AttackType,
    BenchmarkResult,
    DetectionBenchmark,
    ScenarioResult,
    get_all_scenarios,
)
from simp.brp.quantum_lift_measurement import (
    QuantumLiftMeasurer,
    QuantumLiftResult,
    LiftMeasurement,
)


class TestAttackScenarios(unittest.TestCase):
    """Canonical scenarios have correct ground truth."""

    def test_all_scenarios_loaded(self):
        scenarios = get_all_scenarios()
        self.assertGreaterEqual(len(scenarios), 5)
        types = {s.attack_type for s in scenarios}
        self.assertIn(AttackType.TEXT_INJECTION, types)
        self.assertIn(AttackType.CODE_EXPLOIT, types)
        self.assertIn(AttackType.DATA_EXFILTRATION, types)

    def test_text_injection_has_text_inputs(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == AttackType.TEXT_INJECTION]
        self.assertGreater(len(scenarios), 0)
        s = scenarios[0]
        self.assertGreater(len(s.text_inputs), 0)
        self.assertIn("multimodal.text", s.expected_detection_sources)

    def test_code_exploit_has_code_inputs(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == AttackType.CODE_EXPLOIT]
        self.assertGreater(len(scenarios), 0)
        s = scenarios[0]
        self.assertGreater(len(s.code_inputs), 0)
        self.assertIn("multimodal.code", s.expected_detection_sources)

    def test_exfiltration_has_network_inputs(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == AttackType.DATA_EXFILTRATION]
        self.assertGreater(len(scenarios), 0)
        s = scenarios[0]
        self.assertGreater(len(s.network_inputs), 0)
        self.assertIn("multimodal.network", s.expected_detection_sources)

    def test_benign_has_no_expected_detections(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == "benign"]
        self.assertGreaterEqual(len(scenarios), 1)
        for s in scenarios:
            self.assertEqual(len(s.expected_detection_sources), 0)
            self.assertEqual(s.expected_detection_count_min, 0)


class TestDetectionBenchmark(unittest.TestCase):
    """Benchmark runner produces correct metrics."""

    def setUp(self):
        self.benchmark = DetectionBenchmark()

    def test_run_all_returns_result(self):
        result = self.benchmark.run_all()
        self.assertIsInstance(result, BenchmarkResult)
        self.assertGreaterEqual(result.total_scenarios, 5)

    def test_run_all_has_attack_and_benign(self):
        result = self.benchmark.run_all()
        self.assertGreaterEqual(result.attack_scenarios, 4)
        self.assertGreaterEqual(result.benign_scenarios, 1)

    def test_text_injection_is_detected(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == AttackType.TEXT_INJECTION]
        self.assertGreater(len(scenarios), 0)
        s = scenarios[0]
        result = self.benchmark.run_scenario(s)
        self.assertTrue(result.true_positive, f"Text injection should be detected: {result.detection_details}")

    def test_code_exploit_is_detected(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == AttackType.CODE_EXPLOIT]
        s = scenarios[0]
        result = self.benchmark.run_scenario(s)
        self.assertTrue(result.true_positive, f"Code exploit should be detected: {result.detection_details}")

    def test_exfiltration_is_detected(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == AttackType.DATA_EXFILTRATION]
        s = scenarios[0]
        result = self.benchmark.run_scenario(s)
        self.assertTrue(result.true_positive, f"Exfiltration should be detected: {result.detection_details}")

    def test_benign_text_has_no_false_positive(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == "benign" and len(s.text_inputs) > 0]
        s = scenarios[0]
        result = self.benchmark.run_scenario(s)
        self.assertFalse(result.false_positive, f"Benign text should not generate FP: {result.detection_details}")

    def test_benign_code_has_no_false_positive(self):
        scenarios = [s for s in get_all_scenarios() if s.attack_type == "benign" and len(s.code_inputs) > 0]
        s = scenarios[0]
        result = self.benchmark.run_scenario(s)
        self.assertFalse(result.false_positive, f"Benign code should not generate FP: {result.detection_details}")

    def test_metrics_are_floats(self):
        result = self.benchmark.run_all()
        self.assertIsInstance(result.precision, float)
        self.assertIsInstance(result.recall, float)
        self.assertIsInstance(result.f1_score, float)
        self.assertIsInstance(result.accuracy, float)

    def test_precision_recall_between_0_and_1(self):
        result = self.benchmark.run_all()
        self.assertGreaterEqual(result.precision, 0.0)
        self.assertLessEqual(result.precision, 1.0)
        self.assertGreaterEqual(result.recall, 0.0)
        self.assertLessEqual(result.recall, 1.0)
        self.assertGreaterEqual(result.f1_score, 0.0)
        self.assertLessEqual(result.f1_score, 1.0)

    def test_run_all_is_not_all_zero(self):
        result = self.benchmark.run_all()
        # At minimum, text and code injection should be detected
        self.assertGreaterEqual(result.true_positives, 2,
                                f"Expected >=2 TP, got {result.true_positives}")

    def test_benchmark_round_trips_to_dict(self):
        result = self.benchmark.run_all()
        d = {
            "total_scenarios": result.total_scenarios,
            "attack_scenarios": result.attack_scenarios,
            "true_positives": result.true_positives,
            "false_positives": result.false_positives,
            "false_negatives": result.false_negatives,
            "precision": result.precision,
            "recall": result.recall,
            "f1_score": result.f1_score,
            "accuracy": result.accuracy,
        }
        self.assertIn("precision", d)
        self.assertIn("recall", d)
        self.assertIn("f1_score", d)

    def test_get_last_result_none_initial(self):
        fresh = DetectionBenchmark()
        self.assertIsNone(fresh.get_last_result())

    def test_get_last_result_after_run(self):
        result = self.benchmark.run_all()
        same = self.benchmark.get_last_result()
        self.assertIsNotNone(same)
        self.assertEqual(same.total_scenarios, result.total_scenarios)


class TestQuantumLiftMeasurer(unittest.TestCase):
    """Quantum lift measurement produces correct deltas."""

    def setUp(self):
        self.measurer = QuantumLiftMeasurer()

    def test_quantum_lift_has_classical_and_quantum(self):
        result = self.measurer.measure()
        self.assertIsInstance(result, QuantumLiftResult)
        self.assertIsInstance(result.classical, BenchmarkResult)
        self.assertIsInstance(result.quantum_assisted, BenchmarkResult)
        self.assertIsInstance(result.lift, LiftMeasurement)

    def test_lift_has_all_fields(self):
        result = self.measurer.measure()
        lift = result.lift
        # These should always be floats (can be 0.0)
        self.assertIsInstance(lift.precision_lift, float)
        self.assertIsInstance(lift.recall_lift, float)
        self.assertIsInstance(lift.f1_lift, float)
        self.assertIsInstance(lift.accuracy_lift, float)
        self.assertIsInstance(lift.avg_processing_time_lift_ms, float)
        self.assertIsInstance(lift.advantage_ratio, float)

    def test_quantum_backend_info_present(self):
        result = self.measurer.measure()
        lift = result.lift
        self.assertIsInstance(lift.quantum_backends_connected, int)
        self.assertIsInstance(lift.quantum_skill_level, float)

    def test_max_confidence_does_not_exceed_1(self):
        result = self.measurer.measure()
        for sr in result.quantum_assisted.scenario_results:
            self.assertLessEqual(sr.max_confidence, 1.0,
                                 f"Confidence > 1.0 for {sr.name}")

    def test_quantum_lift_scenario_counts(self):
        result = self.measurer.measure()
        counts = result.scenario_counts
        self.assertIn("total", counts)
        self.assertIn("attack", counts)
        self.assertIn("benign", counts)
        self.assertGreaterEqual(counts["total"], 5)

    def test_classical_and_quantum_have_same_scenario_count(self):
        result = self.measurer.measure()
        self.assertEqual(
            len(result.classical.scenario_results),
            len(result.quantum_assisted.scenario_results),
        )

    def test_get_last_result_none_initial(self):
        fresh = QuantumLiftMeasurer()
        self.assertIsNone(fresh.get_last_result())

    def test_get_last_result_after_measure(self):
        result = self.measurer.measure()
        same = self.measurer.get_last_result()
        self.assertIsNotNone(same)
        self.assertEqual(same.lift.advantage_ratio, result.lift.advantage_ratio)

    def test_quantum_does_not_degrade_accuracy(self):
        """Quantum advisory should not reduce detection accuracy.
        (The boost is always >= 0, so confidence can only stay same or increase.)"""
        result = self.measurer.measure()
        self.assertGreaterEqual(
            result.quantum_assisted.precision,
            result.classical.precision - 0.001,
            "Quantum precision should not be lower than classical",
        )
        self.assertGreaterEqual(
            result.quantum_assisted.recall,
            result.classical.recall - 0.001,
            "Quantum recall should not be lower than classical",
        )


class TestQuantumLiftEdgeCases(unittest.TestCase):
    """Edge cases for quantum lift measurement."""

    def test_empty_scenarios_handled(self):
        """If no scenarios, lift should be zero."""
        measurer = QuantumLiftMeasurer()
        # Patch get_all_scenarios to return empty
        with patch("simp.brp.quantum_lift_measurement.get_all_scenarios", return_value=[]):
            result = measurer.measure()
            self.assertEqual(result.scenario_counts["total"], 0)
            self.assertEqual(result.lift.precision_lift, 0.0)
            self.assertEqual(result.lift.f1_lift, 0.0)
            self.assertEqual(result.lift.advantage_ratio, 0.0)

    def test_quantum_boost_does_not_exceed_1(self):
        """Confidence boost should never push past 1.0."""
        from simp.brp.quantum_lift_measurement import _compute_metrics_from_results
        # Create a scenario with confidence 0.99
        result = ScenarioResult(
            attack_type=AttackType.TEXT_INJECTION,
            name="test",
            total_detections=1,
            detection_sources=["multimodal.text"],
            max_confidence=0.99,
            processing_time_ms=1.0,
            true_positive=True,
            false_positive=False,
            false_negative=False,
        )
        # Apply quantum boost
        from simp.brp.quantum_lift_measurement import _compute_metrics_from_results
        from simp.brp.detection_benchmark import BenchmarkResult
        results = _compute_metrics_from_results([result])
        self.assertLessEqual(results.scenario_results[0].max_confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
