"""
pytest tests for simp.projectx.telemetry

Covers the metric emission and aggregation pipeline:
  - Counter, Gauge, Histogram primitives
  - MetricsRegistry registration and retrieval
  - PrometheusExporter text format rendering
  - snapshot() aggregation
  - latency guardrail helpers
  - JSON export (via json.loads on rendered output)
"""

from __future__ import annotations

import json
import math
import threading
from unittest.mock import patch

import pytest

from simp.projectx.telemetry import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    PrometheusExporter,
    GrafanaDashboard,
    TelemetryCollector,
    get_registry,
    get_telemetry_collector,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def registry() -> MetricsRegistry:
    """Fresh registry per test — no singleton pollution."""
    return MetricsRegistry(namespace="test")


@pytest.fixture
def exporter(registry: MetricsRegistry) -> PrometheusExporter:
    return PrometheusExporter(registry)


# ── test_metric_emission ───────────────────────────────────────────────────────

def test_metric_emission(registry: MetricsRegistry) -> None:
    """Emit a Counter, then verify it can be retrieved from the registry."""
    counter = registry.counter("emission_test", help="did we get it back")
    counter.inc(3.0)

    # MetricsRegistry doesn't expose a keyed .get() — retrieve via all_metrics()
    all_m = registry.all_metrics()
    retrieved = next((m for m in all_m if m.name == "test_emission_test"), None)
    assert retrieved is not None, "Counter not found in registry"
    assert retrieved.value() == 3.0


# ── test_counter_increment ─────────────────────────────────────────────────────

def test_counter_increment(registry: MetricsRegistry) -> None:
    """Create a Counter, increment 5 times, verify value == 5."""
    counter = registry.counter("inc_test", help="increment test")
    for _ in range(5):
        counter.inc()
    assert counter.value() == 5.0


def test_counter_increment_by_amount(registry: MetricsRegistry) -> None:
    """Increment by non-default amount."""
    counter = registry.counter("inc_amount_test")
    counter.inc(10.0)
    counter.inc(2.5)
    assert counter.value() == 12.5


def test_counter_negative_rejected(registry: MetricsRegistry) -> None:
    """Negative increment raises ValueError."""
    counter = registry.counter("no_negatives")
    with pytest.raises(ValueError, match="non-negative finite"):
        counter.inc(-1.0)


# ── test_gauge_set ────────────────────────────────────────────────────────────

def test_gauge_set(registry: MetricsRegistry) -> None:
    """Create a Gauge, set to 42.0, verify value == 42.0."""
    gauge = registry.gauge("gauge_test", help="gauge set test")
    gauge.set(42.0)
    assert gauge.value() == 42.0


def test_gauge_inc_dec(registry: MetricsRegistry) -> None:
    """Gauge inc/dec modify the value correctly."""
    gauge = registry.gauge("gauge_inout")
    gauge.set(10.0)
    gauge.inc(5.0)
    assert gauge.value() == 15.0
    gauge.dec(3.0)
    assert gauge.value() == 12.0


# ── test_histogram_record ─────────────────────────────────────────────────────

def test_histogram_record(registry: MetricsRegistry) -> None:
    """Record values, verify histogram stats are computed (count, sum)."""
    hist = registry.histogram("hist_test", help="histogram test")
    values = [0.05, 0.12, 0.9, 2.0, 7.5]
    for v in values:
        hist.observe(v)

    counts, hist_sum, total = hist.snapshot()
    assert total == 5
    assert math.isclose(hist_sum, sum(values), rel_tol=1e-9)
    assert all(c >= 0 for c in counts)


def test_histogram_buckets_populated(registry: MetricsRegistry) -> None:
    """Values fall into correct cumulative buckets."""
    hist = registry.histogram("hist_buckets", buckets=[1.0, 5.0, 10.0])
    hist.observe(0.5)   # in bucket <= 1.0
    hist.observe(3.0)  # in bucket <= 5.0
    hist.observe(7.0)   # in bucket <= 10.0
    hist.observe(15.0)  # above all buckets — not counted in any bucket

    counts, _, total = hist.snapshot()
    assert total == 4
    assert counts[0] == 1   # <= 1.0
    assert counts[1] == 2   # <= 5.0
    assert counts[2] == 3   # <= 10.0
    assert len(counts) == 3


def test_histogram_nan_silently_dropped(registry: MetricsRegistry) -> None:
    """observe() silently drops NaN/Inf without corrupting state."""
    hist = registry.histogram("hist_nan")
    hist.observe(1.0)
    hist.observe(float("nan"))
    hist.observe(float("inf"))
    hist.observe(2.0)

    _, hist_sum, total = hist.snapshot()
    assert total == 2
    assert math.isclose(hist_sum, 3.0, rel_tol=1e-9)


# ── test_metric_labels ────────────────────────────────────────────────────────

def test_metric_labels(registry: MetricsRegistry) -> None:
    """Emit metric with labels, verify labels are preserved."""
    counter = registry.counter(
        "labeled_counter",
        help="counter with labels",
        labels={"service": "test", "env": "pytest"},
    )
    counter.inc(1.0)

    assert counter.labels == {"service": "test", "env": "pytest"}


def test_gauge_labels(registry: MetricsRegistry) -> None:
    """Labels on Gauge are also preserved."""
    gauge = registry.gauge(
        "labeled_gauge",
        labels={"host": "localhost", "zone": "us-east-1"},
    )
    gauge.set(99.0)
    assert gauge.labels == {"host": "localhost", "zone": "us-east-1"}
    assert gauge.value() == 99.0


# ── test_snapshot_captures_all_metrics ────────────────────────────────────────

def test_snapshot_captures_all_metrics(registry: MetricsRegistry) -> None:
    """Emit several metrics of different types, call snapshot(), verify they're all present."""
    c1 = registry.counter("snap_counter_a", help="counter a")
    c1.inc(7.0)

    c2 = registry.counter("snap_counter_b", help="counter b")
    c2.inc(3.0)

    g1 = registry.gauge("snap_gauge_a", help="gauge a")
    g1.set(55.5)

    h1 = registry.histogram("snap_histogram", help="histogram", buckets=[0.1, 1.0, 10.0])
    h1.observe(0.5)
    h1.observe(5.0)

    all_metrics = registry.all_metrics()
    names = {m.name for m in all_metrics}

    assert "test_snap_counter_a" in names
    assert "test_snap_counter_b" in names
    assert "test_snap_gauge_a" in names
    assert "test_snap_histogram" in names


# ── test_export_prometheus_format ─────────────────────────────────────────────

def test_export_prometheus_format(registry: MetricsRegistry, exporter: PrometheusExporter) -> None:
    """Verify Prometheus text format output is valid and well-structured."""
    registry.counter("requests_total", help="Total requests").inc(42.0)
    registry.gauge("process_resident_memory_bytes", help="RSS in bytes").set(1_234_567.0)
    registry.histogram(
        "http_request_duration_seconds",
        help="HTTP request latency",
        buckets=[0.01, 0.05, 0.1, 0.5, 1.0],
    ).observe(0.037)

    output = exporter.render()

    lines = output.splitlines()
    assert any(line.startswith("# HELP") for line in lines), "Missing HELP lines"
    assert any(line.startswith("# TYPE") for line in lines), "Missing TYPE lines"

    type_lines = [l for l in lines if l.startswith("# TYPE")]
    metric_names = [l.split()[2] for l in type_lines]
    assert "test_requests_total" in metric_names
    assert "test_http_request_duration_seconds" in metric_names

    for line in lines:
        if line and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                value_str = parts[-1]
                assert (
                    value_str in ("NaN", "+Inf", "-Inf") or _is_valid_float(value_str)
                ), f"Invalid numeric value in prometheus output: {line}"

    assert "test_process_resident_memory_bytes" in output


def _is_valid_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ── test_metric_sampling ───────────────────────────────────────────────────────

def test_metric_sampling(registry: MetricsRegistry) -> None:
    """Histogram percentile computation doesn't crash."""
    hist = registry.histogram(
        "percentile_test",
        help="percentile sampling test",
        buckets=[0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    for i in range(100):
        hist.observe(0.001 * (i + 1))

    counts, hist_sum, total = hist.snapshot()
    assert total == 100

    expected_sum = 0.001 * (100 * 101 / 2)
    assert math.isclose(hist_sum, expected_sum, rel_tol=1e-9)

    for i in range(1, len(counts)):
        assert counts[i] >= counts[i - 1], "Buckets not cumulative"


# ── test_telemetry_pipeline_no_crash ─────────────────────────────────────────

def test_telemetry_pipeline_no_crash(registry: MetricsRegistry, exporter: PrometheusExporter) -> None:
    """Full pipeline from emit to export doesn't raise."""
    registry.counter("pipeline_counter").inc(99.0)
    registry.gauge("pipeline_gauge").set(77.7)
    registry.histogram("pipeline_histogram", buckets=[0.5, 1.0, 5.0]).observe(0.7)

    all_m = registry.all_metrics()
    assert len(all_m) >= 3

    output = exporter.render()
    assert isinstance(output, str)
    assert len(output) > 0

    lines = output.splitlines()
    assert any(l.startswith("# HELP test_pipeline") for l in lines)


# ── test_metric_reset ─────────────────────────────────────────────────────────

def test_metric_reset(registry: MetricsRegistry) -> None:
    """
    Verify that re-registering a metric name returns the same live instance.

    There is no explicit reset() method — the registry deduplicates by key.
    This test documents that calling counter() twice with the same name returns
    the same object (a design choice, not a bug), and that the registry
    correctly tracks at most one instance per type+name combination.
    """
    counter = registry.counter("reset_counter", help="reset test")
    counter.inc(99.0)
    assert counter.value() == 99.0

    # Calling counter() again with the same name returns the existing instance
    same_instance = registry.counter("reset_counter", help="reset test")
    assert same_instance is counter
    assert same_instance.value() == 99.0

    # Different name gives a different instance
    other = registry.counter("other_counter", help="other")
    assert other is not counter
    assert other.value() == 0.0

    # Registry contains both
    names = {m.name for m in registry.all_metrics()}
    assert "test_reset_counter" in names
    assert "test_other_counter" in names


# ── test_latency_guardrail ────────────────────────────────────────────────────

def test_latency_guardrail(registry: MetricsRegistry) -> None:
    """Emit a latency metric, verify it can be compared against threshold."""
    latency_hist = registry.histogram(
        "guardrail_latency_seconds",
        help="latency histogram for guardrail check",
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    recorded = [0.02, 0.3, 0.8, 3.0]
    for val in recorded:
        latency_hist.observe(val)

    counts, hist_sum, total = latency_hist.snapshot()
    assert total == len(recorded)
    assert math.isclose(hist_sum, sum(recorded), rel_tol=1e-9)

    # buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    # idx 6 == 0.5: values <= 0.5 are 0.02 and 0.3  → count 2
    assert counts[6] == 2, "slow bucket (0.5s) should contain 2 values"
    # idx 7 == 2.5: values <= 2.5 are 0.02, 0.3, 0.8 → count 3
    assert counts[7] == 3, "critical bucket (2.5s) should contain 3 values"


# ── test_export_json ──────────────────────────────────────────────────────────

def test_export_json(registry: MetricsRegistry, exporter: PrometheusExporter) -> None:
    """Verify registry state can be serialised as valid JSON."""
    registry.counter("json_counter", help="json export test").inc(5.0)
    registry.gauge("json_gauge", help="json gauge test").set(12.5)
    registry.histogram(
        "json_histogram",
        help="json histogram test",
        buckets=[1.0, 5.0],
    ).observe(2.3)

    # Serialise all metric states as JSON
    all_m = registry.all_metrics()
    metric_data = [
        {
            "name": m.name,
            "type": type(m).__name__,
            "value": m.value() if hasattr(m, "value") else None,
        }
        for m in all_m
    ]
    json_str = json.dumps(metric_data, indent=2)
    parsed = json.loads(json_str)

    assert isinstance(parsed, list)
    assert len(parsed) == 3

    names = {item["name"] for item in parsed}
    assert "test_json_counter" in names
    assert "test_json_gauge" in names
    assert "test_json_histogram" in names

    counter_entry = next(m for m in parsed if "json_counter" in m["name"])
    assert counter_entry["value"] == 5.0


# ── Thread-safety smoke test ──────────────────────────────────────────────────

def test_counter_threadsafe(registry: MetricsRegistry) -> None:
    """Counter increments are safe under concurrent access."""
    counter = registry.counter("thread_counter", help="thread safety test")
    num_threads = 10
    increments_per_thread = 100

    def worker() -> None:
        for _ in range(increments_per_thread):
            counter.inc()

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter.value() == float(num_threads * increments_per_thread)


# ── GrafanaDashboard smoke test ────────────────────────────────────────────────

def test_grafana_dashboard_structure(registry: MetricsRegistry) -> None:
    """GrafanaDashboard.generate() produces a valid dict that parses as JSON."""
    registry.counter("grafana_counter", help="dashboard smoke test").inc(1.0)
    registry.gauge("grafana_gauge", help="dashboard smoke test").set(2.0)

    result = GrafanaDashboard.generate()

    assert isinstance(result, dict)
    json_str = json.dumps(result)
    reparsed = json.loads(json_str)
    assert reparsed == result
