#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "data" / "quantumarb_phase4" / "decisions.jsonl"
OUTBOX = ROOT / "data" / "quantumarb_phase4" / "outbox"


def _latest_jsonl(path: Path) -> dict:
    if not path.exists():
        return {}
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        return {}
    return json.loads(lines[-1])


def main() -> int:
    latest_decision = _latest_jsonl(DECISIONS)
    latest_outbox = {}
    if OUTBOX.exists():
        files = sorted(OUTBOX.glob("*.json"))
        if files:
            latest_outbox = json.loads(files[-1].read_text())

    report = {
        "ok": bool(latest_decision or latest_outbox),
        "decisions_log_present": DECISIONS.exists(),
        "latest_decision": latest_decision,
        "latest_outbox": latest_outbox,
        "lineage_present": bool(latest_decision.get("lineage") or latest_outbox.get("lineage")),
        "policy_state_version_present": bool(
            latest_decision.get("policy_state_version") or latest_outbox.get("policy_state_version")
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
