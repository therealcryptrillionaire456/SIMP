"""
Tests for Sprint 14 — Path Telemetry.

Covers:
  - Appending records and reading summary
  - Threading safety (50 concurrent appends)
  - ``make_telemetry_block`` shape
  - Persistence across collector restart (reload_from_jsonl)
  - Rolling window behavior (last 100, last 1000)
  - Empty collector returns empty summary
"""

import json
import os
import threading
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from simp.telemetry.path_telemetry import (
    INVOCATION_MODES,
    PathTelemetryCollector,
    PathTelemetryRecord,
    path_telemetry,
    make_telemetry_block,
)

_BRIDGE_MODES = {"mcp_bridge", "external_bridge"}
_NATIVE_MODES = {"native", "mesh_native", "http_native"}


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def collector():
    """Return a fresh collector backed by a temporary JSONL file."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_path = tmp.name
    col = PathTelemetryCollector(jsonl_path=tmp_path)
    yield col
    col.reset()
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


# ======================================================================
# PathTelemetryRecord
# ======================================================================


class TestPathTelemetryRecord:
    def test_to_dict(self):
        rec = PathTelemetryRecord(
            invocation_mode="native",
            agent_id="quantumarb",
            tool_name="detect_arb",
            latency_ms=42.5,
            success=True,
        )
        d = rec.to_dict()
        assert d["invocation_mode"] == "native"
        assert d["agent_id"] == "quantumarb"
        assert d["tool_name"] == "detect_arb"
        assert d["latency_ms"] == 42.5
        assert d["success"] is True
        assert "timestamp" in d

    def test_auto_timestamp(self):
        rec = PathTelemetryRecord(
            invocation_mode="native", agent_id="a", tool_name="t", latency_ms=1.0, success=True
        )
        assert "T" in rec.timestamp  # ISO8601


# ======================================================================
# Append & GetSummary — happy path
# ======================================================================


class TestAppendAndSummary:
    def test_single_append_native(self, collector):
        collector.append("native", "quantumarb", "scan", 12.3, True)
        summary = collector.get_summary()
        assert summary["native_count"] == 1
        assert summary["bridged_count"] == 0
        assert summary["count_by_agent"] == {"quantumarb": 1}
        assert summary["count_by_mode"] == {"native": 1}

    def test_single_append_bridged(self, collector):
        collector.append("mcp_bridge", "gemma4", "plan", 55.0, True)
        summary = collector.get_summary()
        assert summary["native_count"] == 0
        assert summary["bridged_count"] == 1
        assert summary["count_by_agent"] == {"gemma4": 1}
        assert summary["count_by_mode"] == {"mcp_bridge": 1}

    def test_multiple_modes(self, collector):
        collector.append("native", "agent_a", "t1", 10.0, True)
        collector.append("http_native", "agent_b", "t2", 20.0, True)
        collector.append("mcp_bridge", "agent_c", "t3", 30.0, True)
        collector.append("external_bridge", "agent_d", "t4", 40.0, True)
        summary = collector.get_summary()
        assert summary["native_count"] == 2
        assert summary["bridged_count"] == 2
        assert summary["count_by_agent"] == {"agent_a": 1, "agent_b": 1, "agent_c": 1, "agent_d": 1}

    def test_unknown_mode_logged_as_unknown(self, collector):
        collector.append("unknown_mode_xyz", "agent_x", "tool", 5.0, True)
        summary = collector.get_summary()
        # unknown mode counted in neither native nor bridged
        assert summary["native_count"] == 0
        assert summary["bridged_count"] == 0
        assert summary["count_by_mode"].get("unknown", 0) == 1


# ======================================================================
# Aggregate latency stats
# ======================================================================


class TestLatencyStats:
    def test_min_max_avg(self, collector):
        for lat in [10.0, 20.0, 30.0]:
            collector.append("native", "agent_a", "t", lat, True)
        summary = collector.get_summary()
        mode_lat = summary["mode_latency"]["native"]
        assert mode_lat["count"] == 3
        assert mode_lat["min_ms"] == 10.0
        assert mode_lat["max_ms"] == 30.0
        assert mode_lat["avg_ms"] == 20.0

    def test_aggregate_latency_rolling(self, collector):
        for lat in [5.0, 15.0, 25.0]:
            collector.append("http_native", "agent_b", "t", lat, True)
        agg = collector.get_summary()["aggregate_latency_ms"]
        assert agg["count"] == 3
        assert agg["min_ms"] == 5.0
        assert agg["max_ms"] == 25.0
        assert agg["avg_ms"] == 15.0


# ======================================================================
# Threading safety
# ======================================================================


class TestThreadingSafety:
    def test_50_concurrent_appends(self, collector):
        n = 50
        errors = []

        def worker(idx):
            try:
                mode = "native" if idx % 2 == 0 else "mcp_bridge"
                collector.append(mode, f"agent_{idx % 5}", f"tool_{idx}", float(idx), True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        summary = collector.get_summary()
        assert summary["native_count"] + summary["bridged_count"] == n
        assert len(summary["count_by_agent"]) == 5  # agent_0..agent_4


# ======================================================================
# make_telemetry_block
# ======================================================================


class TestMakeTelemetryBlock:
    def test_native_block_shape(self):
        block = make_telemetry_block("native", 12.5, "broker", "quantumarb")
        assert set(block.keys()) == {
            "invocation_mode", "bridge_mode", "source", "agent_id",
            "latency_ms", "delivery_latency_ms", "timestamp",
        }
        assert block["invocation_mode"] == "native"
        assert block["bridge_mode"] == "none"
        assert block["source"] == "broker"
        assert block["agent_id"] == "quantumarb"
        assert block["latency_ms"] == 12.5
        assert block["delivery_latency_ms"] == 12.5
        assert "T" in block["timestamp"]

    def test_mcp_bridge_block_shape(self):
        block = make_telemetry_block("mcp_bridge", 33.3, "mcp_gateway", "gemma4")
        assert block["invocation_mode"] == "mcp_bridge"
        assert block["bridge_mode"] == "mcp_compat"

    def test_external_bridge_block(self):
        block = make_telemetry_block("external_bridge", 99.9, "a2a_gateway", "external_agent")
        assert block["invocation_mode"] == "external_bridge"
        assert block["bridge_mode"] == "external_compat"

    def test_mesh_native_block(self):
        block = make_telemetry_block("mesh_native", 8.0, "mesh_router", "agent_z")
        assert block["bridge_mode"] == "none"

    def test_all_modes_have_correct_bridge_mode(self):
        for mode in _NATIVE_MODES:
            block = make_telemetry_block(mode, 1.0, "test", "a")
            assert block["bridge_mode"] == "none", f"{mode} should be none"
        for mode in _BRIDGE_MODES:
            block = make_telemetry_block(mode, 1.0, "test", "a")
            expected = "mcp_compat" if mode == "mcp_bridge" else "external_compat"
            assert block["bridge_mode"] == expected, f"{mode} should be {expected}"


# ======================================================================
# Persistence across restart
# ======================================================================


class TestPersistence:
    def test_reload_from_jsonl(self, collector):
        collector.append("native", "agent_a", "t1", 10.0, True)
        collector.append("mcp_bridge", "agent_b", "t2", 20.0, True)
        collector.append("http_native", "agent_a", "t3", 30.0, True)

        # simulate restart: new collector on same file
        col2 = PathTelemetryCollector(jsonl_path=collector._jsonl_path)
        col2.reload_from_jsonl()

        summary = col2.get_summary()
        assert summary["native_count"] == 2
        assert summary["bridged_count"] == 1
        assert summary["count_by_agent"]["agent_a"] == 2
        assert summary["count_by_agent"]["agent_b"] == 1

    def test_persistence_file_created(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        tmp.close()
        os.unlink(tmp.name)  # remove so we start clean
        col = PathTelemetryCollector(jsonl_path=tmp.name)
        assert not os.path.exists(col._jsonl_path)
        col.append("native", "a", "t", 1.0, True)
        assert os.path.exists(col._jsonl_path)
        with open(col._jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["agent_id"] == "a"
        os.unlink(tmp.name)

    def test_reload_empty_file(self, collector):
        col2 = PathTelemetryCollector(jsonl_path=collector._jsonl_path)
        col2.reload_from_jsonl()  # should not raise
        summary = col2.get_summary()
        assert summary["native_count"] == 0
        assert summary["bridged_count"] == 0

    def test_reload_after_reset(self, collector):
        collector.append("native", "x", "t", 5.0, True)
        collector.reset()
        # reset clears in-memory but file still has the record
        col2 = PathTelemetryCollector(jsonl_path=collector._jsonl_path)
        col2.reload_from_jsonl()
        assert col2.get_summary()["native_count"] == 1

    def test_corrupt_line_skipped(self, collector):
        # write a valid line then a corrupt one
        collector.append("native", "a", "t", 1.0, True)
        with open(collector._jsonl_path, "a") as f:
            f.write("not-json\n")
        collector.append("native", "b", "t", 2.0, True)

        col2 = PathTelemetryCollector(jsonl_path=collector._jsonl_path)
        col2.reload_from_jsonl()
        summary = col2.get_summary()
        # only the 2 valid records should be loaded
        assert summary["count_by_agent"]["a"] == 1
        assert summary["count_by_agent"]["b"] == 1


# ======================================================================
# Rolling window behavior
# ======================================================================


class TestRollingWindow:
    def test_window_100_exact(self, collector):
        for i in range(100):
            collector.append("native", "a", "t", float(i), True)
        summary = collector.get_summary()
        w100 = summary["window_100"]
        assert w100["count"] == 100
        assert w100["min_ms"] == 0.0
        assert w100["max_ms"] == 99.0
        assert abs(w100["avg_ms"] - 49.5) < 0.01

    def test_window_100_capped(self, collector):
        for i in range(150):
            collector.append("native", "a", "t", float(i), True)
        summary = collector.get_summary()
        w100 = summary["window_100"]
        assert w100["count"] == 100, f"expected 100, got {w100['count']}"
        # last 100 values are 50..149
        assert w100["min_ms"] == 50.0, f"expected 50.0, got {w100['min_ms']}"
        assert w100["max_ms"] == 149.0, f"expected 149.0, got {w100['max_ms']}"

    def test_window_1000_capped(self, collector):
        for i in range(1100):
            collector.append("native", "a", "t", float(i), True)
        summary = collector.get_summary()
        w1000 = summary["window_1000"]
        assert w1000["count"] == 1000
        # last 1000 values are 100..1099
        assert w1000["min_ms"] == 100.0
        assert w1000["max_ms"] == 1099.0

    def test_window_empty_returns_none(self, collector):
        summary = collector.get_summary()
        assert summary["window_100"]["count"] == 0
        assert summary["window_100"]["min_ms"] is None
        assert summary["window_100"]["max_ms"] is None
        assert summary["window_100"]["avg_ms"] is None
        assert summary["window_1000"]["count"] == 0
        assert summary["window_1000"]["min_ms"] is None
        assert summary["window_1000"]["max_ms"] is None
        assert summary["window_1000"]["avg_ms"] is None


# ======================================================================
# Empty collector
# ======================================================================


class TestEmptyCollector:
    def test_empty_summary(self, collector):
        summary = collector.get_summary()
        assert summary["native_count"] == 0
        assert summary["bridged_count"] == 0
        assert summary["count_by_agent"] == {}
        assert summary["count_by_mode"] == {}, f"got {summary['count_by_mode']}"
        assert summary["aggregate_latency_ms"]["count"] == 0
        assert summary["window_100"]["count"] == 0
        assert summary["window_1000"]["count"] == 0

    def test_reset_produces_empty(self, collector):
        collector.append("native", "a", "t", 5.0, True)
        collector.reset()
        summary = collector.get_summary()
        assert summary["native_count"] == 0
        assert summary["count_by_agent"] == {}


# ======================================================================
# Module singleton
# ======================================================================


class TestModuleSingleton:
    def test_singleton_importable(self):
        from simp.telemetry import path_telemetry as pt
        assert pt is not None
        assert isinstance(pt, PathTelemetryCollector)

    def test_singleton_is_same(self):
        from simp.telemetry.path_telemetry import path_telemetry as pt1
        from simp.telemetry import path_telemetry as pt2
        assert pt1 is pt2


# ======================================================================
# All invocation modes produce correct counters
# ======================================================================


class TestAllModes:
    def test_all_modes_in_counts(self, collector):
        exp_native = 0
        exp_bridged = 0
        for i, mode in enumerate(sorted(INVOCATION_MODES)):
            collector.append(mode, f"agent_{mode}", f"tool_{i}", float(i * 10), True)
            if mode in _NATIVE_MODES:
                exp_native += 1
            else:
                exp_bridged += 1
        summary = collector.get_summary()
        assert summary["native_count"] == exp_native
        assert summary["bridged_count"] == exp_bridged

    def test_mode_latency_per_mode(self, collector):
        for mode in INVOCATION_MODES:
            collector.append(mode, "a", "t", 5.0, True)
        summary = collector.get_summary()
        for mode in INVOCATION_MODES:
            assert mode in summary["mode_latency"]
            assert summary["mode_latency"][mode]["count"] == 1
