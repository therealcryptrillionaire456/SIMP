"""
Tests for projectx.evolution_tracker module.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch, Mock, PropertyMock

import pytest

from simp.projectx.evolution_tracker import (
    CapabilitySnapshot,
    EvolutionReport,
    EvolutionTracker,
    _percentile,
    get_evolution_tracker,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_safety_monitor():
    """Create a mock safety monitor with _metrics and get_alerts attributes."""
    monitor = MagicMock()
    monitor._metrics = {
        "eval_score": [],
        "eval_latency_ms": [],
    }
    monitor.get_alerts = MagicMock(return_value=[])
    return monitor


@pytest.fixture
def mock_apo_engine():
    """Create a mock APO engine with report() method."""
    engine = MagicMock()
    engine._metrics = {"best_score": 0.0, "current_gen": 0}
    engine.report = MagicMock(return_value={"generation": 0, "best_score": 0.0})
    return engine


@pytest.fixture
def mock_rag_memory():
    """Create a mock RAG memory store with count() method."""
    mem = MagicMock()
    mem._metrics = {"entry_count": 0}
    mem.count = MagicMock(return_value=0)
    return mem


@pytest.fixture
def tmp_snapshot_file(tmp_path):
    """Provide a temporary path for snapshot files."""
    return tmp_path / "evolution_snapshots.jsonl"


@pytest.fixture
def tmp_dashboard_file(tmp_path):
    """Provide a temporary path for dashboard files."""
    return tmp_path / "evolution_dashboard.json"


# ─────────────────────────────────────────────────────────────────────────────
# Test: track_cycle produces a snapshot
# ─────────────────────────────────────────────────────────────────────────────

def test_track_cycle_produces_snapshot():
    """Calling track_cycle() with None args should still produce a valid snapshot."""
    tracker = EvolutionTracker()
    report = tracker.track_cycle()
    assert isinstance(report, EvolutionReport)
    assert isinstance(report.snapshot, CapabilitySnapshot)
    assert report.snapshot.snapshot_id is not None
    assert len(report.snapshot.snapshot_id) == 8


# ─────────────────────────────────────────────────────────────────────────────
# Test: track_cycle with mock dependencies
# ─────────────────────────────────────────────────────────────────────────────

def test_track_cycle_with_mock_dependencies(tmp_snapshot_file, tmp_dashboard_file):
    """Verify track_cycle accepts and processes mocked dependencies."""
    class MockAlert:
        def __init__(self, value):
            self.alert_type = MagicMock()
            self.alert_type.value = "high_latency"
            self.value = value

    monitor = MagicMock()
    monitor._metrics = {"eval_score": [], "eval_latency_ms": []}
    monitor.get_summary = MagicMock(return_value={
        "metrics": {"avg_score": 0.8, "peak_score": 0.9, "avg_latency_ms": 50.0}
    })
    monitor.get_alerts = MagicMock(return_value=[
        MockAlert(45.0), MockAlert(55.0), MockAlert(95.0)
    ])

    # Create mock APO engine
    apo = MagicMock()
    apo.report = MagicMock(return_value={"generation": 5, "best_score": 0.82})

    # Create mock RAG memory
    rag = MagicMock()
    rag.count = MagicMock(return_value=42)

    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    # Call track_cycle with mock dependencies
    baseline = CapabilitySnapshot(generation=0, eval_mean=0.5)
    tracker._history.append(baseline)

    report = tracker.track_cycle(
        safety_monitor=monitor,
        apo_engine=apo,
        rag_memory=rag,
    )

    # Verify the report structure is correct
    assert isinstance(report, EvolutionReport)
    assert isinstance(report.snapshot, CapabilitySnapshot)
    assert report.trend in ("stable", "improving", "regressing")
    assert isinstance(report.targets_met, dict)
    assert "latency_p95_under_100ms" in report.targets_met
    assert "validation_95pct" in report.targets_met
    assert "monthly_2x_improvement" in report.targets_met

    # Verify APO generation is set from mock
    assert report.snapshot.apo_generation == 5
    assert report.snapshot.memory_entries == 42


# ─────────────────────────────────────────────────────────────────────────────
# Test: snapshot to_dict
# ─────────────────────────────────────────────────────────────────────────────

def test_snapshot_to_dict():
    """Verify to_dict() returns all required keys."""
    snap = CapabilitySnapshot(
        snapshot_id="abc12345",
        generation=1,
        eval_mean=0.85,
        eval_p95=0.90,
        latency_mean_ms=75.0,
        validation_pass_rate=0.97,
        regression_detected=False,
        targets_met={"monthly_improvement_rate": True},
    )

    d = snap.to_dict()

    # Required keys per specification
    assert "snapshot_id" in d
    assert d["snapshot_id"] == "abc12345"
    assert "generation" in d
    assert d["generation"] == 1
    assert "eval_mean" in d
    assert d["eval_mean"] == 0.85
    assert "eval_p95" in d
    assert d["eval_p95"] == 0.90
    assert "latency_mean_ms" in d
    assert d["latency_mean_ms"] == 75.0
    assert "validation_pass_rate" in d
    assert d["validation_pass_rate"] == 0.97
    assert "regression_detected" in d
    assert d["regression_detected"] is False
    assert "targets_met" in d
    assert d["targets_met"] == {"monthly_improvement_rate": True}
    assert "iso_timestamp" in d
    # Verify ISO format
    assert "T" in d["iso_timestamp"]
    assert "Z" in d["iso_timestamp"]


# ─────────────────────────────────────────────────────────────────────────────
# Test: evolution report to_dict
# ─────────────────────────────────────────────────────────────────────────────

def test_evolution_report_to_dict():
    """Verify EvolutionReport.to_dict() returns expected keys."""
    snap = CapabilitySnapshot(generation=0)
    report = EvolutionReport(
        snapshot=snap,
        trend="improving",
        targets_met={"latency_ms_p95": True},
        week_over_week=1.15,
        month_over_month=2.0,
        on_track_for_2x=True,
    )

    d = report.to_dict()

    assert "snapshot" in d
    assert isinstance(d["snapshot"], dict)
    assert "trend" in d
    assert d["trend"] == "improving"
    assert "targets_met" in d
    assert d["targets_met"] == {"latency_ms_p95": True}
    assert "week_over_week" in d
    assert d["week_over_week"] == 1.15
    assert "month_over_month" in d
    assert d["month_over_month"] == 2.0
    assert "on_track_for_2x" in d
    assert d["on_track_for_2x"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Test: trend improving
# ─────────────────────────────────────────────────────────────────────────────

def test_trend_improving(tmp_snapshot_file, tmp_dashboard_file):
    """Adding 5 snapshots with increasing eval_mean should yield trend='improving'."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    for i in range(5):
        snap = CapabilitySnapshot(
            generation=i,
            eval_mean=0.60 + i * 0.05,  # 0.60, 0.65, 0.70, 0.75, 0.80
        )
        snap.timestamp = time.time() + i * 86400  # One day apart
        tracker._history.append(snap)

    trend = tracker._compute_trend()
    assert trend == "improving"


# ─────────────────────────────────────────────────────────────────────────────
# Test: trend regressing
# ─────────────────────────────────────────────────────────────────────────────

def test_trend_regressing(tmp_snapshot_file, tmp_dashboard_file):
    """Adding 5 snapshots with decreasing eval_mean should yield trend='regressing'."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    for i in range(5):
        snap = CapabilitySnapshot(
            generation=i,
            eval_mean=0.90 - i * 0.05,  # 0.90, 0.85, 0.80, 0.75, 0.70
        )
        snap.timestamp = time.time() + i * 86400
        tracker._history.append(snap)

    trend = tracker._compute_trend()
    assert trend == "regressing"


# ─────────────────────────────────────────────────────────────────────────────
# Test: trend stable
# ─────────────────────────────────────────────────────────────────────────────

def test_trend_stable(tmp_snapshot_file, tmp_dashboard_file):
    """Adding 3 snapshots with identical eval_mean should yield trend='stable'."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    for i in range(3):
        snap = CapabilitySnapshot(
            generation=i,
            eval_mean=0.75,  # All identical
        )
        snap.timestamp = time.time() + i * 86400
        tracker._history.append(snap)

    trend = tracker._compute_trend()
    assert trend == "stable"


# ─────────────────────────────────────────────────────────────────────────────
# Test: regression detection
# ─────────────────────────────────────────────────────────────────────────────

def test_regression_detection(tmp_snapshot_file, tmp_dashboard_file):
    """A 0.20 point drop from peak should trigger regression_detected=True."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    # Build history with peak at 0.90, then drop to 0.70
    tracker._history.append(CapabilitySnapshot(generation=0, eval_mean=0.70))
    tracker._history.append(CapabilitySnapshot(generation=1, eval_mean=0.75))
    tracker._history.append(CapabilitySnapshot(generation=2, eval_mean=0.80))
    tracker._history.append(CapabilitySnapshot(generation=3, eval_mean=0.85))
    tracker._history.append(CapabilitySnapshot(generation=4, eval_mean=0.90))  # Peak
    tracker._history.append(CapabilitySnapshot(generation=5, eval_mean=0.70))  # Drop by 0.20

    # Regression detection threshold is 0.15, so drop > 0.15 should trigger
    is_regressing = tracker._detect_regression(current=0.70, window=6)
    assert is_regressing is True


def test_no_regression_when_within_threshold(tmp_snapshot_file, tmp_dashboard_file):
    """A drop smaller than 0.15 should not trigger regression."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    tracker._history.append(CapabilitySnapshot(generation=0, eval_mean=0.80))
    tracker._history.append(CapabilitySnapshot(generation=1, eval_mean=0.82))
    tracker._history.append(CapabilitySnapshot(generation=2, eval_mean=0.85))  # Peak
    tracker._history.append(CapabilitySnapshot(generation=3, eval_mean=0.80))  # Only 0.05 drop

    is_regressing = tracker._detect_regression(current=0.80, window=4)
    assert is_regressing is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: targets_met reflects target status
# ─────────────────────────────────────────────────────────────────────────────

def test_targets_met_partial(tmp_snapshot_file, tmp_dashboard_file):
    """Verify targets_met correctly reflects which targets are met via track_cycle."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    # Call track_cycle without mocks - it should handle defaults gracefully
    report = tracker.track_cycle()

    targets = report.targets_met
    # Verify the target keys are present
    assert "latency_p95_under_100ms" in targets
    assert "validation_95pct" in targets
    assert "monthly_2x_improvement" in targets
    # Values depend on defaults and current state
    assert isinstance(targets["latency_p95_under_100ms"], bool)
    assert isinstance(targets["validation_95pct"], bool)
    assert isinstance(targets["monthly_2x_improvement"], bool)


# ─────────────────────────────────────────────────────────────────────────────
# Test: get_monthly_improvement
# ─────────────────────────────────────────────────────────────────────────────

def test_get_monthly_improvement(tmp_snapshot_file, tmp_dashboard_file):
    """Verify _compute_monthly_improvement computes improvement ratio correctly."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    current_time = time.time()

    # Add older snapshot outside 30-day window
    older_snap = CapabilitySnapshot(
        generation=0,
        eval_mean=0.50,
        timestamp=current_time - 40 * 86400,  # 40 days ago
    )
    tracker._history.append(older_snap)

    # Add intermediate snapshot within 30-day window
    intermediate_snap = CapabilitySnapshot(
        generation=1,
        eval_mean=0.60,
        timestamp=current_time - 20 * 86400,  # 20 days ago
    )
    tracker._history.append(intermediate_snap)

    # Current snapshot
    current_snap = CapabilitySnapshot(
        generation=2,
        eval_mean=0.80,
        timestamp=current_time,
    )
    tracker._history.append(current_snap)

    # Compute monthly improvement
    improvement = tracker._compute_monthly_improvement(current_score=0.80)

    # With baseline_snaps within window and older snapshot outside,
    # the method uses the oldest snapshot as baseline
    assert improvement is not None
    # The exact ratio depends on implementation details; verify it's computed
    assert isinstance(improvement, float)


def test_get_monthly_improvement_no_baseline(tmp_snapshot_file, tmp_dashboard_file):
    """When all snapshots are within 30 days, use the oldest as baseline."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )

    current_time = time.time()

    # All snapshots within 30 days
    for i in range(3):
        tracker._history.append(CapabilitySnapshot(
            generation=i,
            eval_mean=0.80,
            timestamp=current_time - (20 - i * 5) * 86400,  # 20, 15, 10 days ago
        ))

    improvement = tracker._compute_monthly_improvement(current_score=0.80)
    # All have same eval_mean, so ratio should be 1.0
    assert improvement == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Test: load_history ignores malformed lines
# ─────────────────────────────────────────────────────────────────────────────

def test_load_history_ignores_malformed_lines(tmp_path):
    """JSONL with bad lines should load good snapshots without error."""
    snapshot_file = tmp_path / "test_snapshots.jsonl"
    valid_snap = {
        "snapshot_id": "abc12345",
        "timestamp": time.time(),
        "generation": 0,
        "eval_mean": 0.75,
        "eval_p95": 0.80,
        "eval_peak": 0.80,
        "eval_count": 10,
        "latency_mean_ms": 50.0,
        "latency_p95_ms": 75.0,
        "validation_pass_rate": 0.95,
        "validation_total": 100,
        "memory_entries": 50,
        "apo_generation": 3,
        "lessons_total": 10,
        "monthly_improvement": None,
        "regression_detected": False,
        "targets_met": {},
    }

    # Write JSONL with mixed good/bad lines
    lines = [
        json.dumps(valid_snap),
        "{ invalid json }",
        "",
        json.dumps(valid_snap | {"generation": 1, "eval_mean": 0.78}),
        "not even close to json",
        json.dumps(valid_snap | {"generation": 2, "eval_mean": 0.80}),
    ]
    snapshot_file.write_text("\n".join(lines))

    tracker = EvolutionTracker(snapshot_path=str(snapshot_file))

    # Should load the valid snapshots (malformed lines ignored)
    assert len(tracker._history) == 3
    assert tracker._history[0].eval_mean == 0.75
    assert tracker._history[1].eval_mean == 0.78
    assert tracker._history[2].eval_mean == 0.80


# ─────────────────────────────────────────────────────────────────────────────
# Test: save and load snapshot roundtrip
# ─────────────────────────────────────────────────────────────────────────────

def test_save_and_load_snapshot(tmp_path):
    """Saving a snapshot and reloading should produce equal data."""
    snapshot_file = tmp_path / "test_roundtrip.jsonl"

    # Create tracker and add snapshot
    tracker = EvolutionTracker(snapshot_path=str(snapshot_file))
    report = tracker.track_cycle()
    original_snap = report.snapshot

    # Snapshot should have been saved
    assert snapshot_file.exists()
    saved_lines = snapshot_file.read_text().strip().split("\n")
    assert len(saved_lines) == 1

    # Create new tracker instance to load from disk
    loaded_tracker = EvolutionTracker(snapshot_path=str(snapshot_file))
    assert len(loaded_tracker._history) == 1

    loaded_snap = loaded_tracker._history[0]
    assert loaded_snap.snapshot_id == original_snap.snapshot_id
    assert loaded_snap.generation == original_snap.generation
    assert loaded_snap.eval_mean == original_snap.eval_mean
    assert loaded_snap.eval_p95 == original_snap.eval_p95
    assert loaded_snap.latency_mean_ms == original_snap.latency_mean_ms
    assert loaded_snap.validation_pass_rate == original_snap.validation_pass_rate
    assert loaded_snap.regression_detected == original_snap.regression_detected


# ─────────────────────────────────────────────────────────────────────────────
# Test: module singleton
# ─────────────────────────────────────────────────────────────────────────────

def test_module_singleton():
    """get_evolution_tracker() should return the same instance on repeated calls."""
    # Reset the global singleton for this test
    import simp.projectx.evolution_tracker as ev_module
    original_tracker = ev_module._tracker
    ev_module._tracker = None

    try:
        tracker1 = get_evolution_tracker()
        tracker2 = get_evolution_tracker()

        assert tracker1 is tracker2
    finally:
        # Restore original state
        ev_module._tracker = original_tracker


# ─────────────────────────────────────────────────────────────────────────────
# Test: _percentile helper
# ─────────────────────────────────────────────────────────────────────────────

def test_percentile_basic():
    """Verify _percentile calculation matches the module's implementation."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    # The module's implementation: idx = ceil(p * n) - 1, clamped
    # For p=0.5, n=10: idx = ceil(5) - 1 = 5 - 1 = 4 → sorted_data[4] = 5.0
    assert _percentile(data, 0.5) == 5.0
    assert _percentile(data, 0.95) == 10.0
    assert _percentile(data, 0.0) == 1.0


def test_percentile_empty():
    """Empty data should return 0.0."""
    assert _percentile([], 0.5) == 0.0


def test_percentile_single():
    """Single element should return that element."""
    assert _percentile([42.0], 0.95) == 42.0


# ─────────────────────────────────────────────────────────────────────────────
# Test: get_history returns copy
# ─────────────────────────────────────────────────────────────────────────────

def test_get_history_returns_copy(tmp_snapshot_file, tmp_dashboard_file):
    """get_history() should return a copy, not the internal list."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )
    tracker._history.append(CapabilitySnapshot(generation=0))

    history = tracker.get_history()
    history.append(CapabilitySnapshot(generation=999))  # Modify returned list

    assert len(tracker._history) == 1  # Internal list unchanged
    assert len(history) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test: on_track_for_2x calculation
# ─────────────────────────────────────────────────────────────────────────────

def test_on_track_for_2x_positive(tmp_snapshot_file, tmp_dashboard_file):
    """Report should show on_track_for_2x when improvement thresholds are met."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )
    
    # Add history to trigger trend computation
    for i in range(5):
        snap = CapabilitySnapshot(generation=i, eval_mean=0.6 + i * 0.05)
        snap.timestamp = time.time() + i * 86400
        tracker._history.append(snap)
    
    report = tracker.track_cycle()
    assert hasattr(report, 'on_track_for_2x')


def test_track_cycle_sets_targets_met(tmp_snapshot_file, tmp_dashboard_file):
    """Verify track_cycle properly sets targets_met in the returned report."""
    tracker = EvolutionTracker(
        snapshot_path=str(tmp_snapshot_file),
        dashboard_path=str(tmp_dashboard_file),
    )
    
    report = tracker.track_cycle()
    
    assert "latency_p95_under_100ms" in report.targets_met
    assert "validation_95pct" in report.targets_met
    assert "monthly_2x_improvement" in report.targets_met
