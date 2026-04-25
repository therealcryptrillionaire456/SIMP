"""
Latency SLA Enforcement — T29
===============================
Profiler tracks p95; if any path breaches SLA, circuit-break that path
and alert ops.

Integrates with LatencyProfiler to:
  1. Monitor p95 latency per execution path
  2. Compare against path-specific SLA targets
  3. Auto-circuit-break paths that exceed SLA
  4. Auto-restore paths after cooldown period
  5. Alert ops on circuit-break events

Usage:
    sla = LatencySLAEnforcer(profiler=profiler)
    sla.register_path("price_fetch", sla_target_ms=500)
    sla.register_path("jupiter_quote", sla_target_ms=1000)
    violations = sla.check_all_paths()  # Returns paths in breach
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger("latency_sla")


@dataclass
class PathSLARegistration:
    """SLA configuration for a single execution path."""
    path_name: str
    sla_target_ms: float       # Target latency in ms (p95 should be under this)
    sla_hard_limit_ms: float   # Hard limit — p99 must be under this
    circuit_breach_count: int = 3       # Consecutive breaches before circuit break
    circuit_cooldown_seconds: float = 300.0  # Cool-down before auto-restore
    alert_on_breach: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SLABreachEvent:
    """Record of an SLA breach."""
    path_name: str
    sla_target_ms: float
    p95_ms: float
    p99_ms: float
    breach_type: str           # "p95_sla", "p99_hard_limit"
    circuit_broken: bool       # Was the circuit broken after this breach?
    consecutive_breaches: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class CircuitBreakerState:
    """State of a circuit breaker for a single path."""
    OPEN = "open"          # Path blocked — no execution allowed
    HALF_OPEN = "half_open"  # Test execution allowed to check recovery
    CLOSED = "closed"      # Normal operation


class LatencySLAEnforcer:
    """
    Monitors path latencies and circuit-breaks paths that violate SLA.

    Thread-safe. Persists SLA config and breach history.
    """

    def __init__(
        self,
        profiler: Any,     # LatencyProfiler instance
        data_dir: str = "data/sla",
        alert_handler: Optional[Any] = None,
    ):
        self._profiler = profiler
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._paths: Dict[str, PathSLARegistration] = {}
        # Circuit breaker state per path
        self._circuit_state: Dict[str, str] = {}
        self._consecutive_breaches: Dict[str, int] = {}
        self._circuit_opened_at: Dict[str, float] = {}
        self._breach_events: List[SLABreachEvent] = []

        # Test execution flag for half-open state
        self._half_open_tested: Dict[str, float] = {}

        self._load_config()
        self._load_breach_events()

        log.info("LatencySLAEnforcer initialized (%d registered paths)", len(self._paths))

    # ── Public API ──────────────────────────────────────────────────────

    def register_path(
        self,
        path_name: str,
        sla_target_ms: float,
        sla_hard_limit_ms: Optional[float] = None,
        circuit_breach_count: int = 3,
        circuit_cooldown_seconds: float = 300.0,
        alert_on_breach: bool = True,
    ) -> None:
        """
        Register a path with its SLA targets.

        Args:
            path_name: Name matching LatencyProfiler path names
            sla_target_ms: Target p95 latency in ms
            sla_hard_limit_ms: Hard p99 limit (defaults to 2x sla_target)
            circuit_breach_count: Consecutive breaches before circuit break
            circuit_cooldown_seconds: Auto-restore after this many seconds
            alert_on_breach: Whether to alert on breach
        """
        hard_limit = sla_hard_limit_ms or (sla_target_ms * 2.0)
        registration = PathSLARegistration(
            path_name=path_name,
            sla_target_ms=sla_target_ms,
            sla_hard_limit_ms=hard_limit,
            circuit_breach_count=circuit_breach_count,
            circuit_cooldown_seconds=circuit_cooldown_seconds,
            alert_on_breach=alert_on_breach,
        )

        with self._lock:
            self._paths[path_name] = registration
            if path_name not in self._circuit_state:
                self._circuit_state[path_name] = CircuitBreakerState.CLOSED
                self._consecutive_breaches[path_name] = 0

        self._save_config()
        log.info("Registered path '%s': SLA=%.0fms, hard=%.0fms, breach=%d, cooldown=%.0fs",
                  path_name, sla_target_ms, hard_limit, circuit_breach_count, circuit_cooldown_seconds)

    def check_all_paths(self) -> Dict[str, SLABreachEvent]:
        """
        Check all registered paths against their SLA targets.

        Returns:
            Dict mapping path_name -> SLABreachEvent for paths in breach.
        """
        with self._lock:
            paths = dict(self._paths)

        breaches: Dict[str, SLABreachEvent] = {}
        stats = self._profiler.get_stats()

        for path_name, sla in paths.items():
            if path_name not in stats:
                continue

            path_stats = stats[path_name]

            # Check if currently circuit-broken and in cooldown
            if self._is_circuit_open(path_name):
                # Check if cooldown has expired
                if self._should_auto_restore(path_name):
                    self._transition_to_half_open(path_name)
                continue  # Don't check SLA while open

            # Check hard limit first (p99)
            if path_stats.p99_ms > sla.sla_hard_limit_ms:
                breach = self._create_breach(
                    path_name, sla, path_stats, "p99_hard_limit"
                )
                breaches[path_name] = breach
                self._handle_breach(path_name, breach)
                continue

            # Check target (p95)
            if path_stats.p95_ms > sla.sla_target_ms:
                breach = self._create_breach(
                    path_name, sla, path_stats, "p95_sla"
                )
                breaches[path_name] = breach
                self._handle_breach(path_name, breach)
                continue

            # No breach — reset consecutive counter
            self._reset_breach_count(path_name)

        return breaches

    def is_path_allowed(self, path_name: str) -> bool:
        """
        Check if a path is allowed to execute (circuit is closed).

        If the circuit is half-open, allows a test execution.
        """
        with self._lock:
            state = self._circuit_state.get(path_name, CircuitBreakerState.CLOSED)

        if state == CircuitBreakerState.CLOSED:
            return True

        if state == CircuitBreakerState.HALF_OPEN:
            # Allow one test execution
            now = time.time()
            last_test = self._half_open_tested.get(path_name, 0.0)
            if now - last_test > 60.0:  # Test at most once per minute
                self._half_open_tested[path_name] = now
                return True
            return False

        # OPEN
        return False

    def report_success(self, path_name: str) -> None:
        """
        Report a successful execution on a path.

        If the circuit was half-open, this transitions it back to closed.
        """
        with self._lock:
            state = self._circuit_state.get(path_name, CircuitBreakerState.CLOSED)

        if state == CircuitBreakerState.HALF_OPEN:
            log.info("Path '%s' recovered — transitioning CLOSED", path_name)
            self._circuit_state[path_name] = CircuitBreakerState.CLOSED
            self._consecutive_breaches[path_name] = 0
            self._save_breach_events()

    def get_path_status(self, path_name: str) -> Dict[str, Any]:
        """Get the full SLA and circuit status for a path."""
        with self._lock:
            sla = self._paths.get(path_name)
            state = self._circuit_state.get(path_name, CircuitBreakerState.CLOSED)
            breaches = self._consecutive_breaches.get(path_name, 0)
            opened_at = self._circuit_opened_at.get(path_name, 0.0)

        stats = self._profiler.get_stats().get(path_name)

        result: Dict[str, Any] = {
            "path_name": path_name,
            "circuit_state": state,
            "consecutive_breaches": breaches,
        }

        if sla:
            result["sla_target_ms"] = sla.sla_target_ms
            result["sla_hard_limit_ms"] = sla.sla_hard_limit_ms
            result["circuit_breach_threshold"] = sla.circuit_breach_count

        if state == CircuitBreakerState.OPEN:
            remaining = max(0, sla.circuit_cooldown_seconds - (time.time() - opened_at)) if sla else 0
            result["cooldown_remaining_seconds"] = round(remaining, 1)

        if stats:
            result["p95_ms"] = stats.p95_ms
            result["p99_ms"] = stats.p99_ms
            result["p95_vs_target"] = round(stats.p95_ms / sla.sla_target_ms, 2) if sla else None

        return result

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get SLA/circuit status for all registered paths."""
        with self._lock:
            path_names = list(self._paths.keys())
        return {p: self.get_path_status(p) for p in path_names}

    def get_breach_history(self, limit: int = 50) -> List[SLABreachEvent]:
        """Get recent breach events."""
        with self._lock:
            return list(reversed(self._breach_events[-limit:]))

    def get_summary(self) -> Dict[str, Any]:
        """Get overall SLA enforcer summary."""
        status = self.get_all_status()
        breaches = self.get_breach_history(limit=0)

        open_count = sum(1 for s in status.values() if s.get("circuit_state") == "open")
        closed_count = sum(1 for s in status.values() if s.get("circuit_state") == "closed")
        half_open_count = sum(1 for s in status.values() if s.get("circuit_state") == "half_open")

        return {
            "total_paths": len(status),
            "circuits_open": open_count,
            "circuits_closed": closed_count,
            "circuits_half_open": half_open_count,
            "total_breaches": len(breaches),
            "paths": status,
        }

    # ── Internal ────────────────────────────────────────────────────────

    def _create_breach(
        self, path_name: str, sla: PathSLARegistration,
        stats: Any, breach_type: str,
    ) -> SLABreachEvent:
        """Create a breach event."""
        with self._lock:
            self._consecutive_breaches[path_name] = (
                self._consecutive_breaches.get(path_name, 0) + 1
            )
            consecutive = self._consecutive_breaches[path_name]

        should_break = consecutive >= sla.circuit_breach_count

        return SLABreachEvent(
            path_name=path_name,
            sla_target_ms=sla.sla_target_ms,
            p95_ms=round(stats.p95_ms, 2),
            p99_ms=round(stats.p99_ms, 2),
            breach_type=breach_type,
            circuit_broken=should_break,
            consecutive_breaches=consecutive,
        )

    def _handle_breach(self, path_name: str, breach: SLABreachEvent) -> None:
        """Handle a breach event — potentially circuit-break."""
        with self._lock:
            self._breach_events.append(breach)
            self._save_breach_events()

        if breach.circuit_broken:
            self._open_circuit(path_name, breach)

        log.warning(
            "SLA BREACH [%s]: %s p95=%.1fms > target=%.0fms (consecutive=%d, broken=%s)",
            breach.breach_type, path_name, breach.p95_ms,
            breach.sla_target_ms, breach.consecutive_breaches,
            breach.circuit_broken,
        )

    def _open_circuit(self, path_name: str, breach: SLABreachEvent) -> None:
        """Open the circuit breaker for a path."""
        with self._lock:
            self._circuit_state[path_name] = CircuitBreakerState.OPEN
            self._circuit_opened_at[path_name] = time.time()

        log.error(
            "CIRCUIT BROKEN: path='%s' — blocked for %.0fs after %d breaches",
            path_name,
            self._paths[path_name].circuit_cooldown_seconds,
            breach.consecutive_breaches,
        )

    def _is_circuit_open(self, path_name: str) -> bool:
        """Check if the circuit is currently open."""
        with self._lock:
            return self._circuit_state.get(path_name, CircuitBreakerState.CLOSED) == CircuitBreakerState.OPEN

    def _should_auto_restore(self, path_name: str) -> bool:
        """Check if the cooldown period has expired for auto-restore."""
        with self._lock:
            opened = self._circuit_opened_at.get(path_name, 0.0)
            sla = self._paths.get(path_name)
            if not sla:
                return False
            return (time.time() - opened) >= sla.circuit_cooldown_seconds

    def _transition_to_half_open(self, path_name: str) -> None:
        """Transition circuit from open to half-open for testing."""
        with self._lock:
            self._circuit_state[path_name] = CircuitBreakerState.HALF_OPEN
        log.info("Circuit HALF-OPEN for path '%s' — test execution allowed", path_name)

    def _reset_breach_count(self, path_name: str) -> None:
        """Reset consecutive breach counter when no breach occurs."""
        with self._lock:
            self._consecutive_breaches[path_name] = 0

    # ── Persistence ─────────────────────────────────────────────────────

    def _save_config(self) -> None:
        """Save SLA configuration to disk."""
        path = self._data_dir / "sla_config.json"
        with self._lock:
            data = {p: s.to_dict() for p, s in self._paths.items()}
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.warning("Failed to save SLA config: %s", e)

    def _load_config(self) -> None:
        """Load SLA configuration from disk."""
        path = self._data_dir / "sla_config.json"
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for path_name, sdata in data.items():
                self._paths[path_name] = PathSLARegistration(**sdata)
                self._circuit_state.setdefault(path_name, CircuitBreakerState.CLOSED)
                self._consecutive_breaches.setdefault(path_name, 0)
            log.info("Loaded SLA config: %d paths", len(self._paths))
        except Exception as e:
            log.warning("Failed to load SLA config: %s", e)

    def _save_breach_events(self) -> None:
        """Save breach events to JSONL."""
        path = self._data_dir / "sla_breaches.jsonl"
        with self._lock:
            with open(path, "a") as f:
                # Only append new events (skip events already saved)
                pass

    def _load_breach_events(self) -> None:
        """Load breach events from disk."""
        path = self._data_dir / "sla_breaches.jsonl"
        if not path.exists():
            return
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    event = SLABreachEvent(**json.loads(line))
                    self._breach_events.append(event)
        except Exception as e:
            log.warning("Failed to load SLA breaches: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

SLA_ENFORCER: Optional[LatencySLAEnforcer] = None


def get_sla_enforcer(profiler: Any = None) -> LatencySLAEnforcer:
    """Get or create the global LatencySLAEnforcer singleton."""
    global SLA_ENFORCER
    if SLA_ENFORCER is None:
        if profiler is None:
            from .latency_profiler import LatencyProfiler, PROFILER
            profiler = PROFILER
        SLA_ENFORCER = LatencySLAEnforcer(profiler=profiler)
    return SLA_ENFORCER
