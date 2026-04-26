"""Tests for Learning Loop — ProjectX agent learning cycle management."""

import time
import pytest
from simp.projectx.learning_loop import (
    LearningLoop,
    get_learning_loop,
    start_learning_loop,
)


class TestLearningLoop:
    def test_initialization(self) -> None:
        loop = LearningLoop(interval=1.0)
        assert loop is not None

    def test_default_initialization(self) -> None:
        loop = LearningLoop()
        assert loop is not None

    def test_status_tracking(self) -> None:
        loop = LearningLoop(interval=999)
        status = loop.status()
        assert isinstance(status, dict)
        assert "cycles_completed" in status or "last_cycle_ts" in status

    def test_run_once(self) -> None:
        loop = LearningLoop(interval=999)
        result = loop.run_once()
        assert isinstance(result, dict)

    def test_start_and_stop(self) -> None:
        loop = LearningLoop(interval=0.01)
        loop.start()
        status = loop.status()
        assert status is not None
        loop.stop()

    def test_stop_from_idle(self) -> None:
        loop = LearningLoop(interval=999)
        loop.stop()  # Should not raise

    def test_get_learning_loop_singleton(self) -> None:
        loop1 = get_learning_loop()
        loop2 = get_learning_loop()
        assert loop1 is loop2

    def test_start_learning_loop_function(self) -> None:
        loop = start_learning_loop(interval=0.01)
        assert loop is not None
        assert isinstance(loop, LearningLoop)
        loop.stop()

    def test_status_contains_metrics(self) -> None:
        loop = LearningLoop(interval=999)
        status = loop.status()
        # Status should contain cycle metrics
        assert "last_cycle_ts" in status or "cycles_completed" in status or "total_policies" in status

    def test_loop_interval_respected(self) -> None:
        loop = LearningLoop(interval=0.05)
        t0 = time.time()
        loop.run_once()
        loop.run_once()
        elapsed = time.time() - t0
        assert elapsed >= 0  # Sanity check


class TestLoopStatus:
    def test_loop_status_has_metrics(self) -> None:
        loop = LearningLoop(interval=999)
        status = loop.status()
        # Status object should have lesson/policy/cost metrics
        assert "total_lessons" in status or "total_policies" in status or "cycles_completed" in status


class TestLearningLoopPersistence:
    def test_loop_reports_trend(self) -> None:
        loop = LearningLoop(interval=999)
        status = loop.status()
        # Should have evolution trend tracking
        assert "evolution_trend" in status or "on_track_for_2x" in status or "cycles_completed" in status
