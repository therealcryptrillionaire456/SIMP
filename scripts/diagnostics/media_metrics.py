#!/usr/bin/env python3.10
"""
Media Grid Metrics Diagnostics

Reads agent heartbeat and workflow ledgers from data/media/ and prints a
formatted summary table of observability metrics.

Usage:
    python3.10 scripts/diagnostics/media_metrics.py [--data-dir DATA_DIR]

Dependencies: none (stdlib only)
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# ── helpers ──────────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read all records from a JSONL file, returning an empty list if missing."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # silently skip corrupt lines
    return records


def _fmt_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-friendly string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:.0f}m {secs:.0f}s"


def _fmt_pct(numerator: int, denominator: int) -> str:
    """Format a percentage with 1 decimal place, or '—' when denominator is 0."""
    if denominator == 0:
        return "—"
    return f"{100.0 * numerator / denominator:.1f}%"


# ── data loaders ─────────────────────────────────────────────────────────

def load_heartbeats(data_dir: Path) -> List[Dict[str, Any]]:
    """Load agent heartbeat records."""
    return _read_jsonl(data_dir / "agent_heartbeats.jsonl")


def load_workflows(data_dir: Path) -> List[Dict[str, Any]]:
    """Load workflow completion records (if the file exists)."""
    return _read_jsonl(data_dir / "workflows.jsonl")


def load_metrics(data_dir: Path) -> List[Dict[str, Any]]:
    """Load numeric metric records."""
    return _read_jsonl(data_dir / "metrics.jsonl")


# ── computations ─────────────────────────────────────────────────────────

def compute_summary(
    heartbeats: List[Dict[str, Any]],
    workflows: List[Dict[str, Any]],
    metrics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Derive summary statistics from the loaded data."""
    summary: Dict[str, Any] = {}

    # --- heartbeat stats ---
    summary["total_heartbeat_records"] = len(heartbeats)

    if heartbeats:
        agents_seen = list({r.get("agent_id") for r in heartbeats if r.get("agent_id")})
        summary["unique_agents"] = sorted(agents_seen)

        # latest heartbeat per agent
        latest: Dict[str, str] = {}
        for r in heartbeats:
            aid = r.get("agent_id", "")
            ts = r.get("timestamp", "")
            if aid and ts and (aid not in latest or ts > latest[aid]):
                latest[aid] = ts
        summary["latest_heartbeat_per_agent"] = latest

        # agent that has NOT sent a heartbeat in the last 5 minutes
        stale: Dict[str, str] = {}
        now = datetime.utcnow()
        for aid, ts in latest.items():
            try:
                delta = now - datetime.fromisoformat(ts)
                if delta.total_seconds() > 300:  # 5 minutes
                    stale[aid] = ts
            except (ValueError, TypeError):
                stale[aid] = ts
        summary["stale_agents"] = stale
    else:
        summary["unique_agents"] = []
        summary["latest_heartbeat_per_agent"] = {}
        summary["stale_agents"] = {}

    # --- workflow stats ---
    summary["total_workflows"] = len(workflows)

    if workflows:
        status_counter: Counter = Counter(r.get("status", "unknown") for r in workflows)
        summary["workflow_status_counts"] = dict(status_counter)

        type_counter: Counter = Counter(
            r.get("type", r.get("workflow_type", "unknown")) for r in workflows
        )
        summary["workflow_type_counts"] = dict(type_counter)

        durations = [
            r["duration_seconds"]
            for r in workflows
            if isinstance(r.get("duration_seconds"), (int, float))
        ]
        if durations:
            summary["workflow_duration_avg"] = sum(durations) / len(durations)
            summary["workflow_duration_max"] = max(durations)
            summary["workflow_duration_min"] = min(durations)
        else:
            summary["workflow_duration_avg"] = 0.0
            summary["workflow_duration_max"] = 0.0
            summary["workflow_duration_min"] = 0.0

        # published content from workflows (if workflow result has a content_id)
        published = [r for r in workflows if r.get("published_content_id")]
        summary["published_content"] = len(published)
    else:
        summary["workflow_status_counts"] = {}
        summary["workflow_type_counts"] = {}
        summary["workflow_duration_avg"] = 0.0
        summary["workflow_duration_max"] = 0.0
        summary["workflow_duration_min"] = 0.0
        summary["published_content"] = 0

    # --- error rate ---
    total = summary["total_workflows"]
    failures = summary["workflow_status_counts"].get("failed", 0)
    summary["error_count"] = failures
    summary["error_rate"] = failures / total if total > 0 else 0.0

    # --- metric stats ---
    summary["total_metric_records"] = len(metrics)
    if metrics:
        revenue_metrics = [
            r for r in metrics if "revenue" in r.get("metric", "").lower()
        ]
        if revenue_metrics:
            summary["media_revenue_cents"] = sum(
                r["value"] for r in revenue_metrics
                if isinstance(r.get("value"), (int, float))
            )
        else:
            summary["media_revenue_cents"] = 0
    else:
        summary["media_revenue_cents"] = 0

    return summary


# ── display ──────────────────────────────────────────────────────────────

def print_summary(summary: Dict[str, Any]) -> None:
    """Print a formatted summary table to stdout."""
    sep = "─" * 62
    print()
    print("  KashClaw Media Grid — Metrics Summary")
    print(f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(sep)

    # ── heartbeat section ──
    print(f"\n  {'Agent Heartbeats':30s}  {'':>10s}")
    print(f"  {'─' * 40}")
    print(f"  {'Total heartbeat records':30s}  {summary['total_heartbeat_records']:>10d}")
    print(f"  {'Unique agents seen':30s}  {len(summary['unique_agents']):>10d}")

    if summary["unique_agents"]:
        print(f"  {'Agents':30s}  {', '.join(summary['unique_agents']):>10s}")

    stale = summary.get("stale_agents", {})
    if stale:
        print(f"  {'⚠️  Stale agents (>5min)':30s}  {', '.join(stale.keys()):>10s}")
    else:
        print(f"  {'All agents healthy':30s}  {'✓':>10s}")

    # ── workflow section ──
    print(f"\n  {'Workflows':30s}  {'':>10s}")
    print(f"  {'─' * 40}")
    print(f"  {'Total workflows':30s}  {summary['total_workflows']:>10d}")

    if summary["workflow_status_counts"]:
        for status, count in sorted(summary["workflow_status_counts"].items()):
            print(f"  {'  Status: ' + status:30s}  {count:>10d}")

    if summary["workflow_type_counts"]:
        for wtype, count in sorted(summary["workflow_type_counts"].items()):
            print(f"  {'  Type: ' + wtype:30s}  {count:>10d}")

    avg_dur = summary["workflow_duration_avg"]
    if avg_dur:
        print(f"  {'Avg duration':30s}  {_fmt_duration(avg_dur):>10s}")
        print(f"  {'Min duration':30s}  {_fmt_duration(summary['workflow_duration_min']):>10s}")
        print(f"  {'Max duration':30s}  {_fmt_duration(summary['workflow_duration_max']):>10s}")

    # ── quality section ──
    print(f"\n  {'Quality':30s}  {'':>10s}")
    print(f"  {'─' * 40}")
    print(f"  {'Published content':30s}  {summary['published_content']:>10d}")
    err_rate = _fmt_pct(summary["error_count"], summary["total_workflows"])
    print(f"  {'Error count':30s}  {summary['error_count']:>10d}")
    print(f"  {'Error rate':30s}  {err_rate:>10s}")

    # ── revenue section ──
    rev_cents = summary["media_revenue_cents"]
    rev_dollars = rev_cents / 100.0
    print(f"\n  {'Revenue':30s}  {'':>10s}")
    print(f"  {'─' * 40}")
    print(f"  {'Media revenue (cents)':30s}  {rev_cents:>10.0f}")
    print(f"  {'Media revenue (USD)':30s}  ${rev_dollars:>8.2f}")

    # ── metrics ledger section ──
    print(f"\n  {'Metrics Ledger':30s}  {'':>10s}")
    print(f"  {'─' * 40}")
    print(f"  {'Metric records':30s}  {summary['total_metric_records']:>10d}")

    print()
    print(sep)
    print()


# ── main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Media Grid Metrics Diagnostics — read ledgers & print summary"
    )
    parser.add_argument(
        "--data-dir",
        default="data/media",
        help="Path to media data directory (default: data/media)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    heartbeats = load_heartbeats(data_dir)
    workflows = load_workflows(data_dir)
    metrics = load_metrics(data_dir)

    summary = compute_summary(heartbeats, workflows, metrics)
    print_summary(summary)


if __name__ == "__main__":
    main()
