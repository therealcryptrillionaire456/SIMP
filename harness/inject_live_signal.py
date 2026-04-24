#!/usr/bin/env python3
"""
inject_live_signal.py — A2's authorized end-to-end probe.

Creates a minimal canonical decision artifact and writes it into
state/decision_journal.ndjson so the hot path can be exercised without
a real upstream signal source. Safe defaults:

  - venue defaults to "paper"
  - confidence defaults to 0.1 (below typical edge floor)
  - mode is inherited from state/mode.json

This is a probe, not an order generator. If you set --venue to a live
venue AND --confidence above your scoring floor, you will send a real
order. The script refuses --size-usd > 10 without --i-know-what-im-doing.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent if HERE.name in {"scripts", "harness"} else HERE
STATE_DIR = Path(os.environ.get("SIMP_STATE_DIR", REPO_ROOT / "state"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
DECISION_JOURNAL = STATE_DIR / "decision_journal.ndjson"
MODE_PATH = Path(os.environ.get("SIMP_MODE_PATH", STATE_DIR / "mode.json"))


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="paper",
                    choices=["paper", "coinbase", "kalshi", "alpaca", "solana"])
    ap.add_argument("--instrument", default="PAPER-TEST")
    ap.add_argument("--side", default="buy", choices=["buy", "sell", "long", "short"])
    ap.add_argument("--size-usd", type=float, default=5.0)
    ap.add_argument("--confidence", type=float, default=0.1)
    ap.add_argument("--expected-edge-bps", type=float, default=0.0)
    ap.add_argument("--thesis", default="synthetic probe signal")
    ap.add_argument("--i-know-what-im-doing", action="store_true")
    args = ap.parse_args()

    if args.size_usd > 10 and not args.i_know_what_im_doing:
        print("refusing size_usd > 10 without --i-know-what-im-doing", file=sys.stderr)
        return 2

    if args.venue != "paper" and args.confidence >= 0.5:
        print(f"[inject] WARNING: venue={args.venue} confidence={args.confidence} may route to live")
        if not args.i_know_what_im_doing:
            print("refusing live + high confidence without --i-know-what-im-doing", file=sys.stderr)
            return 2

    did = "dec_" + secrets.token_hex(8)
    decision = {
        "decision_id": did,
        "created_at": _utcnow(),
        "source_signal_ids": [f"probe_{secrets.token_hex(4)}"],
        "thesis": args.thesis,
        "confidence": float(args.confidence),
        "risk_budget_usd": float(args.size_usd),
        "venue": args.venue,
        "instrument": args.instrument,
        "side": args.side,
        "size": float(args.size_usd),
        "expected_edge_bps": float(args.expected_edge_bps),
        "policy_result": {
            "status": "allow" if args.venue == "paper" else "shadow",
            "reasons": ["probe"],
            "evaluated_at": _utcnow(),
        },
        "mode": _mode(),
        "lineage": {
            "scorer": "inject_live_signal",
            "planner": "inject_live_signal",
            "broker_intent_id": "",
        },
    }
    with DECISION_JOURNAL.open("a") as f:
        f.write(json.dumps(decision) + "\n")
    print(json.dumps({"decision_id": did, "written_to": str(DECISION_JOURNAL)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
