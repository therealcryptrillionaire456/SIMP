#!/usr/bin/env python3.10
"""
Latency Profiler & Optimizer (T19).

Instruments all execution paths with time.perf_counter() spans to measure
and optimize decision latency. Sub-second arb decisions are the goal.

Features:
1. Instrument price fetch, Jupiter quote, decision eval, execution submit, Solana confirmation
2. Use time.perf_counter() spans with nanosecond precision
3. Write latency profile to data/latency_profiles/<cycle_id>.jsonl
4. Compute p50, p95, p99 per path
5. Alert on p99 > 2x target (degraded network)
6. Compare against previous cycle to detect regressions
"""

import json
import logging
import statistics
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator

log = logging.getLogger("LatencyProfiler")

# ──────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class LatencySpan:
    """A single latency measurement span.

    Attributes:
        name: Logical name of the measured operation (e.g. "price_fetch").
        start_ns: time.perf_counter_ns() value when the span started.
        duration_ms: Computed duration in milliseconds.
        target_ms: Target latency in milliseconds for this operation.
        tags: Optional key-value metadata (e.g. {"exchange": "jupiter"}).
        cycle_id: Unique cycle identifier for grouping related spans.
        timestamp: ISO 8601 UTC timestamp.
    """
    name: str
    start_ns: int
    duration_ms: float = 0.0
    target_ms: float = 1000.0
    tags: Dict[str, str] = field(default_factory=dict)
    cycle_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "start_ns": self.start_ns,
            "duration_ms": round(self.duration_ms, 3),
            "target_ms": self.target_ms,
            "tags": dict(self.tags),
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
        }


@dataclass
class PathStats:
    """Aggregate statistics for a named measurement path."""
    name: str
    count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    mean_ms: float
    target_ms: float
    degraded: bool  # True if p99 > 2× target

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "target_ms": self.target_ms,
            "degraded": self.degraded,
        }


# ──────────────────────────────────────────────────────────────────────────
# Profiler
# ──────────────────────────────────────────────────────────────────────────

class LatencyProfiler:
    """Measures and reports latency spans across execution paths.

    Thread-safe. Accumulates spans in memory and persists to JSONL on
    demand. Provides percentiles, regression detection, and degradation
    alerts.
    """

    def __init__(self, profiles_dir: str = "data/latency_profiles"):
        self._profiles_dir = Path(profiles_dir)
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._spans: List[LatencySpan] = []
        self._previous_spans: List[LatencySpan] = []
        self._cycle_id: str = self._generate_cycle_id()

        # Load any previous profile for regression comparison
        self._load_previous_profile()

        log.info(
            "LatencyProfiler initialized (cycle=%s, profiles_dir=%s)",
            self._cycle_id, self._profiles_dir,
        )

    # ── Public API ──────────────────────────────────────────────────────

    @contextmanager
    def start_span(
        self,
        name: str,
        target_ms: float = 1000.0,
        tags: Optional[Dict[str, str]] = None,
    ) -> Generator[LatencySpan, None, None]:
        """Context manager that times the enclosed block.

        Usage::

            profiler = LatencyProfiler()
            with profiler.start_span("price_fetch", target_ms=500) as span:
                prices = fetch_prices()
            # span.duration_ms is set automatically on exit.

        Yields:
            The LatencySpan instance (with duration_ms updated on exit).
        """
        span = LatencySpan(
            name=name,
            start_ns=time.perf_counter_ns(),
            target_ms=target_ms,
            tags=tags or {},
            cycle_id=self._cycle_id,
        )
        try:
            yield span
        finally:
            self.end_span(span)

    def end_span(self, span: LatencySpan) -> None:
        """Record the end time of a span and store it.

        Called automatically if the span came from ``start_span()``, but
        may be called manually for hand-timed spans.
        """
        elapsed_ns = time.perf_counter_ns() - span.start_ns
        span.duration_ms = elapsed_ns / 1_000_000.0  # ns → ms
        span.timestamp = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._spans.append(span)

        # Log degradation alert inline
        if span.duration_ms > 2.0 * span.target_ms:
            log.warning(
                "LATENCY DEGRADED: %s = %.2f ms (target %.0f ms, %.1f×)",
                span.name, span.duration_ms, span.target_ms,
                span.duration_ms / span.target_ms,
            )

    def record(
        self,
        name: str,
        duration_ms: float,
        target_ms: float = 1000.0,
        tags: Optional[Dict[str, str]] = None,
    ) -> LatencySpan:
        """Record an already-measured duration directly.

        Useful when timing is done externally but you want the same
        profiling infrastructure for persistence.
        """
        span = LatencySpan(
            name=name,
            start_ns=0,
            duration_ms=duration_ms,
            target_ms=target_ms,
            tags=tags or {},
            cycle_id=self._cycle_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._spans.append(span)
        if duration_ms > 2.0 * target_ms:
            log.warning(
                "LATENCY DEGRADED: %s = %.2f ms (target %.0f ms, %.1f×)",
                name, duration_ms, target_ms, duration_ms / target_ms,
            )
        return span

    def get_stats(self, path_filter: Optional[str] = None) -> Dict[str, PathStats]:
        """Compute p50 / p95 / p99 statistics for all paths (optionally filtered).

        Args:
            path_filter: If provided, only paths whose name contains this
                         substring are included.

        Returns:
            Mapping of path name to PathStats.
        """
        with self._lock:
            spans = list(self._spans)

        # Group durations by name
        groups: Dict[str, List[float]] = {}
        targets: Dict[str, float] = {}
        for s in spans:
            if path_filter and path_filter not in s.name:
                continue
            groups.setdefault(s.name, []).append(s.duration_ms)
            # Keep the most recent target per path
            targets[s.name] = s.target_ms

        stats: Dict[str, PathStats] = {}
        for name, durations in groups.items():
            durations.sort()
            n = len(durations)
            p50 = self._percentile(durations, 50)
            p95 = self._percentile(durations, 95)
            p99 = self._percentile(durations, 99)
            tgt = targets.get(name, 1000.0)
            stats[name] = PathStats(
                name=name,
                count=n,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                min_ms=durations[0],
                max_ms=durations[-1],
                mean_ms=statistics.mean(durations),
                target_ms=tgt,
                degraded=(p99 > 2.0 * tgt),
            )
        return stats

    def check_regressions(self) -> List[Dict[str, Any]]:
        """Compare current cycle spans against the previous cycle.

        A regression is flagged when the current p50 for a path is more
        than 20 % higher than the previous p50, provided both cycles have
        at least 3 samples.

        Returns:
            List of regression dicts with keys: path, prev_p50_ms,
            curr_p50_ms, pct_change.
        """
        if not self._previous_spans:
            return []

        # Build stats for both cycles
        prev_stats = self._compute_stats(self._previous_spans)
        curr_stats = self._compute_stats(self._spans)

        regressions: List[Dict[str, Any]] = []
        for path, curr in curr_stats.items():
            if path not in prev_stats:
                continue
            prev = prev_stats[path]
            # Require ≥3 samples in both
            if prev["count"] < 3 or curr["count"] < 3:
                continue
            if prev["p50_ms"] <= 0:
                continue
            pct = (curr["p50_ms"] - prev["p50_ms"]) / prev["p50_ms"] * 100.0
            if pct > 20.0:
                regressions.append({
                    "path": path,
                    "prev_p50_ms": round(prev["p50_ms"], 3),
                    "curr_p50_ms": round(curr["p50_ms"], 3),
                    "pct_change": round(pct, 1),
                })

        if regressions:
            log.warning("Detected %d latency regression(s)", len(regressions))
            for r in regressions:
                log.warning(
                    "  %s: %.1f → %.1f ms (+%.1f%%)",
                    r["path"], r["prev_p50_ms"], r["curr_p50_ms"], r["pct_change"],
                )
        return regressions

    def persist(self) -> str:
        """Write all accumulated spans to a JSONL file.

        The file is named ``latency_<cycle_id>.jsonl`` inside the
        configured profiles directory.

        Returns:
            Path to the written file as a string.
        """
        output_path = self._profiles_dir / f"latency_{self._cycle_id}.jsonl"

        with self._lock:
            spans = list(self._spans)

        with open(output_path, "w") as f:
            for span in spans:
                f.write(json.dumps(span.to_dict()) + "\n")

        log.info("Persisted %d spans to %s", len(spans), output_path)
        return str(output_path)

    def summary(self) -> str:
        """Return a human-readable summary string."""
        stats = self.get_stats()
        regressions = self.check_regressions()

        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"Latency Profiler Summary  (cycle: {self._cycle_id})")
        lines.append("=" * 60)
        lines.append(f"  Total spans recorded: {len(self._spans)}")
        lines.append("")

        if not stats:
            lines.append("  (no measurement data)")
        else:
            lines.append(f"  {'Path':<30s} {'Count':>6s} {'p50(ms)':>10s} "
                         f"{'p95(ms)':>10s} {'p99(ms)':>10s} {'Target':>8s} {'Degraded?':>9s}")
            lines.append("  " + "-" * 87)
            for name in sorted(stats.keys()):
                s = stats[name]
                degraded_flag = "⚠ DEGRADED" if s.degraded else "OK"
                lines.append(
                    f"  {name:<30s} {s.count:>6d} {s.p50_ms:>8.2f}  "
                    f"{s.p95_ms:>8.2f}  {s.p99_ms:>8.2f}  {s.target_ms:>6.0f}  "
                    f"{degraded_flag:>9s}"
                )

        if regressions:
            lines.append("")
            lines.append("  ⚠ LATENCY REGRESSIONS (>20% slowdown):")
            for r in regressions:
                lines.append(
                    f"    {r['path']}: {r['prev_p50_ms']} → {r['curr_p50_ms']} ms "
                    f"(+{r['pct_change']}%)"
                )

        lines.append("=" * 60)
        return "\n".join(lines)

    # ── Internals ───────────────────────────────────────────────────────

    @staticmethod
    def _generate_cycle_id() -> str:
        """Generate a short, unique cycle identifier."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        short_id = uuid.uuid4().hex[:8]
        return f"{ts}_{short_id}"

    @staticmethod
    def _percentile(sorted_durations: List[float], pct: int) -> float:
        """Compute the p-th percentile from a *sorted* list of durations."""
        if not sorted_durations:
            return 0.0
        k = (pct / 100.0) * (len(sorted_durations) - 1)
        f = int(k)
        c = k - f
        if f + 1 < len(sorted_durations):
            return sorted_durations[f] + c * (sorted_durations[f + 1] - sorted_durations[f])
        return sorted_durations[-1]

    def _compute_stats(self, spans: List[LatencySpan]) -> Dict[str, Dict[str, Any]]:
        """Compute p50/p95/p99 for a raw list of spans."""
        groups: Dict[str, List[float]] = {}
        for s in spans:
            groups.setdefault(s.name, []).append(s.duration_ms)

        result: Dict[str, Dict[str, Any]] = {}
        for name, durations in groups.items():
            durations.sort()
            n = len(durations)
            result[name] = {
                "count": n,
                "p50_ms": self._percentile(durations, 50),
                "p95_ms": self._percentile(durations, 95),
                "p99_ms": self._percentile(durations, 99),
            }
        return result

    def _load_previous_profile(self) -> None:
        """Load the most recent JSONL profile for regression comparison."""
        jsonl_files = sorted(self._profiles_dir.glob("latency_*.jsonl"))
        if not jsonl_files:
            return

        # Pick the newest file
        latest = jsonl_files[-1]
        try:
            spans: List[LatencySpan] = []
            with open(latest) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    spans.append(LatencySpan(
                        name=data["name"],
                        start_ns=data.get("start_ns", 0),
                        duration_ms=data.get("duration_ms", 0.0),
                        target_ms=data.get("target_ms", 1000.0),
                        tags=data.get("tags", {}),
                        cycle_id=data.get("cycle_id", ""),
                        timestamp=data.get("timestamp", ""),
                    ))
            self._previous_spans = spans
            log.info(
                "Loaded previous profile (%s) with %d spans for regression analysis",
                latest.name, len(spans),
            )
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            log.warning("Could not load previous profile %s: %s", latest, exc)


# ── Module-level singleton ──────────────────────────────────────────────

PROFILER = LatencyProfiler()


# ── Test function ───────────────────────────────────────────────────────

def test_latency_profiler():
    """Comprehensive test for the LatencyProfiler."""
    import tempfile
    import os

    print("=" * 60)
    print("T19 — Latency Profiler & Optimizer  (test)")
    print("=" * 60)

    # Use a temporary directory so we don't pollute real data
    with tempfile.TemporaryDirectory(prefix="latency_test_") as tmpdir:
        profiler = LatencyProfiler(profiles_dir=tmpdir)

        # ── 1. Context-manager spans ─────────────────────────────────────
        print("\n1. Recording 10 simulated spans with varying durations...")
        durations = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for i, d in enumerate(durations):
            path = "price_fetch" if i < 5 else "jupiter_quote"
            target = 500.0 if path == "price_fetch" else 1000.0
            with profiler.start_span(path, target_ms=target,
                                     tags={"iteration": str(i)}) as span:
                # Simulate work by sleeping for a known duration
                time.sleep(d / 1000.0)  # ms → seconds
            # Verify duration is close to expected (allow sleep jitter)
            assert abs(span.duration_ms - d) < 15.0, \
                f"Expected ~{d} ms, got {span.duration_ms:.1f} ms"
        print("   ✅ 10 spans recorded successfully")

        # ── 2. Direct record ────────────────────────────────────────────
        print("\n2. Testing direct record()...")
        profiler.record("execution_submit", duration_ms=150.0, target_ms=200.0,
                        tags={"exchange": "jupiter"})
        profiler.record("solana_confirm", duration_ms=420.0, target_ms=400.0,
                        tags={"slot": "12345"})
        print("   ✅ 2 direct records added")

        # ── 3. Verify stats (p50/p95/p99) ───────────────────────────────
        print("\n3. Computing p50/p95/p99 per path...")
        stats = profiler.get_stats()

        # price_fetch: [~10, ~20, ~30, ~40, ~50] ms — sleep jitter means actual
        # durations differ. Collect the actual durations to verify percentiles.
        pf_spans = [s for s in profiler._spans if s.name == "price_fetch"]
        pf_durations = sorted(s.duration_ms for s in pf_spans)
        pf_expected_p50 = profiler._percentile(pf_durations, 50)
        pf_expected_p95 = profiler._percentile(pf_durations, 95)
        pf_expected_p99 = profiler._percentile(pf_durations, 99)

        pf = stats.get("price_fetch")
        assert pf is not None, "price_fetch path missing from stats"
        assert pf.count == len(pf_durations)
        assert abs(pf.p50_ms - pf_expected_p50) < 0.01, \
            f"p50 mismatch: expected {pf_expected_p50}, got {pf.p50_ms}"
        assert abs(pf.p95_ms - pf_expected_p95) < 0.01
        assert abs(pf.p99_ms - pf_expected_p99) < 0.01
        print(f"   price_fetch: count={pf.count}, p50={pf.p50_ms:.1f} ms, "
              f"p95={pf.p95_ms:.1f} ms, p99={pf.p99_ms:.1f} ms  ✅")

        # jupiter_quote: [~60, ~70, ~80, ~90, ~100] ms
        jq_spans = [s for s in profiler._spans if s.name == "jupiter_quote"]
        jq_durations = sorted(s.duration_ms for s in jq_spans)
        jq_expected_p50 = profiler._percentile(jq_durations, 50)
        jq_expected_p95 = profiler._percentile(jq_durations, 95)
        jq_expected_p99 = profiler._percentile(jq_durations, 99)

        jq = stats.get("jupiter_quote")
        assert jq is not None, "jupiter_quote path missing from stats"
        assert jq.count == len(jq_durations)
        assert abs(jq.p50_ms - jq_expected_p50) < 0.01, \
            f"p50 mismatch: expected {jq_expected_p50}, got {jq.p50_ms}"
        assert abs(jq.p95_ms - jq_expected_p95) < 0.01
        print(f"   jupiter_quote: count={jq.count}, p50={jq.p50_ms:.1f} ms, "
              f"p95={jq.p95_ms:.1f} ms, p99={jq.p99_ms:.1f} ms  ✅")

        # execution_submit: 150 ms
        es = stats.get("execution_submit")
        assert es is not None
        assert es.count == 1
        print(f"   execution_submit: count={es.count}, duration={es.p50_ms:.1f} ms  ✅")

        # solana_confirm: 420 ms (target=400, 2×=800, 420<800 → not degraded)
        sc = stats.get("solana_confirm")
        assert sc is not None
        assert sc.count == 1
        assert sc.degraded is False, \
            f"Expected degraded=False (420 < 800), got degraded={sc.degraded}"
        print(f"   solana_confirm: count={sc.count}, duration={sc.p50_ms:.1f} ms, "
              f"degraded={sc.degraded} (target=400, 2×target=800)  ✅")

        # Add a truly degraded span
        profiler.record("solana_confirm", duration_ms=900.0, target_ms=400.0)
        stats2 = profiler.get_stats()
        sc2 = stats2.get("solana_confirm")
        assert sc2 is not None
        assert sc2.degraded is True, \
            f"Expected degraded=True now that p99=900 > 800"
        print(f"   solana_confirm (after adding 900ms): p99={sc2.p99_ms:.1f} ms, "
              f"degraded={sc2.degraded}  ✅")

        # ── 4. Regression detection ─────────────────────────────────────
        print("\n4. Testing regression detection...")
        # Manually seed a "previous" profile with lower values
        profiler._previous_spans = [
            LatencySpan(name="price_fetch", start_ns=0, duration_ms=25.0,
                        target_ms=500, cycle_id="prev"),
            LatencySpan(name="price_fetch", start_ns=0, duration_ms=28.0,
                        target_ms=500, cycle_id="prev"),
            LatencySpan(name="price_fetch", start_ns=0, duration_ms=22.0,
                        target_ms=500, cycle_id="prev"),
            LatencySpan(name="jupiter_quote", start_ns=0, duration_ms=70.0,
                        target_ms=1000, cycle_id="prev"),
            LatencySpan(name="jupiter_quote", start_ns=0, duration_ms=75.0,
                        target_ms=1000, cycle_id="prev"),
            LatencySpan(name="jupiter_quote", start_ns=0, duration_ms=68.0,
                        target_ms=1000, cycle_id="prev"),
        ]

        regressions = profiler.check_regressions()
        # price_fetch prev p50 ≈25, curr p50=30 → +20% exactly — threshold is >20%,
        # so just barely over if exactly 20%.  Let's check.
        # 30/25=1.20 → +20% -> NOT >20%, so not a regression
        # jupiter_quote prev p50≈70, curr p50=80 → 80/70≈14.3% → not regression
        print(f"   Regressions found: {len(regressions)}")
        for r in regressions:
            print(f"     {r['path']}: {r['prev_p50_ms']} → {r['curr_p50_ms']} ms "
                  f"(+{r['pct_change']}%)")

        # Now add a span that creates a clear regression
        # Add a very slow jupiter_quote to push current p50 well above previous
        profiler.record("jupiter_quote", duration_ms=300.0, target_ms=1000.0)
        regressions2 = profiler.check_regressions()
        print(f"   After adding slow jupiter_quote: {len(regressions2)} regression(s)")
        jq_found = False
        for r in regressions2:
            print(f"     {r['path']}: {r['prev_p50_ms']} → {r['curr_p50_ms']} ms "
                  f"(+{r['pct_change']}%)")
            if r["path"] == "jupiter_quote":
                jq_found = True
                assert r["pct_change"] > 20.0, \
                    f"Expected >20% regression, got {r['pct_change']}%"
        assert jq_found, "Expected at least one regression for jupiter_quote path"

        print("   ✅ Regression detection working")

        # ── 5. Persistence ──────────────────────────────────────────────
        print("\n5. Testing persistence to JSONL...")
        persisted_path = profiler.persist()
        assert os.path.exists(persisted_path), f"File not found: {persisted_path}"
        print(f"   Written to: {persisted_path}")

        # Verify file contents
        with open(persisted_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == len(profiler._spans), \
            f"Expected {len(profiler._spans)} lines, got {len(lines)}"
        # Verify JSON validity
        for line in lines:
            data = json.loads(line)
            assert "name" in data
            assert "duration_ms" in data
        print(f"   File contains {len(lines)} valid JSON records  ✅")

        # ── 6. Path-filtered stats ─────────────────────────────────────
        print("\n6. Testing path-filtered stats...")
        filtered = profiler.get_stats(path_filter="price")
        assert "price_fetch" in filtered
        assert "jupiter_quote" not in filtered
        assert "solana_confirm" not in filtered
        print(f"   Filtered 'price': {list(filtered.keys())}  ✅")

        # ── 7. Summary ──────────────────────────────────────────────────
        print("\n7. Generating summary...")
        summary_str = profiler.summary()
        print(summary_str)
        assert "Latency Profiler Summary" in summary_str
        assert "price_fetch" in summary_str
        assert "jupiter_quote" in summary_str
        assert "solana_confirm" in summary_str
        print("   ✅ Summary generated successfully")

    # ── All passed ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("✅ ALL T19 TESTS PASSED")
    print("=" * 60)


# ── Entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    test_latency_profiler()
