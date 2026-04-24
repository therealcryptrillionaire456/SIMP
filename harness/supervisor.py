#!/usr/bin/env python3
"""
supervisor.py — A0's command loop.

Runs forever. Every cycle:
  1. Refresh snapshot (A6 function).
  2. Read cycle_journal and status_board.
  3. Detect SLO breaches and escalate severities.
  4. Rebalance queue (state/queue.json) across lanes.
  5. Enforce mode transitions on hard conditions (kill switch, repeated verifier red).
  6. Emit commander_log entry.

This does not own code mutation. It is the queue + escalation authority.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent if HERE.name in {"scripts", "harness"} else HERE
sys.path.insert(0, str(REPO_ROOT))

try:
    from harness import status_board
    from harness import runtime_snapshot
except ImportError:
    sys.path.insert(0, str(HERE))
    import status_board  # type: ignore
    import runtime_snapshot  # type: ignore

STATE_DIR = Path(os.environ.get("SIMP_STATE_DIR", REPO_ROOT / "state"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_PATH = STATE_DIR / "queue.json"
COMMANDER_LOG = STATE_DIR / "commander_log.md"
MODE_PATH = Path(os.environ.get("SIMP_MODE_PATH", STATE_DIR / "mode.json"))
KILL_PATH = Path(os.environ.get("SIMP_KILL_PATH", STATE_DIR / "KILL"))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_queue() -> dict:
    if not QUEUE_PATH.exists():
        return {f"A{i}": [] for i in range(10)}
    with QUEUE_PATH.open() as f:
        return json.load(f)


def _save_queue(q: dict) -> None:
    tmp = QUEUE_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(q, f, indent=2, sort_keys=True)
    os.replace(tmp, QUEUE_PATH)


def _set_mode(mode: str, reason: str) -> None:
    MODE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MODE_PATH.open("w") as f:
        json.dump({"mode": mode, "set_at": _utcnow(), "reason": reason}, f, indent=2)


def _append_commander(line: str) -> None:
    COMMANDER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COMMANDER_LOG.open("a") as f:
        f.write(f"[{_utcnow()}] {line}\n")


def decide_escalations(board: dict) -> list[str]:
    """Return list of commander actions taken this cycle."""
    actions: list[str] = []

    # 1. Kill switch sovereign
    if board["kill_switch"]["set"] and board["mode"] != "halt":
        _set_mode("halt", "kill switch observed")
        actions.append("MODE -> halt (kill switch)")

    # 2. Verifier red for two snapshots → force shadow
    pass_rate = board["verifier"].get("pass_rate_6h", 0.0)
    if board["verifier"]["status"] == "red" and board["mode"] == "fully_live" and pass_rate < 0.5:
        _set_mode("shadow", "verifier red and pass_rate_6h < 0.5")
        actions.append("MODE -> shadow (verifier regression)")

    # 3. Budget exhausted → shadow
    pol = board.get("policy", {})
    cap = float(pol.get("daily_cap_usd", 0) or 0)
    remaining = float(pol.get("budget_remaining_usd", 0) or 0)
    if cap > 0 and remaining / cap <= 0.0 and board["mode"] == "fully_live":
        _set_mode("shadow", "daily budget exhausted")
        actions.append("MODE -> shadow (budget exhausted)")

    return actions


def rebalance_queue(board: dict) -> dict:
    q = _load_queue()
    # If a lane has reported blocked twice in a row (via status_board notes containing 'blocked'),
    # prepend a diagnostic task.
    for lane_id, lane in board.get("lanes", {}).items():
        if lane.get("last_status") == "blocked":
            items = q.setdefault(lane_id, [])
            if not any(t.get("tag") == "unblock" for t in items):
                items.insert(0, {
                    "id": f"unblock_{lane_id}_{int(time.time())}",
                    "tag": "unblock",
                    "why": lane.get("notes", "blocked"),
                    "action": "post a diagnostic journal entry; then attempt smallest forward step",
                })
    return q


def cycle_once() -> None:
    board = runtime_snapshot.snapshot_once()
    actions = decide_escalations(board)
    q = rebalance_queue(board)
    _save_queue(q)
    if actions:
        for a in actions:
            _append_commander(a)
    # heartbeat
    _append_commander(
        f"heartbeat mode={board['mode']} verifier={board['verifier']['status']} "
        f"signal_age={board['freshness']['last_signal_age_s']:.0f}s "
        f"fill_age={board['freshness']['last_fill_age_s']} "
        f"budget=${board['policy']['budget_remaining_usd']:.2f}"
    )


def main() -> int:
    interval = int(os.environ.get("SIMP_SUPERVISOR_INTERVAL_S", "60"))
    while True:
        try:
            cycle_once()
        except Exception as e:
            _append_commander(f"SUPERVISOR ERROR: {e!r}")
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
