"""Shared observability truth helpers.

Single source of truth for:
  - process health checks
  - freshness calculations
  - stage result reporting

Used by: runtime_snapshot.py, verify_revenue_path.py, hot_path_probe.py, status_board
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════
# Process health
# ═══════════════════════════════════════════════════════════════════════════

PROCESS_PATTERNS = {
    "broker": r"bin/start_server",
    "http_server": r"bin/start_server",
    "orchestration_loop": r"closed_loop_scheduler",
    "dashboard": r"dashboard[./]server",
    "projectx": r"projectx_guard_server",
    "gate4_inbox": r"gate4_inbox_consumer",
    "signal_bridge": r"quantum_signal_bridge",
    "decision_adapter": r"decision_adapter",
    "signal_cycle": r"signal_cycle",
    "bullbear": r"bullbear",
    "gemma": r"kashclaw_gemma",
}


def check_process(name: str, pattern: str) -> bool:
    """Check if a process matching the pattern is running via pgrep.

    Returns True if at least one matching process is found.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() != b""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def check_all_processes() -> Dict[str, bool]:
    """Check all known process patterns.

    Returns dict of {process_name: is_running}.
    """
    return {name: check_process(name, pat) for name, pat in PROCESS_PATTERNS.items()}


# ═══════════════════════════════════════════════════════════════════════════
# Freshness
# ═══════════════════════════════════════════════════════════════════════════

def tail_ndjson(path: Path, n: int = 3) -> List[Dict[str, Any]]:
    """Read the last N records from an NDJSON file.

    Returns empty list if the file is missing or empty.
    """
    if not path.exists() or path.stat().st_size == 0:
        return []

    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue

    return records[-n:] if len(records) > n else records


def freshness(ts_iso: str) -> float:
    """Return seconds since the given ISO 8601 timestamp.

    Returns a large number (>1e9) if the timestamp is unparseable.
    """
    if not ts_iso:
        return float("inf")
    try:
        dt = datetime.fromisoformat(ts_iso)
        return time.time() - dt.timestamp()
    except (ValueError, TypeError, OverflowError):
        return float("inf")


def journal_last_age(path_str: str = "state/decision_journal.ndjson") -> Optional[float]:
    """Return age in seconds of the most recent decision journal entry."""
    records = tail_ndjson(Path(path_str), n=1)
    if not records:
        return None
    ts = records[0].get("created_at") or records[0].get("executed_at")
    if not ts:
        return None
    return freshness(ts)


# ═══════════════════════════════════════════════════════════════════════════
# Stage results
# ═══════════════════════════════════════════════════════════════════════════

class StageResult:
    """Result of a single verification stage."""

    def __init__(self, name: str, ok: bool, detail: str = ""):
        self.name = name
        self.ok = ok
        self.detail = detail

    @property
    def terminal_ok(self) -> bool:
        """A terminal stage passes only if ok is True."""
        return self.ok

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


# ═══════════════════════════════════════════════════════════════════════════
# Mode and kill-switch
# ═══════════════════════════════════════════════════════════════════════════

MODE_PATH = Path("state/mode.json")
KILL_PATH = Path("state/KILL")


def load_mode() -> Dict[str, Any]:
    """Load the current mode from state/mode.json."""
    if MODE_PATH.exists():
        try:
            with open(MODE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"mode": "unknown"}


def kill_switch_active() -> bool:
    """Return True if the kill switch file exists."""
    return KILL_PATH.exists()


# ═══════════════════════════════════════════════════════════════════════════
# Limits
# ═══════════════════════════════════════════════════════════════════════════

LIMITS_PATH = Path("state/alert_rules.json")


def load_limits() -> Dict[str, Any]:
    """Load alert threshold limits."""
    if LIMITS_PATH.exists():
        try:
            with open(LIMITS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}
