#!/usr/bin/env python3
"""
A9 — No-Human-Touch Test

Simulates one shift with no human intervention by running
all automatic checks in sequence and reporting survivability.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(script_name: str, timeout: int = 30) -> dict:
    """Run a script and return its output and exit code."""
    path = REPO / "scripts" / script_name
    if not path.exists():
        return {"script": script_name, "status": "NOT_FOUND", "exit_code": -1, "output": ""}
    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO),
        )
        return {
            "script": script_name,
            "status": "OK" if result.returncode == 0 else "FAIL",
            "exit_code": result.returncode,
            "output": (result.stdout + result.stderr)[:500],
        }
    except subprocess.TimeoutExpired:
        return {"script": script_name, "status": "TIMEOUT", "exit_code": -1, "output": ""}
    except Exception as e:
        return {"script": script_name, "status": "ERROR", "exit_code": -1, "output": str(e)}


def main():
    print("=" * 60)
    print("NO-HUMAN-TOUCH TEST (simulated shift)")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    print()

    phases = [
        ("Phase 1/5 — Hot-path probe", "hot_path_probe.py"),
        ("Phase 2/5 — Verifier run", "../scripts/verify_revenue_path.py"),
        ("Phase 3/5 — Stop conditions", "stop_conditions.py"),
        ("Phase 4/5 — Handoff generation", "generate_handoff.py"),
        ("Phase 5/5 — Status board check", None),  # manual check below
    ]

    results = []
    for phase_name, script in phases:
        print(f"[{phase_name}]")
        if script is None:
            # Check status board manually
            board_path = REPO / "state" / "status_board.json"
            if board_path.exists():
                with open(board_path) as f:
                    board = json.load(f)
                lanes = board.get("lanes", {})
                ok_count = sum(1 for v in lanes.values() if v.get("last_status") == "ok")
                results.append({
                    "script": "status_board",
                    "status": "OK" if ok_count == len(lanes) else "DEGRADED",
                    "exit_code": 0 if ok_count == len(lanes) else 1,
                    "output": f"{ok_count}/{len(lanes)} lanes ok",
                })
                print(f"  Status: {ok_count}/{len(lanes)} lanes ok")
            else:
                results.append({"script": "status_board", "status": "NOT_FOUND", "exit_code": 1, "output": ""})
                print("  Status board NOT FOUND")
        else:
            result = _run(script)
            results.append(result)
            status_symbol = "✅" if result["status"] == "OK" else "❌" if result["status"] == "FAIL" else "⚠️"
            print(f"  {status_symbol} {result['status']} (exit={result['exit_code']})")
            if result["output"]:
                for line in result["output"].splitlines()[:5]:
                    print(f"    {line}")

        print()
        if phase_name != phases[-1][0]:
            time.sleep(3)

    # Summary
    print("=" * 60)
    print("NO-HUMAN-TOUCH TEST RESULTS")
    print("=" * 60)
    all_ok = all(r["status"] == "OK" for r in results)
    for r in results:
        status = "✅" if r["status"] == "OK" else "❌" if r["status"] == "FAIL" else "⚠️"
        print(f"  {status} {r['script']}: {r['status']}")

    print()
    if all_ok:
        print("✅ SYSTEM SURVIVES WITHOUT HUMAN TOUCH")
        print("   All checks pass. Autonomous operation is viable.")
        sys.exit(0)
    else:
        failing = [r["script"] for r in results if r["status"] != "OK"]
        print(f"❌ SYSTEM NEEDS HUMAN TOUCH ({len(failing)} failures)")
        for f in failing:
            print(f"   - {f}")
        print("   Review failures before enabling fully autonomous mode.")
        sys.exit(1)


if __name__ == "__main__":
    main()
