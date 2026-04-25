"""
Tests for QuantumArbMetrics (T31)
Covers: metric registration, counter/gauge/histogram behavior,
Prometheus export, singleton, summary API.
"""

import os
import sys
import pytest
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simp.organs.quantumarb.observability_pipeline import (
    QuantumArbMetrics,
    Counter,
    Gauge,
    Histogram,
    get_metrics,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before each test."""
    QuantumArbMetrics.reset_instance()
    yield
    QuantumArbMetrics.reset_instance()


class TestSingleton:
    def test_get_instance_returns_same_instance(self):
        m1 = QuantumArbMetrics.get_instance()
        m2 = QuantumArbMetrics.get_instance()
        assert m1 is m2

    def test_get_metrics_alias_works(self):
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2


class TestCounter:
    def test_counter_starts_at_zero(self):
        c = Counter("test_counter", "test desc", {"label": "val"})
        assert c.value == 0.0

    def test_counter_inc_increments(self):
        c = Counter("test_counter", "test desc")
        c.inc()
        assert c.value == 1.0
        c.inc(5)
        assert c.value == 6.0


class TestGauge:
    def test_gauge_starts_at_zero(self):
        g = Gauge("test_gauge", "test desc")
        assert g.value == 0.0

    def test_gauge_set(self):
        g = Gauge("test_gauge", "test desc")
        g.set(42.5)
        assert g.value == 42.5

    def test_gauge_inc_dec(self):
        g = Gauge("test_gauge", "test desc")
        g.set(10.0)
        g.inc(3)
        assert g.value == 13.0
        g.dec(5)
        assert g.value == 8.0


class TestHistogram:
    def test_histogram_starts_empty(self):
        h = Histogram("test_hist", "test desc")
        stats = h.stats()
        assert stats["count"] == 0

    def test_histogram_observe_and_stats(self):
        h = Histogram("test_hist", "test desc")
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            h.observe(v)
        stats = h.stats()
        assert stats["count"] == 5
        assert stats["sum"] == 15.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["p50"] == 3.0
        assert stats["p95"] == 5.0

    def test_histogram_empty_stats(self):
        h = Histogram("test_hist", "test desc")
        stats = h.stats()
        assert stats["count"] == 0
        assert stats["mean"] == 0


class TestMetricMethods:
    def test_decisions_total(self):
        m = QuantumArbMetrics.get_instance()
        m.decisions_total("go")
        m.decisions_total("go")
        m.decisions_total("no_go")
        m.decisions_total("review", 3)
        assert m._decision_counters["go"] == 2
        assert m._decision_counters["no_go"] == 1
        assert m._decision_counters["review"] == 3

    def test_trades_executed(self):
        m = QuantumArbMetrics.get_instance()
        m.trades_executed("coinbase", "BTC", "buy")
        m.trades_executed("coinbase", "BTC", "buy")
        m.trades_executed("solana", "SOL", "sell")
        # Check via prometheus export
        output = m.export_prometheus()
        assert "quantumarb_trades_executed_total" in output

    def test_pnl_total(self):
        m = QuantumArbMetrics.get_instance()
        m.pnl_total("coinbase", "BTC", 10.5)
        m.pnl_total("coinbase", "BTC", -2.3)
        assert m._pnl_gauges["venue=coinbase,symbol=BTC"] == pytest.approx(8.2)

    def test_circuit_breaker_state(self):
        m = QuantumArbMetrics.get_instance()
        assert m._circuit_breaker_state == 0.0
        m.circuit_breaker_state(1)
        assert m._circuit_breaker_state == 1.0

    def test_regime_current(self):
        m = QuantumArbMetrics.get_instance()
        m.regime_current(3)
        assert m._regime_gauge == 3.0

    def test_execution_latency(self):
        m = QuantumArbMetrics.get_instance()
        m.execution_latency("coinbase", "leg_1", 12.5)
        m.execution_latency("coinbase", "leg_1", 18.3)
        key = "venue=coinbase,leg=leg_1"
        assert key in m._latency_histograms
        assert len(m._latency_histograms[key]) == 2

    def test_kelly_fraction(self):
        m = QuantumArbMetrics.get_instance()
        m.kelly_fraction("coinbase", 0.25)
        m.kelly_fraction("coinbase", 0.30)
        assert len(m._kelly_histograms["coinbase"]) == 2

    def test_decision_latency(self):
        m = QuantumArbMetrics.get_instance()
        m.decision_latency(5.0)
        m.decision_latency(10.0)
        h = m._histograms.get("decision_latency_ms")
        assert h is not None
        assert len(h._values) == 2

    def test_calibration_error(self):
        m = QuantumArbMetrics.get_instance()
        m.calibration_error("signal_momentum", 0.05)
        m.calibration_error("signal_mean_reversion", 0.12)
        assert m._calibration_errors["signal_momentum"] == 0.05

    def test_alerts_total(self):
        m = QuantumArbMetrics.get_instance()
        m.alerts_total("risk_limit", "warning")
        m.alerts_total("risk_limit", "warning")
        m.alerts_total("circuit_breaker", "critical")
        key = "type=risk_limit,severity=warning"
        assert m._alert_counters[key] == 2

    def test_spread_bps(self):
        m = QuantumArbMetrics.get_instance()
        m.spread_bps("cross_exchange", 15.5)
        m.spread_bps("cross_exchange", 22.3)
        assert len(m._spread_histograms["cross_exchange"]) == 2

    def test_open_positions(self):
        m = QuantumArbMetrics.get_instance()
        m.open_positions("coinbase", 3.0)
        m.open_positions("solana", 5.0)
        assert m._open_positions["coinbase"] == 3.0
        assert m._open_positions["solana"] == 5.0

    def test_rollbacks_total(self):
        m = QuantumArbMetrics.get_instance()
        m.rollbacks_total("leg_timeout")
        m.rollbacks_total("leg_timeout")
        m.rollbacks_total("insufficient_balance")
        assert hasattr(m, "_rollback_counters")
        assert m._rollback_counters["reason=leg_timeout"] == 2


class TestPrometheusExport:
    def test_export_contains_uptime(self):
        m = QuantumArbMetrics.get_instance()
        output = m.export_prometheus()
        assert "quantumarb_uptime_seconds" in output

    def test_export_contains_info_metric(self):
        m = QuantumArbMetrics.get_instance()
        output = m.export_prometheus()
        assert 'quantumarb_info' in output

    def test_export_contains_decisions(self):
        m = QuantumArbMetrics.get_instance()
        m.decisions_total("go")
        m.decisions_total("no_go")
        output = m.export_prometheus()
        assert 'decision="go"' in output
        assert 'decision="no_go"' in output

    def test_export_contains_pnl(self):
        m = QuantumArbMetrics.get_instance()
        m.pnl_total("coinbase", "BTC", 50.0)
        output = m.export_prometheus()
        assert "quantumarb_pnl_total_usd" in output

    def test_export_contains_circuit_breaker(self):
        m = QuantumArbMetrics.get_instance()
        m.circuit_breaker_state(0)
        output = m.export_prometheus()
        assert "quantumarb_circuit_breaker_state" in output

    def test_export_contains_latency_histogram(self):
        m = QuantumArbMetrics.get_instance()
        m.execution_latency("coinbase", "leg_1", 45.0)
        output = m.export_prometheus()
        assert "quantumarb_execution_latency_ms" in output

    def test_export_contains_kelly_histogram(self):
        m = QuantumArbMetrics.get_instance()
        m.kelly_fraction("coinbase", 0.25)
        output = m.export_prometheus()
        assert "quantumarb_kelly_fraction" in output

    def test_export_contains_spread_histogram(self):
        m = QuantumArbMetrics.get_instance()
        m.spread_bps("cross_exchange", 12.5)
        output = m.export_prometheus()
        assert "quantumarb_spread_bps" in output

    def test_export_contains_alerts(self):
        m = QuantumArbMetrics.get_instance()
        m.alerts_total("risk_limit", "warning")
        output = m.export_prometheus()
        assert "quantumarb_alerts_sent_total" in output

    def test_export_contains_regime(self):
        m = QuantumArbMetrics.get_instance()
        m.regime_current(2)
        output = m.export_prometheus()
        assert "quantumarb_regime_current" in output

    def test_export_contains_calibration_error(self):
        m = QuantumArbMetrics.get_instance()
        m.calibration_error("momentum", 0.05)
        output = m.export_prometheus()
        assert "quantumarb_calibration_error" in output

    def test_export_all_metrics_have_type_and_help(self):
        m = QuantumArbMetrics.get_instance()
        m.execution_latency("coinbase", "leg_1", 10.0)
        m.kelly_fraction("coinbase", 0.2)
        m.spread_bps("simple", 5.0)
        output = m.export_prometheus()
        # Every histogram should have TYPE and HELP
        assert output.count("# TYPE") >= 3
        assert output.count("# HELP") >= 2  # uptime and info at minimum


class TestSummary:
    def test_summary_has_all_fields(self):
        m = QuantumArbMetrics.get_instance()
        m.decisions_total("go")
        m.trades_executed("coinbase", "BTC", "buy")
        m.pnl_total("coinbase", "BTC", 10.0)
        m.circuit_breaker_state(0)
        m.regime_current(1)
        summary = m.get_summary()
        assert "decisions" in summary
        assert "trades" in summary
        assert "pnl" in summary
        assert "circuit_breaker" in summary
        assert "regime" in summary
        assert "uptime_seconds" in summary
        assert "timestamp" in summary

    def test_summary_timestamp_is_iso_format(self):
        m = QuantumArbMetrics.get_instance()
        summary = m.get_summary()
        ts = summary["timestamp"]
        # Should parse as ISO date
        from datetime import datetime
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed.year >= 2024


class TestGrafanaDashboard:
    def test_export_grafana_dashboard_returns_dict(self):
        m = QuantumArbMetrics.get_instance()
        dash = m.export_grafana_dashboard()
        assert isinstance(dash, dict)
        assert "panels" in dash
        assert "title" in dash

    def test_dashboard_has_all_panel_types(self):
        m = QuantumArbMetrics.get_instance()
        dash = m.export_grafana_dashboard()
        panel_titles = [p.get("title", "") for p in dash["panels"]]
        assert any("Decision Rate" in t for t in panel_titles)
        assert any("PnL" in t for t in panel_titles)
        assert any("Circuit Breaker" in t for t in panel_titles)
        assert any("Regime" in t for t in panel_titles)
        assert any("Latency" in t for t in panel_titles)
        assert any("Spread" in t for t in panel_titles)
        assert any("Trades Executed" in t for t in panel_titles)
        assert any("Alerts" in t for t in panel_titles)
        assert any("Calibration" in t for t in panel_titles)
        assert any("Kelly" in t for t in panel_titles)


class TestReset:
    def test_reset_clears_all_counters(self):
        m = QuantumArbMetrics.get_instance()
        m.decisions_total("go", 5)
        m.trades_executed("coinbase", "BTC", "buy")
        m.pnl_total("coinbase", "BTC", 100.0)
        m.reset()
        assert len(m._decision_counters) == 0
        assert len(m._trade_counters) == 0
        assert len(m._pnl_gauges) == 0

    def test_reset_resets_gauges(self):
        m = QuantumArbMetrics.get_instance()
        m.circuit_breaker_state(1)
        m.regime_current(3)
        m.reset()
        assert m._circuit_breaker_state == 0.0
        assert m._regime_gauge == 0.0

    def test_reset_resets_histograms(self):
        m = QuantumArbMetrics.get_instance()
        m.execution_latency("coinbase", "leg_1", 50.0)
        m.kelly_fraction("coinbase", 0.25)
        m.reset()
        assert len(m._latency_histograms) == 0
        assert len(m._kelly_histograms) == 0


class TestThreadSafety:
    def test_concurrent_increments(self):
        m = QuantumArbMetrics.get_instance()
        results = []

        def inc_decisions(n: int):
            for _ in range(100):
                m.decisions_total("go")

        threads = [threading.Thread(target=inc_decisions, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert m._decision_counters["go"] == 500

    def test_concurrent_pnl_updates(self):
        m = QuantumArbMetrics.get_instance()

        def update_pnl():
            for _ in range(50):
                m.pnl_total("coinbase", "BTC", 1.0)

        threads = [threading.Thread(target=update_pnl) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert m._pnl_gauges["venue=coinbase,symbol=BTC"] == 200.0
