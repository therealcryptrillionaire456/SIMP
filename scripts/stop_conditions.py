#!/usr/bin/env python3
"""
A5 — Stop Conditions Checker

Monitors for repeated regression and suggests stopping when conditions are met.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
KILL_SWITCH_PATH = REPO / "state" / "KILL"
DECISION_JOURNAL = REPO / "state" / "decision_journal.ndjson"
METRICS_DIR = REPO / "state" / "metrics"


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def check_kill_switch() -> dict:
    exists = KILL_SWITCH_PATH.exists()
    return {
        "condition": "kill_switch_active",
        "triggered": exists,
        "detail": "KILL file present — system is halted" if exists else "KILL file absent — system can operate",
    }


def check_consecutive_red(count: int = 3) -> dict:
    """Check the last N verifier runs for consecutive RED."""
    triggered = False
    details = []
    for i in range(count):
        path = METRICS_DIR / f"verify.{i}.json" if i > 0 else METRICS_DIR / "verify.last.json"
        data = _read_json(path)
        if data is None:
            details.append(f"verify.{'last' if i==0 else i}.json: NOT FOUND")
            triggered = False
            break
        green = data.get("green", False)
        if not green:
            details.append(f"verify.{'last' if i==0 else i}.json: RED")
        else:
            details.append(f"verify.{'last' if i==0 else i}.json: GREEN")
        if not green:
            triggered = True

    return {
        "condition": "consecutive_red",
        "triggered": triggered,
        "detail": "; ".join(details[:3]),
    }


def check_signal_freshness_consistency() -> dict:
    """Check if signal has been stale for >300s for 5+ consecutive cycles."""
    if not DECISION_JOURNAL.exists():
        return {"condition": "signal_stale", "triggered": False, "detail": "no decision journal"}

    with open(DECISION_JOURNAL) as f:
        lines = [l.strip() for l in f if l.strip()]

    if len(lines) < 5:
        return {"condition": "signal_stale", "triggered": False, "detail": "fewer than 5 entries"}

    now = datetime.now(timezone.utc)
    stale_count = 0
    for line in reversed(lines[-10:]):
        entry = json.loads(line)
        ts_str = entry.get("created_at")
        if not ts_str:
            stale_count += 1
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age = (now - ts).total_seconds()
            if age > 300:
                stale_count += 1
            else:
                break  # found a fresh one
        except Exception:
            stale_count += 1

    triggered = stale_count >= 5
    return {
        "condition": "signal_stale",
        "triggered": triggered,
        "detail": f"last {stale_count} entries all >300s old (threshold: 5 consecutive)",
    }


def check_policy_block_rate() -> dict:
    """Check if 3+ of the last 10 entries are policy_blocked."""
    if not DECISION_JOURNAL.exists():
        return {"condition": "policy_block_rate", "triggered": False, "detail": "no decision journal"}

    with open(DECISION_JOURNAL) as f:
        lines = [l.strip() for l in f if l.strip()]

    recent = [json.loads(l) for l in lines[-10:]]
    blocked = sum(1 for e in recent if e.get("fill_status") == "policy_blocked")
    triggered = blocked >= 3
    return {
        "condition": "policy_block_rate",
        "triggered": triggered,
        "detail": f"{blocked}/10 recent entries blocked by policy (threshold: 3)",
    }


def main():
    checks = [
        check_kill_switch(),
        check_consecutive_red(),
        check_signal_freshness_consistency(),
        check_policy_block_rate(),
    ]

    triggered = [c["condition"] for c in checks if c["triggered"]]
    print("=" * 60)
    print("STOP CONDITIONS CHECK")
    print("=" * 60)
    for c in checks:
        status = "⚠️ TRIGGERED" if c["triggered"] else "OK"
        print(f"  {status} | {c['condition']}: {c['detail'][:80]}")

    print()
    if triggered:
        print(f"⚠️  {len(triggered)} stop condition(s) triggered: {', '.join(triggered)}")
        print("    Suggest investigating before continuing autonomous operation")
    else:
        print("✅ No stop conditions triggered — safe to continue")

    return triggered


if __name__ == "__main__":
    main()
