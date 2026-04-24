"""
ProjectX Safety Monitor — Phase 4

Real-time safety monitoring for the self-improvement loop.
Provides:
  - Metric collection (latency, score, error rate, resource usage)
  - Threshold alerting with configurable severity levels
  - Emergency stop mechanism that halts all ProjectX operations
  - Human oversight hooks — any ESCALATE judgment pauses the loop

Design principle: safety checks never block indefinitely and always
degrade gracefully. If the monitor itself fails, operations continue
(fail-open for availability) but the failure is logged.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    HIGH_LATENCY = "high_latency"
    HIGH_ERROR_RATE = "high_error_rate"
    LOW_SCORE = "low_score"
    SCORE_REGRESSION = "score_regression"
    RESOURCE_OVERRUN = "resource_overrun"
    EMERGENCY_STOP = "emergency_stop"
    ESCALATION_REQUIRED = "escalation_required"


@dataclass
class Alert:
    alert_type: AlertType
    severity: Severity
    message: str
    value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SafetyConfig:
    """Configurable thresholds for the safety monitor."""
    max_latency_ms: float = 5000.0
    min_score: float = 0.30
    max_error_rate: float = 0.25        # fraction of recent ops
    score_regression_threshold: float = 0.15  # drop from rolling peak
    max_memory_mb: float = 2048.0
    window_size: int = 50               # rolling window for rate calculations
    escalation_pause_seconds: float = 300.0  # pause after ESCALATE judgment


_DEFAULT_CONFIG = SafetyConfig()


class SafetyMonitor:
    """
    Monitors ProjectX runtime metrics and raises alerts.

    Usage::

        monitor = SafetyMonitor()
        monitor.record("inference_latency_ms", 320)
        monitor.record("eval_score", 0.82)
        alerts = monitor.check_alerts()
        if monitor.emergency_stopped:
            sys.exit(1)
    """

    def __init__(self, config: Optional[SafetyConfig] = None) -> None:
        self._config = config or _DEFAULT_CONFIG
        self._metrics: Dict[str, deque] = {}
        self._alerts: List[Alert] = []
        self._emergency_stopped = False
        self._escalation_pause_until: float = 0.0
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._lock = threading.Lock()
        self._peak_score: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def emergency_stopped(self) -> bool:
        return self._emergency_stopped

    @property
    def is_paused(self) -> bool:
        return time.time() < self._escalation_pause_until

    def record(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric data point."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = deque(maxlen=self._config.window_size)
            self._metrics[name].append(
                MetricPoint(name=name, value=value, tags=tags or {})
            )
            # Track peak score for regression detection
            if name == "eval_score" and value > self._peak_score:
                self._peak_score = value

    def check_alerts(self) -> List[Alert]:
        """Evaluate all thresholds and return any new alerts."""
        new_alerts: List[Alert] = []

        with self._lock:
            # Latency check
            latency_pts = self._get_recent("inference_latency_ms")
            if latency_pts:
                avg_lat = sum(p.value for p in latency_pts) / len(latency_pts)
                if avg_lat > self._config.max_latency_ms:
                    new_alerts.append(Alert(
                        alert_type=AlertType.HIGH_LATENCY,
                        severity=Severity.WARNING,
                        message=f"Avg latency {avg_lat:.0f}ms > {self._config.max_latency_ms:.0f}ms",
                        value=avg_lat,
                        threshold=self._config.max_latency_ms,
                    ))

            # Error rate check
            error_pts = self._get_recent("eval_error")
            total_pts = self._get_recent("eval_total")
            if total_pts and len(total_pts) > 0:
                errors = sum(p.value for p in error_pts)
                total = sum(p.value for p in total_pts) or 1
                rate = errors / total
                if rate > self._config.max_error_rate:
                    new_alerts.append(Alert(
                        alert_type=AlertType.HIGH_ERROR_RATE,
                        severity=Severity.CRITICAL,
                        message=f"Error rate {rate:.1%} > {self._config.max_error_rate:.1%}",
                        value=rate,
                        threshold=self._config.max_error_rate,
                    ))

            # Score check
            score_pts = self._get_recent("eval_score")
            if score_pts:
                avg_score = sum(p.value for p in score_pts) / len(score_pts)
                if avg_score < self._config.min_score:
                    new_alerts.append(Alert(
                        alert_type=AlertType.LOW_SCORE,
                        severity=Severity.WARNING,
                        message=f"Avg score {avg_score:.3f} < {self._config.min_score:.3f}",
                        value=avg_score,
                        threshold=self._config.min_score,
                    ))
                # Score regression check
                if self._peak_score > 0:
                    regression = self._peak_score - avg_score
                    if regression > self._config.score_regression_threshold:
                        new_alerts.append(Alert(
                            alert_type=AlertType.SCORE_REGRESSION,
                            severity=Severity.CRITICAL,
                            message=(
                                f"Score regression {regression:.3f} "
                                f"(peak={self._peak_score:.3f}, current={avg_score:.3f})"
                            ),
                            value=regression,
                            threshold=self._config.score_regression_threshold,
                        ))

            # Memory usage
            try:
                import psutil
                proc = psutil.Process(os.getpid())
                mem_mb = proc.memory_info().rss / 1_048_576
                if mem_mb > self._config.max_memory_mb:
                    new_alerts.append(Alert(
                        alert_type=AlertType.RESOURCE_OVERRUN,
                        severity=Severity.CRITICAL,
                        message=f"Memory {mem_mb:.0f}MB > {self._config.max_memory_mb:.0f}MB",
                        value=mem_mb,
                        threshold=self._config.max_memory_mb,
                    ))
            except ImportError:
                pass

        for alert in new_alerts:
            self._handle_alert(alert)

        return new_alerts

    def trigger_emergency_stop(self, reason: str) -> None:
        """Halt all ProjectX operations immediately."""
        with self._lock:
            self._emergency_stopped = True
        alert = Alert(
            alert_type=AlertType.EMERGENCY_STOP,
            severity=Severity.CRITICAL,
            message=f"EMERGENCY STOP: {reason}",
            value=1.0,
            threshold=0.0,
        )
        self._handle_alert(alert)
        logger.critical("ProjectX EMERGENCY STOP triggered: %s", reason)

    def clear_emergency_stop(self) -> None:
        with self._lock:
            self._emergency_stopped = False
        logger.warning("Emergency stop cleared — resuming operations")

    def register_escalation(self, reason: str) -> None:
        """Called when a safety judgment requires human review."""
        with self._lock:
            self._escalation_pause_until = time.time() + self._config.escalation_pause_seconds
        alert = Alert(
            alert_type=AlertType.ESCALATION_REQUIRED,
            severity=Severity.CRITICAL,
            message=f"Human escalation required: {reason}. Pausing {self._config.escalation_pause_seconds:.0f}s.",
            value=1.0,
            threshold=0.0,
        )
        self._handle_alert(alert)
        logger.warning("Escalation registered: %s (pause until %s)", reason,
                       time.ctime(self._escalation_pause_until))

    def on_alert(self, callback: Callable[[Alert], None]) -> None:
        """Register a callback invoked on every new alert."""
        self._alert_callbacks.append(callback)

    def get_summary(self) -> Dict[str, Any]:
        """Return a snapshot of current health metrics."""
        with self._lock:
            def rolling_avg(name: str) -> Optional[float]:
                pts = self._get_recent(name)
                return sum(p.value for p in pts) / len(pts) if pts else None

            return {
                "emergency_stopped": self._emergency_stopped,
                "is_paused": self.is_paused,
                "pause_remaining_s": max(0.0, self._escalation_pause_until - time.time()),
                "alert_count": len(self._alerts),
                "recent_alerts": [a.alert_type.value for a in self._alerts[-5:]],
                "metrics": {
                    "avg_latency_ms": rolling_avg("inference_latency_ms"),
                    "avg_score": rolling_avg("eval_score"),
                    "peak_score": self._peak_score,
                },
            }

    def get_alerts(self, last_n: int = 20) -> List[Alert]:
        return self._alerts[-last_n:]

    # ── Internal ──────────────────────────────────────────────────────────

    def _get_recent(self, name: str) -> List[MetricPoint]:
        return list(self._metrics.get(name, []))

    def _handle_alert(self, alert: Alert) -> None:
        self._alerts.append(alert)
        if len(self._alerts) > 500:
            self._alerts = self._alerts[-500:]
        logger.log(
            logging.CRITICAL if alert.severity == Severity.CRITICAL else logging.WARNING,
            "[SafetyMonitor] %s: %s", alert.alert_type.value, alert.message,
        )
        for cb in self._alert_callbacks:
            try:
                cb(alert)
            except Exception as exc:
                logger.debug("Alert callback raised: %s", exc)


# Module-level singleton
_monitor: Optional[SafetyMonitor] = None
_monitor_lock = threading.Lock()


def get_safety_monitor(config: Optional[SafetyConfig] = None) -> SafetyMonitor:
    global _monitor
    with _monitor_lock:
        if _monitor is None:
            _monitor = SafetyMonitor(config)
    return _monitor
