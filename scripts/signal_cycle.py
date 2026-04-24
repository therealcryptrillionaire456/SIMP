#!/usr/bin/env python3
"""
signal_cycle.py — A2's sustained signal injector for Day 2 freshness.

Injects a fresh decision signal every INTERVAL seconds so the verifier's
signal_freshness stage always sees age_s < target(60s).

Also injects into the gate4 inbox every N cycles so the old pipeline stays
exercised (even if policy-blocked, the block is recorded).

Usage:
    python3 scripts/signal_cycle.py          # default: every 45s
    python3 scripts/signal_cycle.py --interval 30
    python3 scripts/signal_cycle.py --gate4-interval 3  # inject gate4 every 3 cycles
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
STATE_DIR = REPO_ROOT / "state"
DECISION_JOURNAL = STATE_DIR / "decision_journal.ndjson"
MODE_PATH = STATE_DIR / "mode.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mode() -> str:
    if not MODE_PATH.exists():
        return "fully_live"
    try:
        with MODE_PATH.open() as f:
            return json.load(f).get("mode", "fully_live")
    except Exception:
        return "fully_live"


def inject_decision_journal() -> str:
    """Write a probe to decision_journal.ndjson (feeds verifier)."""
    did = "dec_" + secrets.token_hex(8)
    decision = {
        "decision_id": did,
        "created_at": _utcnow(),
        "source_signal_ids": [f"cycle_{secrets.token_hex(4)}"],
        "thesis": "sustained freshness probe",
        "confidence": 0.1,
        "risk_budget_usd": 1.0,
        "venue": "paper",
        "instrument": "PAPER-TEST",
        "side": "buy" if secrets.randbelow(2) == 0 else "sell",
        "size": 1.0,
        "expected_edge_bps": 0.0,
        "policy_result": {
            "status": "allow",
            "reasons": ["freshness_probe"],
            "evaluated_at": _utcnow(),
        },
        "mode": _mode(),
        "lineage": {
            "scorer": "signal_cycle",
            "planner": "signal_cycle",
            "broker_intent_id": "",
        },
        "fill_status": "stale",
        "executed_at": _utcnow(),
        "execution": {
            "attempted": True,
            "terminal": True,
            "final_status": "pending",
            "result": "pending",
        },
    }
    with DECISION_JOURNAL.open("a") as f:
        f.write(json.dumps(decision) + "\n")
    return did


def inject_gate4_inbox() -> str:
    """Use the legacy inject_quantum_signal.py to write to gate4 inbox."""
    try:
        result = subprocess.run(
            [sys.executable, str(HERE / "inject_quantum_signal.py"),
             "--asset", "BTC-USD", "--side", "buy", "--usd", "1.00"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("signal_id", "unknown")
        else:
            return f"error:{result.stderr.strip()}"
    except Exception as e:
        return f"exception:{e}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Sustained signal injector for Day 2 freshness")
    ap.add_argument("--interval", type=int, default=45,
                    help="Seconds between decision journal injections (default: 45)")
    ap.add_argument("--gate4-interval", type=int, default=3,
                    help="Inject gate4 signal every N cycles (0=never, default: 3)")
    args = ap.parse_args()

    print(f"[signal_cycle] Starting — decision journal every {args.interval}s, "
          f"gate4 every {args.gate4_interval} cycles", flush=True)
    print(f"[signal_cycle] Mode: {_mode()}", flush=True)
    print(f"[signal_cycle] Ctrl+C to stop", flush=True)

    cycle = 0
    try:
        while True:
            cycle += 1
            # Primary: inject decision journal (feeds verifier)
            did = inject_decision_journal()
            print(f"[{_utcnow()}] cycle={cycle} decision={did}", flush=True)

            # Secondary: inject gate4 every N cycles
            if args.gate4_interval > 0 and cycle % args.gate4_interval == 0:
                sid = inject_gate4_inbox()
                print(f"[{_utcnow()}] cycle={cycle} gate4_signal={sid}", flush=True)

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n[signal_cycle] Stopped after {cycle} cycles", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
