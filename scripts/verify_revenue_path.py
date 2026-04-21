#!/usr/bin/env python3.10
"""
Opinionated hot-path verification for revenue readiness.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from simp.exchange import coinbase_dns_status
from runtime_snapshot import build_snapshot

TRADE_LOG = REPO / "logs" / "gate4_trades.jsonl"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def build_report(max_trade_age_minutes: int = 30) -> dict[str, Any]:
    snapshot = build_snapshot()
    latest_trade = snapshot["gate4"]["latest_trade"] or {}
    latest_success = snapshot["gate4"]["latest_successful_trade"] or {}
    state = snapshot["gate4"]["state"] or {}

    checks: dict[str, dict[str, Any]] = {
        "broker_up": {"ok": snapshot["services"]["broker"]["ok"]},
        "dashboard_up": {"ok": snapshot["services"]["dashboard"]["ok"]},
        "projectx_up": {"ok": snapshot["services"]["projectx"]["ok"]},
        "gate4_consumer_running": {"ok": snapshot["processes"]["gate4_consumer"] > 0},
        "quantum_bridge_running": {"ok": snapshot["processes"]["quantum_signal_bridge"] > 0},
        "coinbase_dns_ok": {"ok": snapshot["coinbase_dns"]["ok"], "addresses": snapshot["coinbase_dns"]["addresses"]},
        "latest_trade_present": {"ok": bool(latest_trade)},
        "latest_successful_trade_present": {"ok": bool(latest_success)},
    }

    latest_success_ts = parse_iso(latest_success.get("ts"))
    if latest_success_ts:
        age = datetime.now(timezone.utc) - latest_success_ts
        checks["latest_successful_trade_fresh"] = {
            "ok": age <= timedelta(minutes=max_trade_age_minutes),
            "age_seconds": round(age.total_seconds(), 2),
        }
        checks["latest_successful_trade_has_order_id"] = {
            "ok": bool(
                ((latest_success.get("response") or {}).get("success_response") or {}).get("order_id")
            ),
            "result": latest_success.get("result"),
            "symbol": latest_success.get("symbol"),
            "side": latest_success.get("side"),
            "order_id": (
                (latest_success.get("response") or {})
                .get("success_response", {})
                .get("order_id")
            ),
        }
    else:
        checks["latest_successful_trade_fresh"] = {"ok": False, "reason": "no successful trade timestamp"}
        checks["latest_successful_trade_has_order_id"] = {"ok": False, "reason": "no successful trade"}

    checks["breaker_reset_state"] = {
        "ok": not (
            state.get("cooldown_until")
            and parse_iso(state.get("cooldown_until"))
            and parse_iso(state.get("cooldown_until")) <= datetime.now(timezone.utc)
            and state.get("consecutive_losses", 0) > 0
        ),
        "cooldown_until": state.get("cooldown_until"),
        "consecutive_losses": state.get("consecutive_losses", 0),
        "transient_errors": state.get("transient_errors", 0),
        "last_error_classification": state.get("last_error_classification"),
    }

    overall_ok = all(item["ok"] for item in checks.values())
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ok": overall_ok,
        "checks": checks,
        "latest_trade": latest_trade,
        "latest_successful_trade": latest_success,
        "gate4_state": state,
        "coinbase_dns": coinbase_dns_status(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SIMP live revenue path status")
    parser.add_argument("--max-trade-age-minutes", type=int, default=30)
    args = parser.parse_args()

    report = build_report(max_trade_age_minutes=args.max_trade_age_minutes)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
