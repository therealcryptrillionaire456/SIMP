#!/usr/bin/env python3
"""
Analyze cross-system artifacts and promote them into structured memory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from simp.memory import (
    SystemLearningEngine,
    SystemMemoryStore,
    build_active_policy_state,
    write_policy_state,
    write_reflection_status,
)


def build_report(
    db_path: str = "memory/system_memory.sqlite3",
    persist: bool = True,
) -> Dict[str, Any]:
    engine = SystemLearningEngine()
    store = SystemMemoryStore(db_path=db_path)
    report = engine.persist(store) if persist else engine.analyze()
    payload = report.to_dict()
    payload["memory_db"] = str(Path(db_path))
    if persist:
        policy_state = build_active_policy_state(payload)
        write_policy_state(policy_state)
        write_reflection_status(payload, policy_state)
        payload["policy_state"] = policy_state
        payload["stored_counts"] = {
            "episodes": len(store.list_episodes(limit=5000)),
            "lessons": len(store.list_lessons(limit=5000)),
            "policy_candidates": len(store.list_policy_candidates(limit=5000)),
        }
    return payload


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# System Learning Report",
        "",
        "## Trade Learning",
        f"- Total trade records: {report['trade_learning']['total_trade_records']}",
        f"- Live trade records: {report['trade_learning']['live_trade_records']}",
        f"- Successful live trades: {report['trade_learning']['successful_live_trades']}",
        f"- Symbols with success: {', '.join(report['trade_learning']['symbols_with_success']) or '(none)'}",
        "",
        "## Mesh",
        f"- Total events: {report['mesh_summary']['total_events']}",
        f"- Drop rate: {report['mesh_summary']['drop_rate']}",
        "",
        "## Orchestration",
        f"- Plans started: {report['orchestration_summary']['plan_started']}",
        f"- Plans completed: {report['orchestration_summary']['plan_completed']}",
        f"- Completion ratio: {report['orchestration_summary']['completion_ratio']}",
        "",
        "## Security",
        f"- Total events: {report['security_summary']['total_events']}",
        "",
        "## Registry",
        f"- Total events: {report['registry_summary']['total_events']}",
        f"- Churn ratio: {report['registry_summary']['churn_ratio']}",
        "",
        f"- Memory DB: {report['memory_db']}",
    ]

    policy_state = report.get("policy_state") or {}
    if policy_state:
        lines.extend(
            [
                "",
                "## Active Policy State",
                f"- Generated at: {policy_state.get('generated_at', 'unknown')}",
                f"- Active lessons: {len(policy_state.get('active_lessons') or [])}",
                f"- Active policy candidates: {len(policy_state.get('active_policy_candidates') or [])}",
            ]
        )

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
    parser = argparse.ArgumentParser(description="Promote system artifacts into memory and lessons.")
    parser.add_argument("--db-path", default="memory/system_memory.sqlite3")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--analyze-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(db_path=args.db_path, persist=not args.analyze_only)
    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
