"""
BRP — Behavioral Response Protocol package.

BRP is the SIMP security detection and benchmarking stack.
It provides threat detection, pattern recognition, quantum advisory,
and telemetry ingestion for real-time and offline analysis.
"""

from __future__ import annotations

from .detection_benchmark import (
    AttackScenario,
    AttackType,
    BenchmarkResult,
    DetectionBenchmark,
    ScenarioResult,
    get_all_scenarios,
)

from .quantum_lift_measurement import (
    LiftMeasurement,
    QuantumLiftMeasurer,
    QuantumLiftResult,
)

from .telemetry_ingest import (
    TelemetrySample,
    TelemetryDatasetBuilder,
)

__all__ = [
    # Detection benchmark
    "AttackScenario",
    "AttackType",
    "BenchmarkResult",
    "DetectionBenchmark",
    "ScenarioResult",
    "get_all_scenarios",
    # Quantum lift
    "LiftMeasurement",
    "QuantumLiftMeasurer",
    "QuantumLiftResult",
    # Telemetry ingestion
    "TelemetrySample",
    "TelemetryDatasetBuilder",
]
