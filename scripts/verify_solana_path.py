#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRADE_LOG = ROOT / "logs" / "solana_seeker_trades.jsonl"
STATE_FILE = ROOT / "data" / "solana_seeker_state.json"


def _latest_jsonl(path: Path) -> dict:
    if not path.exists():
        return {}
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        return {}
    return json.loads(lines[-1])


def main() -> int:
    latest_trade = _latest_jsonl(TRADE_LOG)
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    report = {
        "ok": bool(latest_trade or state),
        "trade_log_present": TRADE_LOG.exists(),
        "state_present": STATE_FILE.exists(),
        "latest_trade": latest_trade,
        "policy_state_version_present": bool(latest_trade.get("policy_state_version")),
        "lineage_present": bool(latest_trade.get("lineage")),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
