#!/usr/bin/env python3
"""
Intent Telemetry — Usage counters, route success/failure, latency, and
fallback reasons for the SIMP intent router.

Tracks every route attempt, aggregates statistics, and surfaces
"used vs declared capability" metrics for operator visibility.
"""

import json
import logging
import threading
import statistics
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default persistence path
# ---------------------------------------------------------------------------

_TELEMETRY_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "intent_telemetry.jsonl"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RouteResult:
    """A single route attempt result."""
    intent_type: str
    source_agent: str
    target_agent: str
    success: bool
    latency_ms: float
    route_path: str  # "direct", "fallback", "capability_match", "broadcast"
    fallback_reason: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class IntentTelemetry:
    """Aggregated telemetry for a single intent type."""
    intent_type: str
    total_attempts: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    route_path_counts: Dict[str, int] = field(default_factory=dict)
    fallback_reasons: Dict[str, int] = field(default_factory=dict)
    last_routed: Optional[str] = None


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class IntentTelemetryCollector:
    """
    Collects, aggregates, and persists intent routing telemetry.

    Thread-safe via ``threading.Lock()``.  Persists every recorded result
    to ``data/intent_telemetry.jsonl`` (append-only).  Provides summary
    and underutilised-capability detection.
    """

    def __init__(self, log_path: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._log_path = Path(log_path) if log_path else _TELEMETRY_LOG_PATH
        # In-memory raw results (for percentile calculations)
        self._results: List[RouteResult] = []
        # Ensure parent directory exists
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # record
    # ------------------------------------------------------------------

    def record_result(self, result: RouteResult) -> None:
        """Record a single route result (thread-safe, persists to JSONL)."""
        with self._lock:
            self._results.append(result)
            self._append_log(asdict(result))

    # ------------------------------------------------------------------
    # aggregation
    # ------------------------------------------------------------------

    def get_telemetry(
        self, intent_type: Optional[str] = None
    ) -> Union[IntentTelemetry, Dict[str, IntentTelemetry]]:
        """
        Return aggregated telemetry.

        * If *intent_type* is given — return a single ``IntentTelemetry``.
        * If *intent_type* is ``None`` — return ``{intent_type: IntentTelemetry}``
          for every type that has been seen.
        """
        with self._lock:
            if intent_type:
                return self._build_telemetry(intent_type)

            types = {r.intent_type for r in self._results}
            return {t: self._build_telemetry(t) for t in sorted(types)}

    def _build_telemetry(self, intent_type: str) -> IntentTelemetry:
        """Build aggregated telemetry for one intent type from stored results."""
        matching = [r for r in self._results if r.intent_type == intent_type]
        if not matching:
            return IntentTelemetry(intent_type=intent_type)

        success_count = sum(1 for r in matching if r.success)
        failure_count = len(matching) - success_count
        latencies = [r.latency_ms for r in matching]

        avg_latency = statistics.mean(latencies) if latencies else 0.0
        sorted_lats = sorted(latencies)

        def percentile(p: float) -> float:
            if not sorted_lats:
                return 0.0
            idx = max(0, min(len(sorted_lats) - 1, int(len(sorted_lats) * p / 100)))
            return sorted_lats[idx]

        route_path_counts: Dict[str, int] = {}
        fallback_reasons: Dict[str, int] = {}
        last_routed: Optional[str] = None

        for r in matching:
            route_path_counts[r.route_path] = route_path_counts.get(r.route_path, 0) + 1
            if r.fallback_reason:
                fallback_reasons[r.fallback_reason] = fallback_reasons.get(r.fallback_reason, 0) + 1
            # Track most recent timestamp
            if r.timestamp and (last_routed is None or r.timestamp > last_routed):
                last_routed = r.timestamp

        return IntentTelemetry(
            intent_type=intent_type,
            total_attempts=len(matching),
            success_count=success_count,
            failure_count=failure_count,
            avg_latency_ms=round(avg_latency, 2),
            p50_latency_ms=round(percentile(50), 2),
            p99_latency_ms=round(percentile(99), 2),
            route_path_counts=route_path_counts,
            fallback_reasons=fallback_reasons,
            last_routed=last_routed,
        )

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """Overall stats: total routes, success rate, avg latency, top intents, top fallback reasons."""
        with self._lock:
            total = len(self._results)
            if total == 0:
                return {
                    "total_routes": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "top_intents": [],
                    "top_fallback_reasons": [],
                }

            successes = sum(1 for r in self._results if r.success)
            failures = total - successes
            all_latencies = [r.latency_ms for r in self._results]
            avg_lat = statistics.mean(all_latencies) if all_latencies else 0.0

            # Top intents by attempt count
            intent_counts: Dict[str, int] = {}
            for r in self._results:
                intent_counts[r.intent_type] = intent_counts.get(r.intent_type, 0) + 1
            top_intents = sorted(intent_counts.items(), key=lambda x: -x[1])[:10]

            # Top fallback reasons
            fb_counts: Dict[str, int] = {}
            for r in self._results:
                if r.fallback_reason:
                    fb_counts[r.fallback_reason] = fb_counts.get(r.fallback_reason, 0) + 1
            top_fb = sorted(fb_counts.items(), key=lambda x: -x[1])[:10]

            return {
                "total_routes": total,
                "success_count": successes,
                "failure_count": failures,
                "success_rate": round(successes / total, 4),
                "avg_latency_ms": round(avg_lat, 2),
                "top_intents": [{"intent_type": k, "count": v} for k, v in top_intents],
                "top_fallback_reasons": [{"reason": k, "count": v} for k, v in top_fb],
            }

    # ------------------------------------------------------------------
    # underutilised capabilities
    # ------------------------------------------------------------------

    def get_underutilized_capabilities(
        self, declared_intents: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Return intents declared in routing_policy but never routed (zero attempts).

        *declared_intents* — list of intent types from the routing policy.
        If not provided, only intents recorded with zero attempts are flagged.
        """
        with self._lock:
            seen: Dict[str, int] = {}
            for r in self._results:
                seen[r.intent_type] = seen.get(r.intent_type, 0) + 1

            underutilized: List[Dict[str, Any]] = []

            if declared_intents:
                for it in declared_intents:
                    attempts = seen.get(it, 0)
                    if attempts == 0:
                        underutilized.append({
                            "intent_type": it,
                            "attempts": 0,
                            "status": "never_routed",
                        })
            else:
                # Flag types that have been seen but never successfully routed
                unmatched = set(seen.keys()) - {r.intent_type for r in self._results if r.success}
                for it in sorted(unmatched):
                    if seen.get(it, 0) > 0:
                        underutilized.append({
                            "intent_type": it,
                            "attempts": seen.get(it, 0),
                            "status": "no_successful_routes",
                        })

            return underutilized

    # ------------------------------------------------------------------
    # serialization
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Return full telemetry state as a JSON string."""
        with self._lock:
            telemetry_map = self.get_telemetry()  # type: ignore[assignment]
            data: Dict[str, Any] = {
                "summary": self.get_summary(),
                "per_intent": {
                    k: asdict(v) for k, v in telemetry_map.items()
                },
                "underutilized": self.get_underutilized_capabilities(),
            }
            return json.dumps(data, indent=2, default=str)

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def _append_log(self, record: Dict[str, Any]) -> None:
        """Append a JSON line to the JSONL log (thread-safe — caller must hold ``_lock``)."""
        try:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            logger.error("Failed to write telemetry record to %s: %s", self._log_path, exc)

    def replay_log(self) -> int:
        """Replay entries from the JSONL file back into memory.  Returns count of entries loaded."""
        if not self._log_path.exists():
            return 0
        count = 0
        with self._lock:
            try:
                with open(self._log_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            self._results.append(RouteResult(**data))
                            count += 1
                        except (json.JSONDecodeError, TypeError, KeyError) as exc:
                            logger.warning("Skipping malformed telemetry line: %s", exc)
            except OSError as exc:
                logger.error("Failed to read telemetry log %s: %s", self._log_path, exc)
        return count


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

router_telemetry: IntentTelemetryCollector = IntentTelemetryCollector()
"""Module-level singleton used by the intent router instrumentation."""
