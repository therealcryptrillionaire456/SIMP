"""
ProjectX Evolution Tracker — Phase 6 (Success Metrics)

Tracks capability improvement over time against the roadmap's success metrics:
  - 2x monthly improvement in eval scores
  - <100ms inference response (p95)
  - >95% validation pass rate
  - <24h domain adaptation

Records capability snapshots to a JSONL file on each self-improvement cycle.
Computes rolling improvement rates, regression detection, and trend analysis.
Exports a dashboard-compatible JSON summary for the existing SIMP dashboard.

Snapshot schema (one per self_improve() call):
  {
    "snapshot_id": str,
    "timestamp": float,
    "generation": int,
    "eval_score": {"mean": float, "p95": float, "peak": float},
    "latency_ms": {"mean": float, "p95": float},
    "validation": {"pass_rate": float, "total": int},
    "memory_entries": int,
    "apo_generation": int,
    "monthly_improvement": float | null,
    "regression": bool
  }
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Roadmap success metric targets
TARGETS = {
    "monthly_improvement_rate": 2.0,    # 2x = 100% improvement per month
    "latency_ms_p95": 100.0,            # <100ms p95
    "validation_pass_rate": 0.95,       # >95%
    "domain_adaptation_hours": 24.0,    # <24h
}

_SNAPSHOT_PATH = "projectx_logs/evolution_snapshots.jsonl"
_DASHBOARD_PATH = "projectx_logs/evolution_dashboard.json"
_MONTH_SECONDS = 30 * 24 * 3600


@dataclass
class CapabilitySnapshot:
    snapshot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    generation: int = 0
    # Eval scores
    eval_mean: float = 0.0
    eval_p95: float = 0.0
    eval_peak: float = 0.0
    eval_count: int = 0
    # Latency
    latency_mean_ms: float = 0.0
    latency_p95_ms: float = 0.0
    # Validation
    validation_pass_rate: float = 0.0
    validation_total: int = 0
    # System state
    memory_entries: int = 0
    apo_generation: int = 0
    lessons_total: int = 0
    # Computed
    monthly_improvement: Optional[float] = None  # ratio vs 30-day-ago baseline
    regression_detected: bool = False
    targets_met: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["iso_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp))
        return d


@dataclass
class EvolutionReport:
    """Returned from track_cycle() — the caller sees this."""
    snapshot: CapabilitySnapshot
    trend: str          # "improving", "stable", "regressing"
    targets_met: Dict[str, bool] = field(default_factory=dict)
    week_over_week: Optional[float] = None   # score ratio
    month_over_month: Optional[float] = None
    on_track_for_2x: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "trend": self.trend,
            "targets_met": self.targets_met,
            "week_over_week": self.week_over_week,
            "month_over_month": self.month_over_month,
            "on_track_for_2x": self.on_track_for_2x,
        }


class EvolutionTracker:
    """
    Tracks ProjectX capability growth over time.

    Usage::

        tracker = EvolutionTracker()
        report = tracker.track_cycle(safety_monitor=mon, apo_engine=apo, rag_memory=mem)
        print(report.trend, report.on_track_for_2x)
    """

    def __init__(
        self,
        snapshot_path: str = _SNAPSHOT_PATH,
        dashboard_path: str = _DASHBOARD_PATH,
    ) -> None:
        self._snapshot_path = Path(snapshot_path)
        self._dashboard_path = Path(dashboard_path)
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._history: List[CapabilitySnapshot] = self._load_history()

    # ── Public API ────────────────────────────────────────────────────────

    def track_cycle(
        self,
        safety_monitor=None,
        apo_engine=None,
        rag_memory=None,
        meta_learner_report=None,
    ) -> EvolutionReport:
        """
        Capture a capability snapshot and compute evolution metrics.

        Args:
            safety_monitor: SafetyMonitor instance for score/latency metrics.
            apo_engine:     APOEngine for generation and best score.
            rag_memory:     RAGMemory for entry count.
            meta_learner_report: LearningCycleReport from last meta-learning cycle.

        Returns:
            EvolutionReport with trend analysis and target tracking.
        """
        generation = len(self._history)
        snap = CapabilitySnapshot(generation=generation)

        # Collect metrics from safety monitor
        if safety_monitor:
            try:
                summary = safety_monitor.get_summary()
                metrics = summary.get("metrics") or {}
                snap.eval_mean = metrics.get("avg_score") or 0.0
                snap.eval_peak = metrics.get("peak_score") or 0.0
                snap.latency_mean_ms = metrics.get("avg_latency_ms") or 0.0
                # Approximate p95 from recent alerts
                alerts = safety_monitor.get_alerts(last_n=50)
                latencies = [a.value for a in alerts if a.alert_type.value == "high_latency"]
                snap.latency_p95_ms = _percentile(latencies, 0.95) if latencies else snap.latency_mean_ms
                scores_all = self._extract_scores_from_monitor(safety_monitor)
                snap.eval_p95 = _percentile(scores_all, 0.95) if scores_all else snap.eval_mean
                snap.eval_count = len(scores_all)
            except Exception as exc:
                logger.debug("Safety monitor metric extraction failed: %s", exc)

        # APO state
        if apo_engine:
            try:
                report = apo_engine.report()
                snap.apo_generation = report.get("generation", 0)
                best = report.get("best_score", 0.0)
                if best > snap.eval_peak:
                    snap.eval_peak = best
            except Exception as exc:
                logger.debug("APO report failed: %s", exc)

        # RAG memory count
        if rag_memory:
            try:
                snap.memory_entries = rag_memory.count()
            except Exception:
                pass

        # Validation pass rate from validation history
        snap.validation_pass_rate, snap.validation_total = self._compute_validation_rate()

        # Lessons from meta_learner
        if meta_learner_report and hasattr(meta_learner_report, "lessons_promoted"):
            snap.lessons_total = meta_learner_report.lessons_promoted

        # Monthly improvement vs 30-day baseline
        snap.monthly_improvement = self._compute_monthly_improvement(snap.eval_mean)

        # Regression detection
        snap.regression_detected = self._detect_regression(snap.eval_mean)

        # Target tracking
        snap.targets_met = {
            "latency_p95_under_100ms": snap.latency_p95_ms < TARGETS["latency_ms_p95"] if snap.latency_p95_ms else True,
            "validation_95pct": snap.validation_pass_rate >= TARGETS["validation_pass_rate"],
            "monthly_2x_improvement": (snap.monthly_improvement or 0) >= TARGETS["monthly_improvement_rate"],
        }

        # Persist
        self._history.append(snap)
        self._save_snapshot(snap)

        # Build report
        trend = self._compute_trend()
        week_ow = self._compare_periods(7)
        month_ow = snap.monthly_improvement
        on_track = (month_ow or 0) >= 1.5 or (week_ow or 0) >= 1.1

        report = EvolutionReport(
            snapshot=snap,
            trend=trend,
            targets_met=snap.targets_met,
            week_over_week=week_ow,
            month_over_month=month_ow,
            on_track_for_2x=on_track,
        )

        self._update_dashboard(report)
        return report

    def get_history(self, last_n: int = 50) -> List[CapabilitySnapshot]:
        return self._history[-last_n:]

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Return current dashboard JSON for the SIMP dashboard renderer."""
        if self._dashboard_path.exists():
            try:
                return json.loads(self._dashboard_path.read_text())
            except Exception:
                pass
        return {}

    # ── Internal ──────────────────────────────────────────────────────────

    def _compute_monthly_improvement(self, current_score: float) -> Optional[float]:
        """Return current/baseline ratio for the 30-day window."""
        deadline = time.time() - _MONTH_SECONDS
        baseline_snaps = [s for s in self._history if s.timestamp >= deadline]
        if not baseline_snaps:
            older = [s for s in self._history if s.timestamp < deadline]
            if not older:
                return None
            baseline = older[-1].eval_mean
        else:
            baseline = baseline_snaps[0].eval_mean
        if baseline <= 0:
            return None
        return round(current_score / baseline, 4)

    def _compare_periods(self, days: int) -> Optional[float]:
        """Return ratio of current score vs score N days ago."""
        if len(self._history) < 2:
            return None
        cutoff = time.time() - days * 86400
        baseline = next((s.eval_mean for s in reversed(self._history) if s.timestamp < cutoff), None)
        if baseline is None or baseline <= 0:
            return None
        current = self._history[-1].eval_mean
        return round(current / baseline, 4)

    def _detect_regression(self, current: float, window: int = 10) -> bool:
        if len(self._history) < window:
            return False
        recent = [s.eval_mean for s in self._history[-window:]]
        if not recent:
            return False
        peak = max(recent)
        return (peak - current) > 0.15

    def _compute_trend(self) -> str:
        if len(self._history) < 3:
            return "stable"
        recent = [s.eval_mean for s in self._history[-5:]]
        if len(recent) < 3:
            return "stable"
        diffs = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        avg_diff = sum(diffs) / len(diffs)
        if avg_diff > 0.01:
            return "improving"
        if avg_diff < -0.01:
            return "regressing"
        return "stable"

    def _compute_validation_rate(self) -> Tuple[float, int]:
        if not self._history:
            return 0.0, 0
        last = self._history[-1]
        return last.validation_pass_rate, last.validation_total

    @staticmethod
    def _extract_scores_from_monitor(monitor) -> List[float]:
        try:
            pts = monitor._metrics.get("eval_score", [])
            return [p.value for p in pts]
        except Exception:
            return []

    def _save_snapshot(self, snap: CapabilitySnapshot) -> None:
        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.append_line(self._snapshot_path, json.dumps(snap.to_dict(), default=str))
        except Exception as exc:
            logger.warning("Failed to save evolution snapshot: %s", exc)

    def _load_history(self) -> List[CapabilitySnapshot]:
        if not self._snapshot_path.exists():
            return []
        history: List[CapabilitySnapshot] = []
        try:
            for line in self._snapshot_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    # Remove computed fields not in dataclass
                    d.pop("iso_timestamp", None)
                    history.append(CapabilitySnapshot(**{
                        k: v for k, v in d.items()
                        if k in CapabilitySnapshot.__dataclass_fields__
                    }))
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Failed to load evolution history: %s", exc)
        return history

    def _update_dashboard(self, report: EvolutionReport) -> None:
        """Write a dashboard-compatible JSON summary."""
        try:
            history_scores = [s.eval_mean for s in self._history[-30:]]
            history_ts = [s.timestamp for s in self._history[-30:]]
            dashboard = {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "current": report.snapshot.to_dict(),
                "trend": report.trend,
                "on_track_for_2x": report.on_track_for_2x,
                "targets_met": report.targets_met,
                "week_over_week": report.week_over_week,
                "month_over_month": report.month_over_month,
                "chart": {
                    "timestamps": history_ts,
                    "eval_scores": history_scores,
                    "target_score": 0.95,
                },
                "roadmap_targets": TARGETS,
            }
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.write_json(self._dashboard_path, dashboard)
        except Exception as exc:
            logger.debug("Dashboard update failed: %s", exc)


def _percentile(data: List[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = math.ceil(p * len(sorted_data)) - 1
    return sorted_data[max(0, min(idx, len(sorted_data) - 1))]


# Module-level singleton
_tracker: Optional[EvolutionTracker] = None


def get_evolution_tracker() -> EvolutionTracker:
    global _tracker
    if _tracker is None:
        _tracker = EvolutionTracker()
    return _tracker
