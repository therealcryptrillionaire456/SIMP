#!/usr/bin/env python3
"""
runtime_snapshot.py — one canonical snapshot writer, owned by A6.

Collects:
  - process health (broker, http_server, orchestration_loop, gate4_inbox_consumer, signal bridge)
  - freshness ages from decision_journal
  - verifier status (by invoking harness/verify_revenue_path.py --json)
  - mode + kill switch
  - policy: budget remaining, block rate 1h, limits from contracts/live_limits.json

Writes: state/status_board.json via harness/status_board.py, and appends one line
to state/metrics/snapshots.ndjson.

Safe to run every 30s during burn-in.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent if HERE.name in {"scripts", "harness"} else HERE
sys.path.insert(0, str(REPO_ROOT))

try:
    from harness import status_board
    from harness import verify_revenue_path as verifier
except ImportError:
    sys.path.insert(0, str(HERE))
    import status_board  # type: ignore
    import verify_revenue_path as verifier  # type: ignore

STATE_DIR = Path(os.environ.get("SIMP_STATE_DIR", REPO_ROOT / "state"))
METRICS_DIR = STATE_DIR / "metrics"
METRICS_DIR.mkdir(parents=True, exist_ok=True)
DECISION_JOURNAL = STATE_DIR / "decision_journal.ndjson"
LIMITS_PATH = Path(os.environ.get("SIMP_LIMITS_PATH", REPO_ROOT / "contracts" / "live_limits.json"))
MODE_PATH = Path(os.environ.get("SIMP_MODE_PATH", STATE_DIR / "mode.json"))
KILL_PATH = Path(os.environ.get("SIMP_KILL_PATH", STATE_DIR / "KILL"))


PROCESSES = {
    "broker":               r"bin/start_server|simp[./]server[./]broker",
    "http_server":          r"bin/start_server|simp[./]server[./]http_server|uvicorn.*http_server",
    "orchestration_loop":   r"orchestration_loop|closed_loop_scheduler",
    "gate4_inbox_consumer": r"gate4_inbox_consumer",
    "signal_bridge":        r"quantum_signal_bridge",
    "dashboard":            r"dashboard[./]server|uvicorn.*dashboard",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pid_for(pattern: str) -> Optional[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True, timeout=3).strip()
        if not out:
            return None
        # take first
        return int(out.splitlines()[0])
    except Exception:
        return None


def _age_seconds(iso_ts: str) -> float:
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return float("inf")
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())


def _tail(path: Path, n: int = 500) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, 2_000_000)
            f.seek(size - block)
            lines = f.read().decode("utf-8", errors="replace").splitlines()
        out = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
            if len(out) >= n:
                break
        out.reverse()
        return out
    except Exception:
        return []


def compute_freshness(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    last_signal_age: Optional[float] = None
    last_fill_age: Optional[float] = None
    for e in reversed(entries):
        if last_signal_age is None and "decision_id" in e and "created_at" in e:
            last_signal_age = _age_seconds(e["created_at"])
        if last_fill_age is None and e.get("fill_status") == "executed" and e.get("executed_at"):
            last_fill_age = _age_seconds(e["executed_at"])
        if last_signal_age is not None and last_fill_age is not None:
            break
    return {
        "last_signal_age_s": last_signal_age if last_signal_age is not None else 9_999_999,
        "last_fill_age_s": last_fill_age,
        "bridge_rtt_ms_p95": None,
        "consumer_backlog": 0,
    }


def compute_policy(entries: List[Dict[str, Any]], limits: Dict[str, Any]) -> Dict[str, Any]:
    one_hour_ago = 3600.0
    fills_1h = [e for e in entries
                if e.get("fill_status") and _age_seconds(e.get("executed_at", _utcnow())) <= one_hour_ago]
    blocks = [e for e in fills_1h if e.get("fill_status") == "policy_blocked"]
    total = len(fills_1h)
    block_rate = (len(blocks) / total) if total else 0.0

    # Budget: sum notional of executed fills today vs daily cap
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    spent = 0.0
    for e in entries:
        if e.get("fill_status") != "executed":
            continue
        ts = e.get("executed_at", "")
        if not ts.startswith(today):
            continue
        spent += abs(float(e.get("fill_price", 0)) * float(e.get("fill_size", 0)))
    cap = float(limits.get("daily_cap_usd", 0.0))
    remaining = max(0.0, cap - spent)

    return {
        "live_mode": _load_mode(),
        "block_rate_1h": round(block_rate, 4),
        "budget_remaining_usd": round(remaining, 2),
        "max_position_usd": float(limits.get("max_position_usd", 0.0)),
        "daily_cap_usd": cap,
    }


def _load_mode() -> str:
    if not MODE_PATH.exists():
        return "fully_live"
    try:
        with MODE_PATH.open() as f:
            return json.load(f).get("mode", "fully_live")
    except Exception:
        return "fully_live"


def _load_limits() -> Dict[str, Any]:
    if not LIMITS_PATH.exists():
        return {}
    with LIMITS_PATH.open() as f:
        return json.load(f)


def collect_processes() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for name, pat in PROCESSES.items():
        pid = _pid_for(pat)
        out[name] = {
            "pid": pid,
            "state": "up" if pid else "down",
            "last_restart": None,
        }
    return out


def snapshot_once() -> Dict[str, Any]:
    limits = _load_limits()
    entries = _tail(DECISION_JOURNAL, n=1000)
    freshness = compute_freshness(entries)
    policy = compute_policy(entries, limits)
    processes = collect_processes()

    # Run verifier (in-process)
    v_report = verifier.run()
    v_status = "green" if v_report.green else "red"
    v_failing = next((s.name for s in v_report.stages if not s.ok and not s.terminal_ok), None)

    # Write full board
    board = {
        "updated_at": _utcnow(),
        "mode": _load_mode(),
        "kill_switch": {
            "set": KILL_PATH.exists(),
            "path": str(KILL_PATH),
            "last_checked": _utcnow(),
        },
        "verifier": {
            "status": v_status,
            "last_run": _utcnow(),
            "failing_stage": v_failing,
            "pass_rate_6h": _pass_rate_6h(),
        },
        "freshness": freshness,
        "processes": processes,
        "policy": policy,
        "lanes": status_board.load().get("lanes", {}),  # preserve lanes
        "slo": limits.get("slo", {}),
        "incidents_open": status_board.load().get("incidents_open", []),
    }
    status_board.write_full(board)

    # Append metrics line
    metrics_line = {
        "ts": board["updated_at"],
        "verifier": v_status,
        "failing_stage": v_failing,
        "last_signal_age_s": freshness["last_signal_age_s"],
        "last_fill_age_s": freshness["last_fill_age_s"],
        "block_rate_1h": policy["block_rate_1h"],
        "budget_remaining_usd": policy["budget_remaining_usd"],
        "procs_down": [name for name, st in processes.items() if st["state"] != "up"],
    }
    with (METRICS_DIR / "snapshots.ndjson").open("a") as f:
        f.write(json.dumps(metrics_line) + "\n")
    return board


def _pass_rate_6h() -> float:
    path = METRICS_DIR / "snapshots.ndjson"
    if not path.exists():
        return 0.0
    cutoff = 6 * 3600
    total = 0
    green = 0
    try:
        with path.open() as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if _age_seconds(r.get("ts", "")) > cutoff:
                    continue
                total += 1
                if r.get("verifier") == "green":
                    green += 1
    except Exception:
        return 0.0
    return round(green / total, 4) if total else 0.0


def main(argv: List[str]) -> int:
    loop = "--loop" in argv
    interval = 30
    for i, a in enumerate(argv):
        if a == "--interval" and i + 1 < len(argv):
            try:
                interval = int(argv[i + 1])
            except ValueError:
                pass

    if not loop:
        board = snapshot_once()
        print(json.dumps({
            "verifier": board["verifier"]["status"],
            "freshness": board["freshness"],
            "policy": board["policy"],
            "mode": board["mode"],
            "kill": board["kill_switch"]["set"],
            "procs_down": [n for n, s in board["processes"].items() if s["state"] != "up"],
        }, indent=2))
        return 0

    while True:
        try:
            snapshot_once()
        except Exception as e:
            print(f"[snapshot] error: {e}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
