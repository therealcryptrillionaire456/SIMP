#!/usr/bin/env python3.10
"""
Opinionated hot-path verification for revenue readiness.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from runtime_snapshot import build_snapshot

REPO = Path(__file__).resolve().parents[1]
TRADE_LOG = REPO / "logs" / "gate4_trades.jsonl"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def build_report(max_trade_age_minutes: int = 30) -> dict[str, Any]:
    snapshot = build_snapshot()
    latest_trade = snapshot["gate4"]["latest_trade"] or {}

    checks: dict[str, dict[str, Any]] = {
        "broker_up": {"ok": snapshot["services"]["broker"]["ok"]},
        "dashboard_up": {"ok": snapshot["services"]["dashboard"]["ok"]},
        "projectx_up": {"ok": snapshot["services"]["projectx"]["ok"]},
        "gate4_consumer_running": {"ok": snapshot["processes"]["gate4_consumer"] > 0},
        "quantum_bridge_running": {"ok": snapshot["processes"]["quantum_signal_bridge"] > 0},
        "latest_trade_present": {"ok": bool(latest_trade)},
    }

    latest_trade_ts = parse_iso(latest_trade.get("ts"))
    if latest_trade_ts:
        age = datetime.now(timezone.utc) - latest_trade_ts
        checks["latest_trade_fresh"] = {
            "ok": age <= timedelta(minutes=max_trade_age_minutes),
            "age_seconds": round(age.total_seconds(), 2),
        }
        checks["latest_trade_successful"] = {
            "ok": latest_trade.get("result") == "ok",
            "result": latest_trade.get("result"),
            "symbol": latest_trade.get("symbol"),
            "side": latest_trade.get("side"),
            "order_id": (
                (latest_trade.get("response") or {})
                .get("success_response", {})
                .get("order_id")
            ),
        }
    else:
        checks["latest_trade_fresh"] = {"ok": False, "reason": "no trade timestamp"}
        checks["latest_trade_successful"] = {"ok": False, "reason": "no trade"}

    overall_ok = all(item["ok"] for item in checks.values())
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ok": overall_ok,
        "checks": checks,
        "latest_trade": latest_trade,
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
