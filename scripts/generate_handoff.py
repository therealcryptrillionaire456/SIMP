#!/usr/bin/env python3
"""
A8 — Auto Handoff Notes Generator

Reads current system state and generates a markdown handoff document.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
HANDOFF_DIR = REPO / "state" / "handoff"
HANDOFF_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _read_ndjson_tail(path: Path, n: int = 10) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-n:]


def build_report() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    lines: list[str] = []
    lines.append(f"# Auto-Generated Handoff — {ts}")
    lines.append("")

    # Mode
    mode = _read_json(REPO / "state" / "mode.json")
    if mode:
        lines.append("## Mode")
        lines.append(f"- **Status**: {mode.get('mode', 'unknown')}")
        lines.append(f"- **Live Trading**: {mode.get('restrictions', {}).get('live_trading', 'unknown')}")
        lines.append(f"- **Set at**: {mode.get('set_at', '?')}")
        lines.append("")

    # Status Board
    board = _read_json(REPO / "state" / "status_board.json")
    if board:
        lines.append("## Status Board")
        lanes = board.get("lanes", {})
        lines.append(f"- **{len(lanes)} lanes** reporting")
        for lane_id, info in sorted(lanes.items()):
            status = info.get("last_status", "?")
            last = info.get("last_cycle_at", "never")
            lines.append(f"  - **{lane_id}**: {status} (last: {last})")
        lines.append("")

    # Verifier
    verify = _read_json(REPO / "state" / "metrics" / "verify.last.json")
    if verify:
        lines.append("## Last Verifier Result")
        lines.append(f"- **Result**: {'GREEN' if verify.get('green') else 'RED'}")
        stages = verify.get("stages", [])
        if isinstance(stages, list):
            for stage in stages:
                if isinstance(stage, dict):
                    name = stage.get("name", "?")
                    ok = stage.get("ok", stage.get("terminal_ok", "?"))
                    detail = stage.get("detail", "")
                    lines.append(f"  - {name}: {'OK' if ok else 'FAIL'} — {detail}")
        lines.append("")

    # Queue
    queue = _read_json(REPO / "state" / "queue.json")
    if queue:
        lines.append("## Pending Queue")
        cards = queue if isinstance(queue, list) else queue.get("cards", [])
        for card in cards[:10]:
            cid = card.get("card_id", card.get("id", "?"))
            title = card.get("title", card.get("objective", "?"))
            lines.append(f"  - {cid}: {title}")
        if len(cards) > 10:
            lines.append(f"  - ... and {len(cards) - 10} more")
        lines.append("")

    # Recent decisions
    journal = _read_ndjson_tail(REPO / "state" / "decision_journal.ndjson", 10)
    if journal:
        lines.append("## Recent Decisions (last 10)")
        for e in reversed(journal):
            did = e.get("decision_id", "?")[:35]
            fs = e.get("fill_status", "?")
            created = e.get("created_at", "?")[:19]
            lines.append(f"  - {created} | {did:35s} | {fs}")
        lines.append("")

    # Gate4
    gate4_log = REPO / "logs" / "gate4_trades.jsonl"
    if gate4_log.exists():
        with open(gate4_log) as f:
            gate_lines = [l.strip() for l in f if l.strip()]
        lines.append(f"## Gate4 Trade Log")
        lines.append(f"- **Total trades**: {len(gate_lines)}")
        if gate_lines:
            last_trade = json.loads(gate_lines[-1])
            lines.append(f"- **Last trade**: {last_trade.get('symbol', '?')} {last_trade.get('result', '?')[:50]}")
        lines.append("")

    # Kill switch
    kill = REPO / "state" / "KILL"
    lines.append("## Kill Switch")
    lines.append(f"- **File exists**: {kill.exists()}")
    lines.append("")

    # Checksum
    lines.append("---")
    lines.append(f"_Generated automatically at {datetime.now(timezone.utc).isoformat()}_")
    return "\n".join(lines)


def main():
    report = build_report()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = HANDOFF_DIR / f"auto_handoff_{ts}.md"
    out_path.write_text(report)
    print(f"Handoff written to {out_path}")
    print(report[:500] + "..." if len(report) > 500 else report)


if __name__ == "__main__":
    main()
