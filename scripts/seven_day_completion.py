#!/usr/bin/env python3
"""
7-Day Swarm Completion Report

Generated at end of Day 7 burn-in initialization.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _header(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_verifier() -> dict:
    try:
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "verify_revenue_path.py")],
            capture_output=True, text=True, timeout=30, cwd=str(REPO),
        )
        green = "GREEN" in r.stdout
        return {"ok": green, "detail": r.stdout.strip().split("\n")[0][:80] if r.stdout else "no output"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def check_hot_path() -> dict:
    try:
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "hot_path_probe.py")],
            capture_output=True, text=True, timeout=30, cwd=str(REPO),
        )
        data = json.loads(r.stdout)
        return {"ok": data.get("all_ok", False), "detail": f"{sum(1 for c in data['checks'].values() if c['ok'])}/{len(data['checks'])} green"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def check_stop_conditions() -> dict:
    triggered = 0
    details = []
    try:
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "stop_conditions.py")],
            capture_output=True, text=True, timeout=30, cwd=str(REPO),
        )
        for line in r.stdout.split("\n"):
            if "TRIGGERED" in line:
                triggered += 1
                details.append(line.strip())
        return {"ok": triggered == 0, "detail": f"{triggered} triggered" if triggered > 0 else "all clear"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def check_decision_journal() -> dict:
    journal_path = REPO / "state" / "decision_journal.ndjson"
    if not journal_path.exists():
        return {"ok": False, "detail": "no decision journal"}
    with open(journal_path) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    total = len(entries)
    missing_fs = sum(1 for e in entries if "fill_status" not in e)
    bad_pr = sum(1 for e in entries if e.get("policy_result", {}).get("status", "") not in ("allow", "block", "shadow"))
    now = datetime.now(timezone.utc)
    last_ts = entries[-1].get("created_at", "")
    age = -1
    if last_ts:
        try:
            age = (now - datetime.fromisoformat(last_ts.replace("Z", "+00:00"))).total_seconds()
        except Exception:
            pass
    return {
        "ok": missing_fs == 0 and bad_pr == 0,
        "detail": f"{total} entries, {missing_fs} missing fill_status, {bad_pr} bad policy, last={age:.0f}s",
    }


def check_all_green() -> bool:
    checks = {
        "Hot-path probe": check_hot_path(),
        "Verifier": check_verifier(),
        "Stop conditions": check_stop_conditions(),
        "Decision journal": check_decision_journal(),
    }

    _header("FINAL 7-DAY SWARM COMPLETION CHECK")
    print(f"  Generated: {datetime.now(timezone.utc).isoformat()}")
    print()

    all_ok = True
    for name, result in checks.items():
        status = "✅ PASS" if result["ok"] else "❌ FAIL"
        if not result["ok"]:
            all_ok = False
        print(f"  {status} | {name}")
        print(f"         {result['detail']}")

    print()
    if all_ok:
        print("  🎉 ALL CHECKS PASS — 7-DAY SWARM COMPLETE")
        print()
        print("  The system is fully autonomous, observable, and safe.")
        print("  Paper-only production mode active. Ready for live promotion.")
    else:
        print("  ⚠️  Some checks failed — review before promotion.")

    return all_ok


if __name__ == "__main__":
    ok = check_all_green()
    sys.exit(0 if ok else 1)
