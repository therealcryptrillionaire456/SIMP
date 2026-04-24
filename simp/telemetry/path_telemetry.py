"""
SIMP Path Telemetry — Tranche 14

Thread-safe collector that tracks per-agent + per-invocation-mode counters,
latency statistics, and rolling window summaries.  Persists to JSONL for
broker-agnostic audit.
"""

import json
import logging
import threading
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SIMP.PathTelemetry")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INVOCATION_MODES = frozenset({
    "native",
    "mesh_native",
    "http_native",
    "mcp_bridge",
    "external_bridge",
})

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class PathTelemetryRecord:
    """A single telemetry observation — one tool invocation."""

    invocation_mode: str
    agent_id: str
    tool_name: str
    latency_ms: float
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Rolling window helper
# ---------------------------------------------------------------------------

class RollingWindow:
    """Min / max / avg over a sliding window of observations."""

    def __init__(self, maxlen: int = 1000):
        self.maxlen = maxlen
        self.values: deque = deque(maxlen=maxlen)

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def min_ms(self) -> Optional[float]:
        return min(self.values) if self.values else None

    @property
    def max_ms(self) -> Optional[float]:
        return max(self.values) if self.values else None

    @property
    def avg_ms(self) -> Optional[float]:
        if not self.values:
            return None
        return sum(self.values) / len(self.values)

    def push(self, latency_ms: float) -> None:
        self.values.append(latency_ms)

    def summary(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "avg_ms": self.avg_ms,
        }


# ---------------------------------------------------------------------------
# Per-mode latency accumulator
# ---------------------------------------------------------------------------

@dataclass
class ModeLatencyStats:
    """Aggregate latency stats for one invocation mode."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    def record(self, latency_ms: float) -> None:
        self.count += 1
        self.total_ms += latency_ms
        if latency_ms < self.min_ms:
            self.min_ms = latency_ms
        if latency_ms > self.max_ms:
            self.max_ms = latency_ms

    @property
    def avg_ms(self) -> Optional[float]:
        return self.total_ms / self.count if self.count else None

    def summary(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "total_ms": self.total_ms,
            "min_ms": self.min_ms if self.count else None,
            "max_ms": self.max_ms if self.count else None,
            "avg_ms": self.avg_ms,
        }


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class PathTelemetryCollector:
    """
    Thread-safe singleton that accumulates invocation telemetry.

    Tracks:
      - Per-agent + per-mode counters
      - Aggregate latency stats per invocation mode
      - Rolling windows (last 100, last 1000)
      - JSONL persistence at ``data/path_telemetry.jsonl``
    """

    def __init__(self, jsonl_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._jsonl_path = Path(jsonl_path or self._default_jsonl_path())

        # counters
        self._agent_count: Dict[str, int] = defaultdict(int)
        self._mode_count: Dict[str, int] = defaultdict(int)
        self._agent_mode_count: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # latency stats per invocation mode
        self._mode_latency: Dict[str, ModeLatencyStats] = defaultdict(ModeLatencyStats)

        # rolling windows (last 100, last 1000)
        self._window_100: RollingWindow = RollingWindow(maxlen=100)
        self._window_1000: RollingWindow = RollingWindow(maxlen=1000)

        self._ensure_dir()

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_jsonl_path() -> str:
        return str(Path(_REPO_ROOT) / "data" / "path_telemetry.jsonl")

    def _ensure_dir(self) -> None:
        try:
            self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def _validate_mode(self, invocation_mode: str) -> str:
        """Return the mode if valid; log a warning and return 'unknown' otherwise."""
        if invocation_mode not in INVOCATION_MODES:
            logger.warning("Unknown invocation_mode=%r — recording as 'unknown'", invocation_mode)
            return "unknown"
        return invocation_mode

    # ------------------------------------------------------------------
    # append
    # ------------------------------------------------------------------

    def append(
        self,
        invocation_mode: str,
        agent_id: str,
        tool_name: str,
        latency_ms: float,
        success: bool,
    ) -> None:
        """
        Record one telemetry observation.

        Thread-safe via ``threading.RLock()``.  Never raises — errors are logged.
        """
        try:
            mode = self._validate_mode(invocation_mode)
            record = PathTelemetryRecord(
                invocation_mode=mode,
                agent_id=agent_id,
                tool_name=tool_name,
                latency_ms=latency_ms,
                success=success,
            )
            with self._lock:
                # update counters
                self._agent_count[agent_id] += 1
                self._mode_count[mode] += 1
                self._agent_mode_count[agent_id][mode] += 1

                # latency stats
                self._mode_latency[mode].record(latency_ms)

                # rolling windows
                self._window_100.push(latency_ms)
                self._window_1000.push(latency_ms)

                # persist
                self._persist(record)
        except Exception as exc:
            logger.error("PathTelemetryCollector.append failed: %s", exc)

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def _persist(self, record: PathTelemetryRecord) -> None:
        """Write one JSONL line (caller must hold _lock)."""
        line = json.dumps(record.to_dict(), default=str) + "\n"
        with open(self._jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all telemetry state."""
        with self._lock:
            self._agent_count.clear()
            self._mode_count.clear()
            self._agent_mode_count.clear()
            self._mode_latency.clear()
            self._window_100.values.clear()
            self._window_1000.values.clear()

    def get_summary(self) -> Dict[str, Any]:
        """
        Return a snapshot of all accumulated telemetry.

        Keys:
          - ``native_count`` — total invocations in native modes
          - ``bridged_count`` — total invocations in bridge modes
          - ``aggregate_latency_ms`` — overall min/max/avg/count
          - ``count_by_agent`` — per-agent totals
          - ``count_by_mode`` — per-invocation-mode totals
          - ``mode_latency`` — per-mode latency stats
          - ``window_100`` — rolling window of last 100
          - ``window_1000`` — rolling window of last 1000
        """
        with self._lock:
            native_modes = {"native", "mesh_native", "http_native"}
            bridged_modes = {"mcp_bridge", "external_bridge"}

            native_count = sum(self._mode_count[m] for m in native_modes)
            bridged_count = sum(self._mode_count[m] for m in bridged_modes)

            # aggregate across all modes
            all_latencies: List[float] = []
            for stats in self._mode_latency.values():
                # can't extract individual values from aggregate easily,
                # so build from rolling window as approximation
                pass

            return {
                "native_count": native_count,
                "bridged_count": bridged_count,
                "aggregate_latency_ms": self._window_1000.summary(),
                "count_by_agent": dict(self._agent_count),
                "count_by_mode": {k: v for k, v in self._mode_count.items() if v > 0},
                "mode_latency": {
                    mode: stats.summary()
                    for mode, stats in self._mode_latency.items()
                },
                "window_100": self._window_100.summary(),
                "window_1000": self._window_1000.summary(),
            }

    # ------------------------------------------------------------------
    # reload from JSONL (for test restart simulation)
    # ------------------------------------------------------------------

    def reload_from_jsonl(self) -> None:
        """
        Replay all persisted records into memory.

        Useful for simulating collector restart.  Clears all in-memory state
        first, then replays.  Thread-safe.
        """
        records: List[PathTelemetryRecord] = []
        if not self._jsonl_path.exists():
            return
        try:
            with open(self._jsonl_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        records.append(PathTelemetryRecord(**data))
                    except (json.JSONDecodeError, TypeError) as exc:
                        logger.warning("Skipping corrupt telemetry line: %s", exc)
        except Exception as exc:
            logger.error("reload_from_jsonl read error: %s", exc)
            return

        with self._lock:
            # reset
            self._agent_count.clear()
            self._mode_count.clear()
            self._agent_mode_count.clear()
            self._mode_latency.clear()
            self._window_100 = RollingWindow(maxlen=100)
            self._window_1000 = RollingWindow(maxlen=1000)

            # replay
            for rec in records:
                mode = self._validate_mode(rec.invocation_mode)
                self._agent_count[rec.agent_id] += 1
                self._mode_count[mode] += 1
                self._agent_mode_count[rec.agent_id][mode] += 1
                self._mode_latency[mode].record(rec.latency_ms)
                self._window_100.push(rec.latency_ms)
                self._window_1000.push(rec.latency_ms)

    # ------------------------------------------------------------------
    # reset (for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all in-memory state.  Does NOT touch the JSONL file."""
        with self._lock:
            self._agent_count.clear()
            self._mode_count.clear()
            self._agent_mode_count.clear()
            self._mode_latency.clear()
            self._window_100 = RollingWindow(maxlen=100)
            self._window_1000 = RollingWindow(maxlen=1000)


# ---------------------------------------------------------------------------
# Helper — telemetry block
# ---------------------------------------------------------------------------

def make_telemetry_block(
    invocation_mode: str,
    latency_ms: float,
    source: str,
    agent_id: str,
) -> Dict[str, Any]:
    """
    Build a standard telemetry block suitable for embedding in intent payloads.

    Args:
        invocation_mode: One of ``native``, ``mesh_native``, ``http_native``,
            ``mcp_bridge``, ``external_bridge``.
        latency_ms: Round-trip latency in milliseconds.
        source: The agent or system component that generated this block.
        agent_id: The target agent identifier.

    Returns:
        Dict with keys: ``invocation_mode``, ``bridge_mode``, ``source``,
        ``latency_ms``, ``delivery_latency_ms``, ``timestamp``.
    """
    is_native = invocation_mode in ("native", "mesh_native", "http_native")
    bridge_mode = "none" if is_native else (
        "mcp_compat" if invocation_mode == "mcp_bridge" else "external_compat"
    )
    now = datetime.now(timezone.utc).isoformat()
    return {
        "invocation_mode": invocation_mode,
        "bridge_mode": bridge_mode,
        "source": source,
        "agent_id": agent_id,
        "latency_ms": float(latency_ms),
        "delivery_latency_ms": float(latency_ms),
        "timestamp": now,
    }


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

path_telemetry = PathTelemetryCollector()
