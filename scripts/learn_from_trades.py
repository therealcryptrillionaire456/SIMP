#!/usr/bin/env python3
"""
Analyze Gate4 trade artifacts and promote them into structured memory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from simp.memory import SystemMemoryStore, TradeLearningEngine


def build_report(
    trade_log: str = "logs/gate4_trades.jsonl",
    pnl_ledger: str = "data/phase4_pnl_ledger.jsonl",
    db_path: str = "memory/system_memory.sqlite3",
    persist: bool = True,
) -> Dict[str, Any]:
    engine = TradeLearningEngine(trade_log_path=trade_log, pnl_ledger_path=pnl_ledger)
    store = SystemMemoryStore(db_path=db_path)

    report = engine.persist(store) if persist else engine.analyze()
    payload = report.to_dict()
    payload["memory_db"] = str(Path(db_path))
    if persist:
        payload["stored_counts"] = {
            "episodes": len(store.list_episodes(limit=5000)),
            "lessons": len(store.list_lessons(limit=5000)),
            "policy_candidates": len(store.list_policy_candidates(limit=5000)),
        }
    return payload


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Trade Learning Report",
        "",
        f"- Total trade records: {report['total_trade_records']}",
        f"- Live trade records: {report['live_trade_records']}",
        f"- Successful live trades: {report['successful_live_trades']}",
        f"- Insufficient balance events: {report['insufficient_balance_events']}",
        f"- Dry-run records: {report['dry_run_records']}",
        f"- Symbols with success: {', '.join(report['symbols_with_success']) or '(none)'}",
        f"- Memory DB: {report['memory_db']}",
    ]

    if "stored_counts" in report:
        lines.extend(
            [
                "",
                "## Stored Counts",
                f"- Episodes: {report['stored_counts']['episodes']}",
                f"- Lessons: {report['stored_counts']['lessons']}",
                f"- Policy candidates: {report['stored_counts']['policy_candidates']}",
            ]
        )

    lines.extend(["", "## Lessons"])
    for lesson in report["lessons"]:
        lines.append(f"- {lesson['title']} ({lesson['lesson_type']}, confidence={lesson['confidence']})")
        lines.append(f"  {lesson['summary']}")

    lines.extend(["", "## Policy Candidates"])
    for candidate in report["policy_candidates"]:
        lines.append(f"- {candidate['title']} [{candidate['priority']}]")
        lines.append(f"  {candidate['rationale']}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote trade artifacts into memory and lessons.")
    parser.add_argument("--trade-log", default="logs/gate4_trades.jsonl")
    parser.add_argument("--pnl-ledger", default="data/phase4_pnl_ledger.jsonl")
    parser.add_argument("--db-path", default="memory/system_memory.sqlite3")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--analyze-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        trade_log=args.trade_log,
        pnl_ledger=args.pnl_ledger,
        db_path=args.db_path,
        persist=not args.analyze_only,
    )

    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
