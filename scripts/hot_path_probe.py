#!/usr/bin/env python3
"""
A2 — Hot-Path Probe

Single health check cycle against all critical system components.
Returns JSON. Exit code 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DECISION_JOURNAL = REPO / "state" / "decision_journal.ndjson"
GATE4_LOG = REPO / "logs" / "gate4_trades.jsonl"
BROKER_HEALTH_URL = "http://127.0.0.1:5555/health"


def _fetch_json(url: str, timeout: int = 5) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _age_of_last_line(path: Path) -> float | None:
    """Return age in seconds of the last line's timestamp, or None."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            lines = f.readlines()
        if not lines:
            return None
        last = lines[-1].strip()
        if not last:
            return None
        data = json.loads(last)
        ts_str = data.get("created_at") or data.get("ts") or data.get("executed_at")
        if not ts_str:
            return None
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age
    except Exception:
        return None


def check_broker() -> dict:
    data = _fetch_json(BROKER_HEALTH_URL)
    if data is None:
        return {"ok": False, "detail": "broker endpoint unreachable"}
    agents = data.get("agents_online", 0)
    return {"ok": agents > 0, "detail": f"broker healthy, {agents} agents online", "agents": agents}


def check_gate4_freshness() -> dict:
    age = _age_of_last_line(GATE4_LOG)
    if age is None:
        return {"ok": False, "detail": "no gate4 trade log found"}
    ok = age < 120
    return {"ok": ok, "detail": f"gate4 trade age={age:.0f}s (target <120s)", "age_s": round(age, 1)}


def check_decision_freshness() -> dict:
    age = _age_of_last_line(DECISION_JOURNAL)
    if age is None:
        return {"ok": False, "detail": "no decision journal found"}
    ok = age < 120
    return {"ok": ok, "detail": f"decision journal age={age:.0f}s (target <120s)", "age_s": round(age, 1)}


def check_signal_freshness() -> dict:
    """Check the decision journal for signals with age < 60s."""
    if not DECISION_JOURNAL.exists():
        return {"ok": False, "detail": "no decision journal"}
    try:
        with open(DECISION_JOURNAL) as f:
            lines = [l.strip() for l in f if l.strip()]
        if not lines:
            return {"ok": False, "detail": "empty decision journal"}
        recent = json.loads(lines[-1])
        ts_str = recent.get("created_at")
        if not ts_str:
            return {"ok": False, "detail": "no created_at in latest entry"}
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        ok = age < 60
        return {"ok": ok, "detail": f"signal age={age:.0f}s (target <60s)", "age_s": round(age, 1)}
    except Exception as e:
        return {"ok": False, "detail": f"error: {e}"}


def main():
    log_to = REPO / "state" / "metrics" / "hot_path_last.json"
    log_to.parent.mkdir(parents=True, exist_ok=True)

    checks = {
        "broker": check_broker(),
        "gate4_freshness": check_gate4_freshness(),
        "decision_freshness": check_decision_freshness(),
        "signal_freshness": check_signal_freshness(),
    }

    all_ok = all(v["ok"] for v in checks.values())
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "all_ok": all_ok,
        "checks": checks,
    }

    # Write to disk
    with open(log_to, "w") as f:
        json.dump(result, f, indent=2)

    # Also print to stdout
    print(json.dumps(result, indent=2))

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
