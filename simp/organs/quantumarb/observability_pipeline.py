"""
Unified Observability Pipeline — T31
====================================
All quantumarb metrics in one place: Prometheus-compatible exposition format,
Grafana dashboard JSON, structured JSON logging.

Metrics:
  quantumarb_decisions_total{decision}
  quantumarb_trades_executed_total{venue,symbol,side}
  quantumarb_pnl_total_usd{venue,symbol}
  quantumarb_spread_bps{arb_type}
  quantumarb_circuit_breaker_state
  quantumarb_execution_latency_ms{venue,leg}
  quantumarb_confidence_calibration_error{signal_type}
  quantumarb_regime_current
  quantumarb_position_size_kelly_fraction{venue}

Usage:
    m = QuantumArbMetrics.get_instance()
    m.decisions_total(decision="go")
    m.trades_executed(venue="coinbase", symbol="BTC", side="buy")
    m.pnl_total(venue="coinbase", symbol="BTC", pnl=0.50)
    m.circuit_breaker_state(state=0)
    m.execution_latency(venue="coinbase", leg="leg_1", ms=45.3)
    print(m.export_prometheus())
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("observability")

# ── Metric types ───────────────────────────────────────────────────────────

MetricType_COUNTER = "counter"
MetricType_GAUGE = "gauge"
MetricType_HISTOGRAM = "histogram"


@dataclass
class Metric:
    name: str
    type: str
    description: str
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Counter(Metric):
    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        super().__init__(name=name, type=MetricType_COUNTER, description=description, labels=labels or {})
        self._value = 0.0

    def inc(self, amount: float = 1.0) -> None:
        self._value += amount

    @property
    def value(self) -> float:
        return self._value


@dataclass
class Gauge(Metric):
    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        super().__init__(name=name, type=MetricType_GAUGE, description=description, labels=labels or {})
        self._value = 0.0

    def set(self, value: float) -> None:
        self._value = value

    def inc(self, amount: float = 1.0) -> None:
        self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        self._value -= amount

    @property
    def value(self) -> float:
        return self._value


@dataclass
class Histogram(Metric):
    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ):
        super().__init__(
            name=name,
            type=MetricType_HISTOGRAM,
            description=description,
            labels=labels or {},
        )
        self._values: List[float] = []
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def observe(self, value: float) -> None:
        self._values.append(value)

    def stats(self) -> Dict[str, float]:
        if not self._values:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0, "mean": 0}
        sorted_vals = sorted(self._values)
        n = len(sorted_vals)
        return {
            "count": n,
            "sum": sum(sorted_vals),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": sorted_vals[int(n * 0.50)],
            "p95": sorted_vals[min(int(n * 0.95), n - 1)],
            "p99": sorted_vals[min(int(n * 0.99), n - 1)],
            "mean": sum(sorted_vals) / n,
        }


class QuantumArbMetrics:
    """
    Singleton metrics registry for all quantumarb metrics.

    Thread-safe. All counters/histograms support per-label tracking.
    """

    _instance: Optional["QuantumArbMetrics"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock2 = threading.Lock()
        self._start_time = time.time()

        # Per-label tracking (label_key → value)
        self._decision_counters: Dict[str, float] = {}
        self._trade_counters: Dict[str, float] = {}
        self._pnl_gauges: Dict[str, float] = {}
        self._latency_histograms: Dict[str, List[float]] = {}
        self._kelly_histograms: Dict[str, List[float]] = {}
        self._spread_histograms: Dict[str, List[float]] = {}
        self._calibration_errors: Dict[str, float] = {}
        self._alert_counters: Dict[str, float] = {}
        self._regime_gauge: float = 0.0
        self._circuit_breaker_state: float = 0.0
        self._open_positions: Dict[str, float] = {}

    @classmethod
    def get_instance(cls) -> "QuantumArbMetrics":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance._register_defaults()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance = None

    def _label_key(self, base: str, labels: Dict[str, str]) -> str:
        if not labels:
            return base
        parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return f"{base}{{{','.join(parts)}}}"

    def _register_counter(self, name: str, description: str, label_names: List[str]) -> None:
        labels = {k: "" for k in label_names}
        self._counters[name] = Counter(name=name, description=description, labels=labels)

    def _register_gauge(self, name: str, description: str, label_names: List[str]) -> None:
        labels = {k: "" for k in label_names}
        self._gauges[name] = Gauge(name=name, description=description, labels=labels)

    def _register_histogram(
        self, name: str, description: str, label_names: List[str]
    ) -> None:
        labels = {k: "" for k in label_names}
        self._histograms[name] = Histogram(name=name, description=description, labels=labels)

    def _register_defaults(self) -> None:
        """Register all standard metrics."""
        self._register_counter("decisions_total", "Total decisions by outcome", ["decision"])
        self._register_counter("trades_executed_total", "Total trades executed", ["venue", "symbol", "side"])
        self._register_counter("alerts_sent_total", "Total alerts sent", ["alert_type", "severity"])
        self._register_counter("rollbacks_total", "Total rollback events", ["reason"])
        self._register_counter("open_positions", "Open positions", ["venue"])

        self._register_gauge("pnl_total_usd", "Total PnL in USD", ["venue", "symbol"])
        self._register_gauge("circuit_breaker_state", "Circuit breaker (0=closed, 1=open)", [])
        self._register_gauge("regime_current", "Current market regime code", [])
        self._register_gauge("calibration_error", "Confidence calibration error", ["signal_type"])

        self._register_histogram("spread_bps", "Spread in basis points", ["arb_type"])
        self._register_histogram("execution_latency_ms", "Execution latency in ms", ["venue", "leg"])
        self._register_histogram("kelly_fraction", "Kelly fraction used", ["venue"])
        self._register_histogram("decision_latency_ms", "Decision latency in ms", [])

    # ── Convenience methods ─────────────────────────────────────────────────

    def decisions_total(self, decision: str, amount: float = 1.0) -> None:
        with self._lock2:
            self._decision_counters[decision] = self._decision_counters.get(decision, 0) + amount

    def trades_executed(self, venue: str, symbol: str, side: str) -> None:
        with self._lock2:
            key = f"venue={venue},symbol={symbol},side={side}"
            self._trade_counters[key] = self._trade_counters.get(key, 0) + 1

    def pnl_total(self, venue: str, symbol: str, pnl: float) -> None:
        with self._lock2:
            key = f"venue={venue},symbol={symbol}"
            self._pnl_gauges[key] = self._pnl_gauges.get(key, 0) + pnl

    def circuit_breaker_state(self, state: int) -> None:
        with self._lock2:
            self._circuit_breaker_state = float(state)

    def regime_current(self, regime_code: int) -> None:
        with self._lock2:
            self._regime_gauge = float(regime_code)

    def execution_latency(self, venue: str, leg: str, ms: float) -> None:
        with self._lock2:
            key = f"venue={venue},leg={leg}"
            self._latency_histograms.setdefault(key, []).append(ms)

    def kelly_fraction(self, venue: str, fraction: float) -> None:
        with self._lock2:
            self._kelly_histograms.setdefault(venue, []).append(fraction)

    def decision_latency(self, ms: float) -> None:
        h = self._histograms.get("decision_latency_ms")
        if h:
            h.observe(ms)

    def calibration_error(self, signal_type: str, error: float) -> None:
        with self._lock2:
            self._calibration_errors[signal_type] = error

    def alerts_total(self, alert_type: str, severity: str) -> None:
        with self._lock2:
            key = f"type={alert_type},severity={severity}"
            self._alert_counters[key] = self._alert_counters.get(key, 0) + 1

    def spread_bps(self, arb_type: str, bps: float) -> None:
        with self._lock2:
            self._spread_histograms.setdefault(arb_type, []).append(bps)

    def open_positions(self, venue: str, count: float) -> None:
        with self._lock2:
            self._open_positions[venue] = count

    def rollbacks_total(self, reason: str) -> None:
        with self._lock2:
            key = f"reason={reason}"
            # Uses _decision_counters dict for rollbacks
            if not hasattr(self, "_rollback_counters"):
                self._rollback_counters: Dict[str, float] = {}
            self._rollback_counters[key] = self._rollback_counters.get(key, 0) + 1

    # ── Export: Prometheus text format ──────────────────────────────────────

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text exposition format."""
        lines: List[str] = [
            f"# HELP quantumarb_uptime_seconds Uptime in seconds",
            f"# TYPE quantumarb_uptime_seconds gauge",
            f"quantumarb_uptime_seconds {time.time() - self._start_time:.2f}",
            f"",
            f"# HELP quantumarb_info Info metric",
            f"# TYPE quantumarb_info gauge",
            f'quantumarb_info{{version="1.0.0"}} 1',
            f"",
        ]

        # Decision counters
        with self._lock2:
            for decision, val in sorted(self._decision_counters.items()):
                lines.append(f'quantumarb_decisions_total{{decision="{decision}"}} {val}')
        lines.append("")

        # Trade counters
        with self._lock2:
            for key, val in sorted(self._trade_counters.items()):
                # key format: venue=X,symbol=Y,side=Z
                label_str = key
                lines.append(f"quantumarb_trades_executed_total{{{label_str}}} {val}")
        lines.append("")

        # PnL gauges
        with self._lock2:
            for key, val in sorted(self._pnl_gauges.items()):
                label_str = key
                lines.append(f"quantumarb_pnl_total_usd{{{label_str}}} {val:.6f}")
        lines.append("")

        # Alerts counters
        with self._lock2:
            for key, val in sorted(self._alert_counters.items()):
                label_str = key
                lines.append(f"quantumarb_alerts_sent_total{{{label_str}}} {val}")
        lines.append("")

        # Rollbacks counters
        if hasattr(self, "_rollback_counters"):
            with self._lock2:
                for key, val in sorted(self._rollback_counters.items()):
                    label_str = key
                    lines.append(f"quantumarb_rollbacks_total{{{label_str}}} {val}")
            lines.append("")

        # Open positions
        with self._lock2:
            for venue, count in sorted(self._open_positions.items()):
                lines.append(f'quantumarb_open_positions{{venue="{venue}"}} {count}')
        lines.append("")

        # Circuit breaker
        with self._lock2:
            lines.append(f"quantumarb_circuit_breaker_state {self._circuit_breaker_state:.0f}")

        # Regime
        with self._lock2:
            lines.append(f"quantumarb_regime_current {self._regime_gauge:.0f}")
        lines.append("")

        # Calibration errors
        with self._lock2:
            for signal_type, error in sorted(self._calibration_errors.items()):
                lines.append(f'quantumarb_calibration_error{{signal_type="{signal_type}"}} {error:.6f}')
        lines.append("")

        # Latency histograms
        with self._lock2:
            for key, vals in sorted(self._latency_histograms.items()):
                if not vals:
                    continue
                label_str = key
                sorted_vals = sorted(vals)
                n = len(sorted_vals)
                lines.append(f"# TYPE quantumarb_execution_latency_ms histogram")
                for pct_name, pct_val in [("0.5", 0.5), ("0.95", 0.95), ("0.99", 0.99)]:
                    idx = min(int(n * pct_val), n - 1)
                    v = sorted_vals[idx]
                    lines.append(
                        f'quantumarb_execution_latency_ms{{{label_str},quantile="{pct_name}"}} {v:.2f}'
                    )
                lines.append(f"quantumarb_execution_latency_ms_sum{{{label_str}}} {sum(vals):.2f}")
                lines.append(f"quantumarb_execution_latency_ms_count{{{label_str}}} {n}")
                lines.append("")
            # Kelly histograms
            for venue, vals in sorted(self._kelly_histograms.items()):
                if not vals:
                    continue
                sorted_vals = sorted(vals)
                n = len(sorted_vals)
                lines.append(f"# TYPE quantumarb_kelly_fraction histogram")
                for pct_name, pct_val in [("0.5", 0.5), ("0.95", 0.95), ("0.99", 0.99)]:
                    idx = min(int(n * pct_val), n - 1)
                    v = sorted_vals[idx]
                    lines.append(f'quantumarb_kelly_fraction{{venue="{venue}",quantile="{pct_name}"}} {v:.4f}')
                lines.append(f"quantumarb_kelly_fraction_sum{{venue=\"{venue}\"}} {sum(vals):.4f}")
                lines.append(f"quantumarb_kelly_fraction_count{{venue=\"{venue}\"}} {n}")
                lines.append("")
            # Spread histograms
            for arb_type, vals in sorted(self._spread_histograms.items()):
                if not vals:
                    continue
                sorted_vals = sorted(vals)
                n = len(sorted_vals)
                lines.append(f"# TYPE quantumarb_spread_bps histogram")
                for pct_name, pct_val in [("0.5", 0.5), ("0.95", 0.95), ("0.99", 0.99)]:
                    idx = min(int(n * pct_val), n - 1)
                    v = sorted_vals[idx]
                    lines.append(f'quantumarb_spread_bps{{arb_type="{arb_type}",quantile="{pct_name}"}} {v:.2f}')
                lines.append(f"quantumarb_spread_bps_sum{{arb_type=\"{arb_type}\"}} {sum(vals):.2f}")
                lines.append(f"quantumarb_spread_bps_count{{arb_type=\"{arb_type}\"}} {n}")
                lines.append("")

        return "\n".join(lines)

    def get_summary(self) -> Dict[str, Any]:
        """Get all metrics as a dict for dashboard API."""
        with self._lock2:
            return {
                "decisions": dict(self._decision_counters),
                "trades": dict(self._trade_counters),
                "pnl": dict(self._pnl_gauges),
                "alerts": dict(self._alert_counters),
                "rollbacks": dict(getattr(self, "_rollback_counters", {})),
                "circuit_breaker": self._circuit_breaker_state,
                "regime": self._regime_gauge,
                "calibration_errors": dict(self._calibration_errors),
                "open_positions": dict(self._open_positions),
                "uptime_seconds": time.time() - self._start_time,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock2:
            self._decision_counters.clear()
            self._trade_counters.clear()
            self._pnl_gauges.clear()
            self._latency_histograms.clear()
            self._kelly_histograms.clear()
            self._spread_histograms.clear()
            self._calibration_errors.clear()
            self._alert_counters.clear()
            self._regime_gauge = 0.0
            self._circuit_breaker_state = 0.0
            self._open_positions.clear()
            if hasattr(self, "_rollback_counters"):
                self._rollback_counters.clear()
            self._start_time = time.time()

    # ── Grafana JSON dashboard export ──────────────────────────────────────

    def export_grafana_dashboard(self, title: str = "QuantumArb Dashboard") -> Dict[str, Any]:
        """Generate a Grafana dashboard JSON for all tracked metrics."""
        dashboard: Dict[str, Any] = {
            "title": title,
            "tags": ["quantumarb", "trading"],
            "timezone": "browser",
            "refresh": "5s",
            "panels": [],
            "schemaVersion": 30,
            "version": 1,
        }
        panels = dashboard["panels"]

        # Decision rate panel
        panels.append({
            "title": "Decision Rate (go/no_go/review)",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            "targets": [
                {
                    "expr": 'sum(rate(quantumarb_decisions_total[5m])) by (decision)',
                    "legendFormat": "{{decision}}",
                    "refId": "A",
                }
            ],
        })

        # PnL panel
        panels.append({
            "title": "Total PnL by Venue",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            "targets": [
                {
                    "expr": 'quantumarb_pnl_total_usd',
                    "legendFormat": "{{venue}} / {{symbol}}",
                    "refId": "A",
                }
            ],
        })

        # Circuit breaker state
        panels.append({
            "title": "Circuit Breaker State",
            "type": "stat",
            "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8},
            "targets": [{"expr": "quantumarb_circuit_breaker_state", "refId": "A"}],
            "options": {"colorMode": "value", " thresholdsMode": "absolute"},
            "fieldConfig": {
                "defaults": {
                    "mappings": [{"type": "value", "options": {"0": {"text": "CLOSED", "color": "green"}, "1": {"text": "OPEN", "color": "red"}}}],
                    "thresholds": {"mode": "absolute", "steps": [{"value": 0, "color": "green"}, {"value": 1, "color": "red"}]},
                }
            },
        })

        # Current regime
        panels.append({
            "title": "Market Regime",
            "type": "stat",
            "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8},
            "targets": [{"expr": "quantumarb_regime_current", "refId": "A"}],
            "options": {"colorMode": "value"},
        })

        # Execution latency
        panels.append({
            "title": "Execution Latency (ms) — p50/p95/p99",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
            "targets": [
                {"expr": 'quantumarb_execution_latency_ms{quantile="0.5"}', "legendFormat": "p50", "refId": "A"},
                {"expr": 'quantumarb_execution_latency_ms{quantile="0.95"}', "legendFormat": "p95", "refId": "B"},
                {"expr": 'quantumarb_execution_latency_ms{quantile="0.99"}', "legendFormat": "p99", "refId": "C"},
            ],
        })

        # Spread distribution
        panels.append({
            "title": "Spread Distribution (bps)",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
            "targets": [
                {"expr": 'histogram_quantile(0.95, sum(rate(quantumarb_spread_bps_bucket[5m])) by (le, arb_type))', "legendFormat": "{{arb_type}}", "refId": "A"}
            ],
        })

        # Trade execution rate
        panels.append({
            "title": "Trades Executed Rate",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 20},
            "targets": [
                {"expr": 'sum(rate(quantumarb_trades_executed_total[1m])) by (venue, symbol, side)', "legendFormat": "{{venue}} {{symbol}} {{side}}", "refId": "A"}
            ],
        })

        # Alert rate
        panels.append({
            "title": "Alerts Sent by Type",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 20},
            "targets": [
                {"expr": 'sum(rate(quantumarb_alerts_sent_total[5m])) by (alert_type, severity)', "legendFormat": "{{alert_type}} ({{severity}})", "refId": "A"}
            ],
        })

        # Calibration error
        panels.append({
            "title": "Calibration Error by Signal Type",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 28},
            "targets": [
                {"expr": 'quantumarb_calibration_error', "legendFormat": "{{signal_type}}", "refId": "A"}
            ],
        })

        # Kelly fraction
        panels.append({
            "title": "Kelly Fraction Distribution",
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 28},
            "targets": [
                {"expr": 'histogram_quantile(0.95, sum(rate(quantumarb_kelly_fraction_bucket[5m])) by (le, venue))', "legendFormat": "{{venue}}", "refId": "A"}
            ],
        })

        return dashboard


def get_metrics() -> QuantumArbMetrics:
    """Get the global QuantumArbMetrics singleton."""
    return QuantumArbMetrics.get_instance()
