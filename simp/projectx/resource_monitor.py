"""
ProjectX Resource Monitor — Step 7

CPU / memory / disk / thread monitoring with auto-throttle wired into SafetyMonitor.

Features:
  - Polls system resources every N seconds via background thread
  - Emits ResourceSnapshot dataclass with all metrics
  - Auto-throttle: raises ThrottleSignal when thresholds exceeded
  - Wires into SafetyMonitor.record() for unified alerting
  - Exposes Prometheus-style gauge metrics for telemetry.py
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    timestamp:      float = field(default_factory=time.time)
    cpu_percent:    float = 0.0
    memory_percent: float = 0.0
    memory_mb:      float = 0.0
    disk_percent:   float = 0.0
    thread_count:   int = 0
    fd_count:       int = 0
    load_avg_1m:    float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_percent": round(self.memory_percent, 1),
            "memory_mb": round(self.memory_mb, 1),
            "disk_percent": round(self.disk_percent, 1),
            "thread_count": self.thread_count,
            "fd_count": self.fd_count,
            "load_avg_1m": round(self.load_avg_1m, 2),
        }

    @property
    def healthy(self) -> bool:
        return (
            self.cpu_percent < 85.0
            and self.memory_percent < 88.0
            and self.disk_percent < 90.0
        )


class ThrottleSignal(Exception):
    """Raised when a resource threshold is breached."""
    def __init__(self, reason: str, snapshot: ResourceSnapshot) -> None:
        super().__init__(reason)
        self.reason = reason
        self.snapshot = snapshot


@dataclass
class ResourceThresholds:
    cpu_warn:       float = 70.0
    cpu_critical:   float = 85.0
    memory_warn:    float = 75.0
    memory_critical: float = 88.0
    disk_warn:      float = 80.0
    disk_critical:  float = 90.0
    thread_max:     int = 200
    fd_max:         int = 1000


class ResourceMonitor:
    """
    Background resource monitor with auto-throttle and SafetyMonitor integration.

    Usage::

        monitor = ResourceMonitor(poll_interval=10)
        monitor.start()

        snap = monitor.latest()
        monitor.check_throttle()   # raises ThrottleSignal if critical
    """

    def __init__(
        self,
        poll_interval: int = 15,
        thresholds: Optional[ResourceThresholds] = None,
        safety_monitor=None,
        on_throttle: Optional[Callable[[ThrottleSignal], None]] = None,
    ) -> None:
        # Clamp interval to [5, 300] to prevent runaway polling or staleness
        self._interval = max(5, min(poll_interval, 300))
        self._thresholds = thresholds or ResourceThresholds()
        self._safety = safety_monitor
        self._on_throttle = on_throttle
        self._history: List[ResourceSnapshot] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._psutil_available: Optional[bool] = None

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="resource-monitor")
        self._thread.start()
        logger.info("ResourceMonitor started (interval=%ds)", self._interval)

    def stop(self) -> None:
        self._running = False

    def latest(self) -> Optional[ResourceSnapshot]:
        with self._lock:
            return self._history[-1] if self._history else None

    def history(self, last_n: int = 60) -> List[ResourceSnapshot]:
        with self._lock:
            return list(self._history[-last_n:])

    def snapshot(self) -> ResourceSnapshot:
        """Take an immediate snapshot (synchronous)."""
        snap = self._collect()
        with self._lock:
            self._history.append(snap)
            if len(self._history) > 1000:
                self._history = self._history[-500:]
        return snap

    def check_throttle(self) -> None:
        """Raise ThrottleSignal if any critical threshold is exceeded."""
        snap = self.latest() or self.snapshot()
        t = self._thresholds
        if snap.cpu_percent >= t.cpu_critical:
            raise ThrottleSignal(f"CPU critical: {snap.cpu_percent:.1f}%", snap)
        if snap.memory_percent >= t.memory_critical:
            raise ThrottleSignal(f"Memory critical: {snap.memory_percent:.1f}%", snap)
        if snap.disk_percent >= t.disk_critical:
            raise ThrottleSignal(f"Disk critical: {snap.disk_percent:.1f}%", snap)
        if snap.thread_count >= t.thread_max:
            raise ThrottleSignal(f"Thread count critical: {snap.thread_count}", snap)

    def gauges(self) -> Dict[str, float]:
        """Return flat dict of gauge values for telemetry."""
        snap = self.latest()
        if not snap:
            return {}
        return {
            "resource_cpu_percent": snap.cpu_percent,
            "resource_memory_percent": snap.memory_percent,
            "resource_memory_mb": snap.memory_mb,
            "resource_disk_percent": snap.disk_percent,
            "resource_thread_count": float(snap.thread_count),
            "resource_load_avg_1m": snap.load_avg_1m,
        }

    # ── Internal ──────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        while self._running:
            try:
                snap = self._collect()
                with self._lock:
                    self._history.append(snap)
                    if len(self._history) > 1000:
                        self._history = self._history[-500:]
                self._evaluate(snap)
            except Exception as exc:
                logger.debug("ResourceMonitor poll error: %s", exc)
            time.sleep(self._interval)

    _PSUTIL_TIMEOUT = 2.0  # seconds — psutil can block on some Linux /proc configs

    def _collect(self) -> ResourceSnapshot:
        snap = ResourceSnapshot()
        snap.thread_count = threading.active_count()

        # Probe psutil availability once
        if self._psutil_available is None:
            try:
                import psutil  # noqa: F401
                self._psutil_available = True
            except ImportError:
                self._psutil_available = False

        if self._psutil_available:
            self._collect_psutil(snap)

        # Fallback: load avg (Unix only)
        try:
            load = os.getloadavg()
            snap.load_avg_1m = load[0]
        except AttributeError:
            pass

        return snap

    def _collect_psutil(self, snap: ResourceSnapshot) -> None:
        """Run psutil collection in a daemon thread with timeout guard."""
        result: list = []

        def _worker() -> None:
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.1)
                vm = psutil.virtual_memory()
                du = psutil.disk_usage("/")
                proc = psutil.Process(os.getpid())
                fd = proc.num_fds() if hasattr(proc, "num_fds") else 0
                result.append((cpu, vm.percent, vm.used / 1_048_576, du.percent, fd))
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True, name="rmon-psutil")
        t.start()
        t.join(timeout=self._PSUTIL_TIMEOUT)
        if result:
            cpu, mem_pct, mem_mb, disk_pct, fd = result[0]
            snap.cpu_percent = cpu
            snap.memory_percent = mem_pct
            snap.memory_mb = mem_mb
            snap.disk_percent = disk_pct
            snap.fd_count = fd

    def _evaluate(self, snap: ResourceSnapshot) -> None:
        t = self._thresholds

        def _alert(metric: str, value: float, threshold: float, level: str) -> None:
            msg = f"[{level.upper()}] {metric}={value:.1f} exceeds {threshold}"
            logger.warning(msg)
            if self._safety:
                try:
                    self._safety.record(
                        subsystem="resource_monitor",
                        metric="resource_" + metric,
                        value=value,
                        metadata={"level": level, "threshold": threshold},
                    )
                except Exception:
                    pass

        if snap.cpu_percent >= t.cpu_critical:
            _alert("cpu_percent", snap.cpu_percent, t.cpu_critical, "critical")
            self._fire_throttle(f"CPU critical {snap.cpu_percent:.1f}%", snap)
        elif snap.cpu_percent >= t.cpu_warn:
            _alert("cpu_percent", snap.cpu_percent, t.cpu_warn, "warning")

        if snap.memory_percent >= t.memory_critical:
            _alert("memory_percent", snap.memory_percent, t.memory_critical, "critical")
            self._fire_throttle(f"Memory critical {snap.memory_percent:.1f}%", snap)
        elif snap.memory_percent >= t.memory_warn:
            _alert("memory_percent", snap.memory_percent, t.memory_warn, "warning")

        if snap.disk_percent >= t.disk_critical:
            _alert("disk_percent", snap.disk_percent, t.disk_critical, "critical")
        elif snap.disk_percent >= t.disk_warn:
            _alert("disk_percent", snap.disk_percent, t.disk_warn, "warning")

        if snap.thread_count >= t.thread_max:
            _alert("thread_count", float(snap.thread_count), float(t.thread_max), "critical")

    def _fire_throttle(self, reason: str, snap: ResourceSnapshot) -> None:
        signal = ThrottleSignal(reason, snap)
        if self._on_throttle:
            try:
                self._on_throttle(signal)
            except Exception:
                pass


# Module-level singleton
_monitor: Optional[ResourceMonitor] = None
_monitor_lock = threading.Lock()


def get_resource_monitor(auto_start: bool = True) -> ResourceMonitor:
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = ResourceMonitor()
                if auto_start:
                    _monitor.start()
    return _monitor
