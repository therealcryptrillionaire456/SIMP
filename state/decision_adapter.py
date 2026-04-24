#!/usr/bin/env python3.10
"""
decision_adapter.py — post-hoc decision_id tagging shim for Day 1.

Maps existing signal_id-based trade records to canonical decision artifacts
so the verifier's lineage/policy/execution stages have something to grade.

Purpose: bridge until A3 ships native decision_id minting (target: Day 2).
This file is owned by A2 (writes fills with decision_id).
A3 owns the decision_id namespace; this uses "legacy:<signal_id>" as the tag.

Usage:
    # Watch the trade log and mirror to decision journal
    python3 state/decision_adapter.py

    # One-shot backfill of existing trades
    python3 state/decision_adapter.py --backfill
"""

import json
import os
import sys
import time
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from threading import Thread, Event

# Paths relative to repo root
REPO = Path(__file__).resolve().parent.parent
TRADE_LOG = REPO / "logs" / "gate4_trades.jsonl"
DECISION_JOURNAL = REPO / "state" / "decision_journal.ndjson"
PNL_LEDGER = REPO / "data" / "phase4_pnl_ledger.jsonl"
WATCHED_LOGS = [TRADE_LOG, PNL_LEDGER]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("decision_adapter")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _decision_id(signal_id: str) -> str:
    """Mint a deterministic legacy decision_id from a signal_id."""
    return f"legacy:{signal_id}"


def _load_jsonl(path: Path) -> list[Dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    log.warning("Skipping malformed line in %s", path)
    return entries


def _decision_journal_ids() -> set:
    """Return set of decision_ids already in the journal."""
    return {e.get("decision_id") for e in _load_jsonl(DECISION_JOURNAL) if e.get("decision_id")}


def _append_journal(entry: Dict[str, Any]) -> None:
    DECISION_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISION_JOURNAL, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def translate_trade_to_decision(trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a gate4 trade_record to a canonical decision artifact entry."""
    signal_id = trade.get("signal_id") or trade.get("id", "")
    if not signal_id:
        return None

    did = _decision_id(signal_id)

    # Determine terminal status
    result = trade.get("result", "unknown")
    if result == "dry_run_ok" or result == "ok":
        status = "executed"
    elif result and "policy_blocked" in result:
        status = "policy_blocked"
    elif result == "exchange_error":
        status = "exchange_error"
    elif result.startswith("exception:"):
        status = "exchange_error"
    else:
        status = result

    entry = {
        "decision_id": did,
        "legacy_signal_id": signal_id,
        "created_at": trade.get("ts", _utcnow()),
        "type": "trade_fill",
        "source": "gate4_inbox_consumer",
        "symbol": trade.get("symbol"),
        "side": trade.get("side"),
        "requested_usd": trade.get("requested_usd"),
        "executed_usd": trade.get("executed_usd"),
        "is_paper": trade.get("dry_run", True),
        "policy_result": {
            "status": "allow" if status == "executed" else ("block" if status in ("policy_blocked",) else "shadow"),
            "details": trade.get("result", ""),
            "budget_remaining": trade.get("available_quote_usd"),
        },
        "fill_status": status,
        "executed_at": trade.get("ts", _utcnow()),
        "execution": {
            "attempted": True,
            "terminal": result not in ("unknown",),
            "final_status": status,
            "result": result,
        },
        "lineage": {
            "signal_received": True,
            "policy_evaluated": True,
            "decision_made": True,
            "execution_attempted": status == "executed",
            "fill_reported": status == "executed",
        },
        "feedback": {
            "fill_age_s": None,
            "slippage_bps": None,
            "pnl_usd": None,
        },
        "legacy": True,
    }
    return entry


def translate_pnl_to_decision(pnl: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a PNL ledger entry to a decision artifact (feedback stage)."""
    signal_id = pnl.get("signal_id") or pnl.get("id", "")
    if not signal_id:
        return None

    did = _decision_id(signal_id)

    entry = {
        "decision_id": did,
        "legacy_signal_id": signal_id,
        "created_at": pnl.get("ts", _utcnow()),
        "type": "pnl_feedback",
        "source": "pnl_ledger",
        "symbol": pnl.get("symbol"),
        "pnl_usd": pnl.get("net_pnl"),
        "feedback": {
            "fill_age_s": None,
            "slippage_bps": pnl.get("slippage_bps"),
            "pnl_usd": pnl.get("net_pnl"),
        },
        "legacy": True,
    }
    return entry


def backfill_all() -> int:
    """One-shot backfill: read all trade logs and PNL ledger, write missing decision entries."""
    existing = _decision_journal_ids()
    count = 0

    for log_path in WATCHED_LOGS:
        if not log_path.exists():
            log.info("No file at %s, skipping", log_path)
            continue
        entries = _load_jsonl(log_path)
        for entry in entries:
            if log_path == TRADE_LOG:
                dec = translate_trade_to_decision(entry)
            elif log_path == PNL_LEDGER:
                dec = translate_pnl_to_decision(entry)
            else:
                continue
            if dec and dec["decision_id"] not in existing:
                _append_journal(dec)
                existing.add(dec["decision_id"])
                count += 1

    return count


def watch_loop(interval: float = 5.0, stop_event: Optional[Event] = None) -> None:
    """Tail the trade log and translate new entries to decision journal."""
    log.info("Watching logs at %s for new trade records", TRADE_LOG)
    last_sizes = {p: (p.stat().st_size if p.exists() else 0) for p in WATCHED_LOGS}

    while stop_event is None or not stop_event.is_set():
        for log_path in WATCHED_LOGS:
            if not log_path.exists():
                continue
            current_size = log_path.stat().st_size
            if current_size > last_sizes.get(log_path, 0):
                # Read new lines
                with open(log_path) as f:
                    f.seek(last_sizes.get(log_path, 0))
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        dec = translate_trade_to_decision(entry) if log_path == TRADE_LOG else translate_pnl_to_decision(entry)
                        if dec and dec["decision_id"] not in _decision_journal_ids():
                            _append_journal(dec)
                            log.info("Mapped %s → decision_journal", dec["decision_id"])
                last_sizes[log_path] = current_size

        if stop_event:
            stop_event.wait(timeout=interval)
        else:
            time.sleep(interval)


# --- Main ------------------------------------------------------------------
if __name__ == "__main__":
    if "--backfill" in sys.argv:
        count = backfill_all()
        log.info("Backfill complete: %d new decision entries", count)
    else:
        log.info("Starting watch loop (Ctrl+C to stop)")
        backfill_all()
        try:
            watch_loop(interval=5.0)
        except KeyboardInterrupt:
            log.info("Shutting down")
