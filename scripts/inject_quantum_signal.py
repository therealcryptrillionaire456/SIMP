#!/usr/bin/env python3.10
"""
Create a controlled Gate4-compatible quantum signal in the live inbox.

This is the operator-side manual lever for proving the revenue path:
QIP/bridge semantics -> Gate4 inbox consumer -> Coinbase order attempt.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

REPO = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = REPO / "data" / "inboxes" / "gate4_real"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_signal(
    *,
    asset: str,
    side: str,
    position_usd: float,
    source: str = "operator_manual_injection",
    metadata: Dict[str, Any] | None = None,
    signal_id: str | None = None,
) -> Dict[str, Any]:
    normalized_side = side.lower()
    if normalized_side not in {"buy", "sell", "hold"}:
        raise ValueError(f"unsupported side: {side}")

    signal = {
        "signal_id": signal_id or str(uuid.uuid4()),
        "source": source,
        "generated_at": utc_now_iso(),
        "signal_type": "portfolio_allocation",
        "assets": {
            asset: {
                "weight": 1.0,
                "position_usd": round(float(position_usd), 2),
                "action": normalized_side,
            }
        },
        "metadata": {
            "injected_by": "scripts/inject_quantum_signal.py",
            "injection_mode": "manual_operator",
        },
    }
    if metadata:
        signal["metadata"].update(metadata)
    return signal


def write_signal(signal: Dict[str, Any], inbox: Path) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    signal_key = str(signal.get("signal_id") or uuid.uuid4()).replace("-", "")[:12]
    target = inbox / f"quantum_signal_{int(datetime.now(timezone.utc).timestamp())}_{signal_key}.json"
    target.write_text(json.dumps(signal, indent=2), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject a controlled Gate4 quantum signal")
    parser.add_argument("--asset", default="BTC-USD", help="Trading pair, e.g. BTC-USD")
    parser.add_argument("--side", default="sell", choices=["buy", "sell", "hold"])
    parser.add_argument("--usd", type=float, default=1.0, help="Target USD notional")
    parser.add_argument("--source", default="operator_manual_injection")
    parser.add_argument("--signal-id", default=None)
    parser.add_argument("--metadata", action="append", default=[], help="Extra metadata as key=value")
    parser.add_argument("--inbox", default=str(DEFAULT_INBOX))
    parser.add_argument("--print-only", action="store_true", help="Print signal without writing file")
    args = parser.parse_args()

    extra_metadata: Dict[str, Any] = {}
    for item in args.metadata:
        if "=" not in item:
            raise SystemExit(f"invalid metadata item: {item} (expected key=value)")
        key, value = item.split("=", 1)
        extra_metadata[key] = value

    signal = build_signal(
        asset=args.asset,
        side=args.side,
        position_usd=args.usd,
        source=args.source,
        metadata=extra_metadata,
        signal_id=args.signal_id,
    )

    if args.print_only:
        print(json.dumps(signal, indent=2))
        return 0

    path = write_signal(signal, Path(args.inbox))
    print(json.dumps({"status": "ok", "path": str(path), "signal_id": signal["signal_id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
