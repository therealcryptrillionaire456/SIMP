"""
ProjectX Telemetry — Step 8

Prometheus exposition-format metrics emitter + Grafana dashboard generator.

Features:
  - MetricsRegistry: thread-safe counter, gauge, histogram registration
  - PrometheusExporter: /metrics endpoint text format (no HTTP server required)
  - GrafanaDashboard: generates dashboard JSON for standard panels
  - Auto-wires: APO scores, safety events, resource gauges, subsystem latency
  - TelemetryCollector: pulls from all projectx subsystems every cycle
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TELEMETRY_DIR = Path("projectx_logs/telemetry")
_NAMESPACE = "projectx"
_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")   # Prometheus: only [a-zA-Z0-9_]
_SAFE_HELP_RE = re.compile(r"[\r\n]")            # strip newlines from # HELP lines
_MAX_HELP_LEN = 256
_REGISTRY_LOCK = threading.Lock()               # module-level lock for singleton init


def _sanitize_name(raw: str) -> str:
    """Collapse non-alphanumeric chars to '_' and strip leading digits."""
    name = _SAFE_NAME_RE.sub("_", raw)
    if name and name[0].isdigit():
        name = "_" + name
    return name[:128] or "_"


def _sanitize_help(raw: str) -> str:
    return _SAFE_HELP_RE.sub(" ", str(raw))[:_MAX_HELP_LEN]


# ── Metric primitives ─────────────────────────────────────────────────────────

@dataclass
class Counter:
    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def inc(self, amount: float = 1.0) -> None:
        if amount < 0 or not math.isfinite(amount):
            raise ValueError(f"Counter.inc() amount must be non-negative finite, got {amount}")
        with self._lock:
            self._value += amount

    def value(self) -> float:
        with self._lock:
            return self._value


@dataclass
class Gauge:
    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def value(self) -> float:
        with self._lock:
            return self._value


@dataclass
class Histogram:
    name: str
    help: str
    buckets: List[float] = field(default_factory=lambda: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])
    labels: Dict[str, str] = field(default_factory=dict)
    _counts: List[int] = field(default_factory=list, init=False, repr=False)
    _sum: float = field(default=0.0, init=False, repr=False)
    _total: int = field(default=0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._counts = [0] * len(self.buckets)

    def observe(self, value: float) -> None:
        if not math.isfinite(value):
            return   # silently drop NaN/Inf — don't corrupt running sum
        with self._lock:
            self._sum += value
            self._total += 1
            for i, b in enumerate(self.buckets):
                if value <= b:
                    self._counts[i] += 1

    def snapshot(self) -> Tuple[List[int], float, int]:
        with self._lock:
            return list(self._counts), self._sum, self._total


# ── Registry ──────────────────────────────────────────────────────────────────

class MetricsRegistry:
    """Thread-safe registry for all projectx metrics."""

    def __init__(self, namespace: str = _NAMESPACE) -> None:
        self._ns = namespace
        self._metrics: Dict[str, Any] = {}
        self._lock = threading.Lock()

    _MAX_METRICS = 512   # prevent unbounded registry growth

    def counter(self, name: str, help: str = "", labels: Optional[Dict] = None) -> Counter:
        safe = _sanitize_name(name)
        key = f"counter:{safe}"
        with self._lock:
            if key not in self._metrics:
                if len(self._metrics) >= self._MAX_METRICS:
                    raise RuntimeError("MetricsRegistry full (512 metrics max)")
                self._metrics[key] = Counter(f"{self._ns}_{safe}", _sanitize_help(help), labels or {})
            return self._metrics[key]

    def gauge(self, name: str, help: str = "", labels: Optional[Dict] = None) -> Gauge:
        safe = _sanitize_name(name)
        key = f"gauge:{safe}"
        with self._lock:
            if key not in self._metrics:
                if len(self._metrics) >= self._MAX_METRICS:
                    raise RuntimeError("MetricsRegistry full (512 metrics max)")
                self._metrics[key] = Gauge(f"{self._ns}_{safe}", _sanitize_help(help), labels or {})
            return self._metrics[key]

    def histogram(self, name: str, help: str = "", buckets: Optional[List[float]] = None) -> Histogram:
        safe = _sanitize_name(name)
        key = f"histogram:{safe}"
        with self._lock:
            if key not in self._metrics:
                if len(self._metrics) >= self._MAX_METRICS:
                    raise RuntimeError("MetricsRegistry full (512 metrics max)")
                default_buckets = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
                bkts = sorted(b for b in (buckets or default_buckets) if math.isfinite(b) and b > 0)
                if not bkts:
                    bkts = default_buckets
                self._metrics[key] = Histogram(f"{self._ns}_{safe}", _sanitize_help(help), bkts)
            return self._metrics[key]

    def all_metrics(self) -> List[Any]:
        with self._lock:
            return list(self._metrics.values())


# ── Prometheus exporter ───────────────────────────────────────────────────────

class PrometheusExporter:
    """
    Renders MetricsRegistry as Prometheus text format.

    Call .render() to get the text; write it to a file or serve it.
    """

    def __init__(self, registry: MetricsRegistry) -> None:
        self._registry = registry

    def render(self) -> str:
        lines: List[str] = []
        for m in self._registry.all_metrics():
            # Names are already sanitized at registration time
            if isinstance(m, Counter):
                lines.append(f"# HELP {m.name} {_sanitize_help(m.help)}")
                lines.append(f"# TYPE {m.name} counter")
                lines.append(f"{m.name} {m.value():.6g}")
            elif isinstance(m, Gauge):
                lines.append(f"# HELP {m.name} {_sanitize_help(m.help)}")
                lines.append(f"# TYPE {m.name} gauge")
                lines.append(f"{m.name} {m.value():.6g}")
            elif isinstance(m, Histogram):
                counts, total_sum, total_count = m.snapshot()
                lines.append(f"# HELP {m.name} {_sanitize_help(m.help)}")
                lines.append(f"# TYPE {m.name} histogram")
                cumulative = 0
                for b, c in zip(m.buckets, counts):
                    cumulative += c
                    lines.append(f'{m.name}_bucket{{le="{b}"}} {cumulative}')
                lines.append(f'{m.name}_bucket{{le="+Inf"}} {total_count}')
                lines.append(f"{m.name}_sum {total_sum:.6g}")
                lines.append(f"{m.name}_count {total_count}")
        return "\n".join(lines) + "\n"

    def write(self, path: str) -> None:
        # Guard against path traversal
        p = Path(path).resolve()
        if ".." in Path(path).parts:
            raise ValueError(f"Path traversal rejected: {path}")
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.write_text(p, self.render())
        except Exception:
            p.write_text(self.render())


# ── Grafana dashboard generator ───────────────────────────────────────────────

class GrafanaDashboard:
    """Generates a minimal Grafana dashboard JSON for projectx metrics."""

    @staticmethod
    def generate(output_path: str = "projectx_logs/telemetry/grafana_dashboard.json") -> Dict:
        panels = [
            GrafanaDashboard._stat_panel(1, "APO Best Score", "projectx_apo_best_score", 0, 4),
            GrafanaDashboard._stat_panel(2, "CPU %", "projectx_resource_cpu_percent", 4, 4),
            GrafanaDashboard._stat_panel(3, "Memory %", "projectx_resource_memory_percent", 8, 4),
            GrafanaDashboard._timeseries_panel(4, "APO Score Over Time", "projectx_apo_best_score", 0, 8, 12, 8),
            GrafanaDashboard._timeseries_panel(5, "Safety Events", "projectx_safety_events_total", 12, 8, 12, 8),
            GrafanaDashboard._timeseries_panel(6, "Subsystem Calls", "projectx_subsystem_calls_total", 0, 16, 12, 8),
            GrafanaDashboard._timeseries_panel(7, "Resource CPU", "projectx_resource_cpu_percent", 12, 16, 12, 8),
        ]
        dashboard = {
            "title": "ProjectX Autonomy Dashboard",
            "uid": "projectx-v1",
            "schemaVersion": 36,
            "version": 1,
            "panels": panels,
            "time": {"from": "now-1h", "to": "now"},
            "refresh": "30s",
        }
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.write_json(p, dashboard)
        except Exception:
            p.write_text(json.dumps(dashboard, indent=2))
        return dashboard

    @staticmethod
    def _stat_panel(panel_id: int, title: str, metric: str, x: int, w: int) -> Dict:
        return {
            "id": panel_id, "type": "stat", "title": title,
            "gridPos": {"x": x, "y": 0, "w": w, "h": 4},
            "targets": [{"expr": metric, "refId": "A"}],
        }

    @staticmethod
    def _timeseries_panel(panel_id: int, title: str, metric: str, x: int, y: int, w: int, h: int) -> Dict:
        return {
            "id": panel_id, "type": "timeseries", "title": title,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "targets": [{"expr": f"rate({metric}[5m])", "refId": "A"}],
        }


# ── Collector — wires all subsystems ─────────────────────────────────────────

class TelemetryCollector:
    """
    Pulls metrics from all projectx subsystems and updates the registry.

    Usage::

        collector = TelemetryCollector()
        collector.start()   # background thread
        # or
        collector.collect() # one-shot
    """

    def __init__(
        self,
        registry: Optional[MetricsRegistry] = None,
        interval: int = 30,
        metrics_path: str = "projectx_logs/telemetry/metrics.txt",
    ) -> None:
        self._registry = registry or get_registry()
        self._interval = interval
        self._metrics_path = metrics_path
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._exporter = PrometheusExporter(self._registry)
        self._setup_metrics()

    def _setup_metrics(self) -> None:
        r = self._registry
        self.apo_best_score = r.gauge("apo_best_score", "Best APO candidate score")
        self.apo_steps = r.counter("apo_steps_total", "Total APO optimization steps")
        self.subsystem_calls = r.counter("subsystem_calls_total", "Total subsystem.run() calls")
        self.subsystem_errors = r.counter("subsystem_errors_total", "Subsystem errors")
        self.subsystem_latency = r.histogram("subsystem_latency_seconds", "Subsystem call latency")
        self.safety_events = r.counter("safety_events_total", "Safety monitor events")
        self.safety_estop = r.gauge("safety_emergency_stop", "1 if emergency stop active")
        self.resource_cpu = r.gauge("resource_cpu_percent", "CPU usage percent")
        self.resource_mem = r.gauge("resource_memory_percent", "Memory usage percent")
        self.resource_disk = r.gauge("resource_disk_percent", "Disk usage percent")
        self.resource_threads = r.gauge("resource_thread_count", "Active thread count")
        self.agents_active = r.gauge("agents_active", "Active spawned agents")
        self.learning_cycles = r.counter("learning_cycles_total", "MetaLearner cycles completed")
        self.evolution_score = r.gauge("evolution_score", "Latest evolution tracker score")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="telemetry-collector")
        self._thread.start()
        logger.info("TelemetryCollector started (interval=%ds)", self._interval)

    def stop(self) -> None:
        self._running = False

    def collect(self) -> None:
        """One-shot collection from all subsystems."""
        self._collect_resource()
        self._collect_safety()
        self._collect_agents()
        self._collect_evolution()
        self._exporter.write(self._metrics_path)

    def render(self) -> str:
        return self._exporter.render()

    # ── Collection methods ────────────────────────────────────────────────

    def _collect_resource(self) -> None:
        try:
            from simp.projectx.resource_monitor import get_resource_monitor
            mon = get_resource_monitor(auto_start=False)
            snap = mon.latest()
            if snap:
                self.resource_cpu.set(snap.cpu_percent)
                self.resource_mem.set(snap.memory_percent)
                self.resource_disk.set(snap.disk_percent)
                self.resource_threads.set(float(snap.thread_count))
        except Exception as exc:
            logger.debug("resource collect: %s", exc)

    def _collect_safety(self) -> None:
        try:
            from simp.projectx.safety_monitor import get_safety_monitor
            sm = get_safety_monitor()
            self.safety_estop.set(1.0 if sm.emergency_stopped else 0.0)
            summary = sm.get_summary() if hasattr(sm, "get_summary") else {}
            self.safety_events.inc(float(summary.get("new_alerts", 0)))
        except Exception as exc:
            logger.debug("safety collect: %s", exc)

    def _collect_agents(self) -> None:
        try:
            from simp.projectx.agent_spawner import get_agent_spawner
            spawner = get_agent_spawner()
            active = len([a for a in spawner.list_agents() if a.get("alive")])
            self.agents_active.set(float(active))
        except Exception as exc:
            logger.debug("agents collect: %s", exc)

    def _collect_evolution(self) -> None:
        try:
            from simp.projectx.evolution_tracker import get_evolution_tracker
            tracker = get_evolution_tracker()
            report = tracker.latest_report()
            if report:
                self.evolution_score.set(float(report.get("current_score", 0.0)))
        except Exception as exc:
            logger.debug("evolution collect: %s", exc)

    def _loop(self) -> None:
        while self._running:
            try:
                self.collect()
            except Exception as exc:
                logger.debug("TelemetryCollector loop error: %s", exc)
            time.sleep(self._interval)


# ── Module-level singletons ───────────────────────────────────────────────────

_registry: Optional[MetricsRegistry] = None
_collector: Optional[TelemetryCollector] = None


def get_registry() -> MetricsRegistry:
    global _registry
    if _registry is None:
        with _REGISTRY_LOCK:
            if _registry is None:           # double-check under lock
                _registry = MetricsRegistry()
    return _registry


def get_telemetry_collector(auto_start: bool = True) -> TelemetryCollector:
    global _collector
    if _collector is None:
        with _REGISTRY_LOCK:
            if _collector is None:          # double-check under lock
                _collector = TelemetryCollector(registry=get_registry())
                if auto_start:
                    _collector.start()
    return _collector
