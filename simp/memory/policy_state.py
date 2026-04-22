"""
Active system policy state derived from reflection artifacts.

This module is intentionally simple: reflection jobs write a compact JSON
artifact, and runtime consumers read it without mutating the source report.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


POLICY_STATE_PATH = Path("memory/active_system_policies.json")
REFLECTION_STATUS_PATH = Path("memory/reflection_status.json")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_active_policy_state(
    report: Dict[str, Any],
    *,
    min_lesson_confidence: float = 0.8,
    default_quality_score: float = 0.5,
) -> Dict[str, Any]:
    lessons: List[Dict[str, Any]] = list(report.get("lessons") or [])
    policy_candidates: List[Dict[str, Any]] = list(report.get("policy_candidates") or [])

    active_lessons = [
        lesson
        for lesson in lessons
        if float(lesson.get("confidence", 0.0) or 0.0) >= min_lesson_confidence
    ]

    mesh_summary = report.get("mesh_summary") or {}
    registry_summary = report.get("registry_summary") or {}
    trade_learning = report.get("trade_learning") or {}

    return {
        "generated_at": _utcnow(),
        "source": "system_learning",
        "version": report.get("memory_db") or "memory/system_memory.sqlite3",
        "thresholds": {
            "min_lesson_confidence": min_lesson_confidence,
        },
        "capital_budgeting": {
            "enabled": True,
            "mode": "sequential_top_down",
            "min_quote_reserve_usd": 0.0,
            "required_for_multi_buy": True,
            "observed_insufficient_balance_events": trade_learning.get("insufficient_balance_events", 0),
        },
        "execution_quality": {
            "enabled": True,
            "min_quality_score": default_quality_score,
            "successful_live_trades": trade_learning.get("successful_live_trades", 0),
        },
        "mesh_hygiene": {
            "enabled": True,
            "drop_rate": mesh_summary.get("drop_rate", 0.0),
            "error_counts": mesh_summary.get("error_counts", {}),
        },
        "agent_churn": {
            "enabled": True,
            "churn_ratio": registry_summary.get("churn_ratio", 0.0),
        },
        "plan_lineage": {
            "enabled": True,
            "required": True,
        },
        "active_lessons": active_lessons,
        "active_policy_candidates": policy_candidates,
    }


def write_policy_state(policy_state: Dict[str, Any], path: Path | None = None) -> None:
    path = path or POLICY_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy_state, indent=2, sort_keys=True))


def write_reflection_status(
    report: Dict[str, Any],
    policy_state: Dict[str, Any],
    path: Path | None = None,
) -> None:
    path = path or REFLECTION_STATUS_PATH
    payload = {
        "generated_at": _utcnow(),
        "source": "system_learning",
        "report_summary": {
            "successful_live_trades": (report.get("trade_learning") or {}).get("successful_live_trades", 0),
            "mesh_drop_rate": (report.get("mesh_summary") or {}).get("drop_rate", 0.0),
            "registry_churn_ratio": (report.get("registry_summary") or {}).get("churn_ratio", 0.0),
            "lessons": len(report.get("lessons") or []),
            "policy_candidates": len(report.get("policy_candidates") or []),
        },
        "policy_summary": {
            "active_lessons": len(policy_state.get("active_lessons") or []),
            "active_policy_candidates": len(policy_state.get("active_policy_candidates") or []),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def load_active_system_policies(path: Path | None = None) -> Dict[str, Any]:
    path = path or POLICY_STATE_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
