#!/usr/bin/env python3.10
"""
safety_bridge.py — read-only link between contracts/live_limits.json and running policy.

Purpose: makes live_limits.json values discoverable by policy code without
changing the policy code itself. A5 owns this file; it emits a status report
showing whether runtime policy matches configured limits.

Usage:
    python3 state/safety_bridge.py     # print compliance report
    python3 state/safety_bridge.py --json   # JSON output for status board
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO = Path(__file__).resolve().parent.parent
LIMITS_PATH = REPO / "contracts" / "live_limits.json"
MODE_PATH = REPO / "state" / "mode.json"
KILL_SWITCH_PATHS = [
    REPO / "data" / "KILL_SWITCH",
    REPO / "state" / "KILL",
]


def load_limits() -> Dict[str, Any]:
    if LIMITS_PATH.exists():
        return json.loads(LIMITS_PATH.read_text())
    return {}


def load_mode() -> Optional[str]:
    if MODE_PATH.exists():
        try:
            return json.loads(MODE_PATH.read_text()).get("mode")
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def check_kill_switch() -> Dict[str, Any]:
    for p in KILL_SWITCH_PATHS:
        if p.exists():
            reason = ""
            try:
                data = json.loads(p.read_text())
                reason = data.get("reason", "")
            except (json.JSONDecodeError, TypeError):
                reason = "(file exists, unparseable)"
            return {"set": True, "path": str(p), "reason": reason}
    return {"set": False, "path": " — ", "reason": ""}


def check_policy_compliance(limits: Dict[str, Any]) -> Dict[str, Any]:
    """Check runtime environment against contract limits."""
    issues = []

    # Kill switch path
    configured_ks = limits.get("kill_switch_path", "state/KILL")
    actual_ks_env = os.environ.get("SIMP_KILL_SWITCH_PATH", "data/KILL_SWITCH")
    if configured_ks != actual_ks_env:
        issues.append({
            "field": "kill_switch_path",
            "expected": configured_ks,
            "actual_env": actual_ks_env,
            "severity": "SEV2",
            "note": "trading_policy.py default is data/KILL_SWITCH; contract says state/KILL",
        })

    # Mode file
    mode = load_mode()
    if mode and mode != limits.get("mode_default", "fully_live"):
        issues.append({
            "field": "mode",
            "expected": limits.get("mode_default"),
            "actual": mode,
            "severity": "INFO",
            "note": f"Mode is {mode}, contract default is {limits.get('mode_default')}",
        })

    return {
        "compliant": len(issues) == 0,
        "issues": issues,
    }


def run_check() -> Dict[str, Any]:
    limits = load_limits()
    ks = check_kill_switch()
    compliance = check_policy_compliance(limits)

    return {
        "checked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "limits_file": str(LIMITS_PATH),
        "limits_loaded": bool(limits),
        "mode": load_mode(),
        "kill_switch": ks,
        "limits": {
            "daily_cap_usd": limits.get("daily_cap_usd"),
            "max_position_usd": limits.get("max_position_usd"),
            "max_per_strategy_gross_usd": limits.get("max_per_strategy_gross_usd"),
            "max_orders_per_minute": limits.get("max_orders_per_minute"),
        },
        "compliance": compliance,
    }


if __name__ == "__main__":
    report = run_check()
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print("═══ Safety Bridge Report ═══")
        print(f"Mode:          {report['mode']}")
        print(f"Kill Switch:   {'⚠️ SET' if report['kill_switch']['set'] else '✅ NOT SET'}")
        if report['kill_switch']['set']:
            print(f"  Path:        {report['kill_switch']['path']}")
            print(f"  Reason:      {report['kill_switch']['reason']}")
        print(f"Daily Cap:     {report['limits']['daily_cap_usd']}")
        print(f"Max Position:  {report['limits']['max_position_usd']}")
        print(f"Compliant:     {'✅' if report['compliance']['compliant'] else '❌'}")
        for issue in report['compliance']['issues']:
            print(f"  [{issue['severity']}] {issue['field']}: {issue['note']}")
