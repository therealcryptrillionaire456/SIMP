"""
status_board.py — writer + reader for state/status_board.json

Conventions:
- A6 owns the whole-file write (atomic replace).
- All other lanes update their own `lanes.Ax` entry via `update_lane(...)`.
- All reads return a schema-shaped object; missing fields are filled with safe defaults.
- File lives at SIMP_REPO_ROOT/state/status_board.json by default.

This module has no third-party deps. It uses file locks via fcntl to make
concurrent agent writes safe on a single host.
"""
from __future__ import annotations

import json
import os
import fcntl
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_PATH = Path(os.environ.get("SIMP_STATUS_BOARD", "state/status_board.json"))
LOCK_PATH = Path(str(DEFAULT_PATH) + ".lock")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_board() -> Dict[str, Any]:
    return {
        "updated_at": _utcnow(),
        "mode": "fully_live",
        "kill_switch": {
            "set": False,
            "path": "state/KILL",
            "last_checked": _utcnow(),
        },
        "verifier": {
            "status": "unknown",
            "last_run": _utcnow(),
            "failing_stage": None,
            "pass_rate_6h": 0.0,
        },
        "freshness": {
            "last_signal_age_s": 9_999_999,
            "last_fill_age_s": None,
            "bridge_rtt_ms_p95": None,
            "consumer_backlog": 0,
        },
        "processes": {},
        "policy": {
            "live_mode": "fully_live",
            "block_rate_1h": 0.0,
            "budget_remaining_usd": 0.0,
            "max_position_usd": 0.0,
            "daily_cap_usd": 0.0,
        },
        "lanes": {
            f"A{i}": {
                "last_cycle_at": _utcnow(),
                "last_status": "ok",
                "sev_open": 0,
                "notes": "",
            }
            for i in range(10)
        },
        "slo": {
            "signal_fresh_target_s": 60,
            "fill_fresh_target_s": 300,
            "verifier_green_target": 0.95,
            "policy_block_ceiling": 0.05,
        },
        "incidents_open": [],
    }


@contextmanager
def _locked():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def load(path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        board = _default_board()
        _atomic_write(path, board)
        return board
    with path.open("r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # corrupt; rewrite defaults but preserve corrupt copy
            path.rename(path.with_suffix(".corrupt." + str(int(time.time()))))
            board = _default_board()
            _atomic_write(path, board)
            return board


def _atomic_write(path: Path, board: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=str(path.parent), delete=False, prefix=".sb_", suffix=".tmp"
    ) as tmp:
        json.dump(board, tmp, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def write_full(board: Dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    """A6 only — whole-board replace."""
    board["updated_at"] = _utcnow()
    with _locked():
        _atomic_write(path, board)


def update_lane(lane: str, patch: Dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    """Any lane — update its own lanes.Ax block only."""
    if not (len(lane) == 2 and lane[0] == "A" and lane[1].isdigit()):
        raise ValueError(f"invalid lane id: {lane}")
    with _locked():
        board = load(path)
        lanes = board.setdefault("lanes", {})
        cur = lanes.get(lane, {})
        cur.update(patch)
        cur["last_cycle_at"] = _utcnow()
        lanes[lane] = cur
        board["updated_at"] = _utcnow()
        _atomic_write(path, board)


def set_verifier(status: str, failing_stage: Optional[str], pass_rate_6h: Optional[float] = None,
                 path: Path = DEFAULT_PATH) -> None:
    assert status in {"green", "yellow", "red", "unknown"}
    with _locked():
        board = load(path)
        v = board.setdefault("verifier", {})
        v["status"] = status
        v["failing_stage"] = failing_stage
        v["last_run"] = _utcnow()
        if pass_rate_6h is not None:
            v["pass_rate_6h"] = pass_rate_6h
        board["updated_at"] = _utcnow()
        _atomic_write(path, board)


def set_freshness(last_signal_age_s: float, last_fill_age_s: Optional[float],
                  bridge_rtt_ms_p95: Optional[float], consumer_backlog: int = 0,
                  path: Path = DEFAULT_PATH) -> None:
    with _locked():
        board = load(path)
        board["freshness"] = {
            "last_signal_age_s": last_signal_age_s,
            "last_fill_age_s": last_fill_age_s,
            "bridge_rtt_ms_p95": bridge_rtt_ms_p95,
            "consumer_backlog": consumer_backlog,
        }
        board["updated_at"] = _utcnow()
        _atomic_write(path, board)


def set_kill_switch(set_: bool, reason: str = "", kill_path: str = "state/KILL",
                    path: Path = DEFAULT_PATH) -> None:
    with _locked():
        board = load(path)
        board["kill_switch"] = {
            "set": bool(set_),
            "path": kill_path,
            "last_checked": _utcnow(),
            "reason": reason,
        }
        if set_:
            board["mode"] = "halt"
        board["updated_at"] = _utcnow()
        _atomic_write(path, board)


def open_incident(id_: str, sev: int, lane: str, summary: str,
                  path: Path = DEFAULT_PATH) -> None:
    assert 1 <= sev <= 4
    with _locked():
        board = load(path)
        inc = board.setdefault("incidents_open", [])
        inc.append({
            "id": id_,
            "sev": sev,
            "lane": lane,
            "opened_at": _utcnow(),
            "summary": summary,
        })
        board["updated_at"] = _utcnow()
        _atomic_write(path, board)


def close_incident(id_: str, path: Path = DEFAULT_PATH) -> None:
    with _locked():
        board = load(path)
        board["incidents_open"] = [i for i in board.get("incidents_open", []) if i.get("id") != id_]
        board["updated_at"] = _utcnow()
        _atomic_write(path, board)


if __name__ == "__main__":
    # quick self-test
    board = load()
    print(json.dumps(board, indent=2)[:400])
