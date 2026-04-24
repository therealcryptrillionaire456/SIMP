"""ProjectX control-plane snapshot helpers.

Combines ProjectX phase health and contract coverage into a single bounded
packet for broker, dashboard, and watchtower views.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from simp.compat.projectx_contracts import (
    CONTRACT_TYPES,
    DEFAULT_CONTRACT_LOG,
    contract_summary,
    read_contracts,
)
from simp.compat.projectx_phase_status import (
    DEFAULT_PHASE_ALERT_ACK_LOG,
    DEFAULT_PHASE_STATUS_LOG,
    build_operator_packet,
)


def build_contract_scoreboard(
    *,
    log_path: Path = DEFAULT_CONTRACT_LOG,
    recent_limit: int = 25,
) -> Dict[str, Any]:
    summary = contract_summary(log_path=log_path)
    counts = dict(summary.get("counts") or {})
    contract_types = list(summary.get("contract_types") or sorted(CONTRACT_TYPES))
    emitted_type_count = sum(1 for contract_type in contract_types if counts.get(contract_type, 0) > 0)
    total_type_count = len(contract_types)
    coverage_ratio = (emitted_type_count / total_type_count) if total_type_count else 1.0
    recent_rows = read_contracts(log_path=log_path, limit=max(1, min(recent_limit, 100)))

    source_agents: Dict[str, Dict[str, Any]] = {}
    recent_mission_ids: list[str] = []
    recent_metric_names: list[str] = []
    seen_missions: set[str] = set()
    seen_metrics: set[str] = set()

    for row in recent_rows:
        source_agent = str(row.get("source_agent") or "projectx_native")
        bucket = source_agents.setdefault(source_agent, {"count": 0, "contract_types": []})
        bucket["count"] += 1
        contract_type = str(row.get("contract_type") or "unknown")
        if contract_type not in bucket["contract_types"]:
            bucket["contract_types"].append(contract_type)

        mission_id = row.get("mission_id")
        if mission_id:
            mission_key = str(mission_id)
            if mission_key not in seen_missions:
                recent_mission_ids.append(mission_key)
                seen_missions.add(mission_key)

        if contract_type == "scoreboard_metric":
            metric_name = str(row.get("metric_name") or "").strip()
            if metric_name and metric_name not in seen_metrics:
                recent_metric_names.append(metric_name)
                seen_metrics.add(metric_name)

    return {
        "status": str(summary.get("status") or "ok"),
        "generated_at": str(summary.get("generated_at") or ""),
        "counts": counts,
        "total_recent": int(summary.get("total_recent") or 0),
        "mission_count": int(summary.get("mission_count") or 0),
        "missing_contract_types": list(summary.get("missing_contract_types") or []),
        "latest_by_type": dict(summary.get("latest_by_type") or {}),
        "source_agents": source_agents,
        "recent_mission_ids": recent_mission_ids,
        "recent_metric_names": recent_metric_names,
        "recent_contracts": recent_rows[:10],
        "coverage": {
            "emitted_type_count": emitted_type_count,
            "total_type_count": total_type_count,
            "coverage_ratio": round(coverage_ratio, 4),
            "full_coverage": emitted_type_count == total_type_count,
        },
    }


def build_control_plane_snapshot(
    payload: Optional[Dict[str, Any]],
    *,
    phase_log_path: Path = DEFAULT_PHASE_STATUS_LOG,
    ack_path: Path = DEFAULT_PHASE_ALERT_ACK_LOG,
    contract_log_path: Path = DEFAULT_CONTRACT_LOG,
    history_limit: int = 12,
) -> Dict[str, Any]:
    operator_packet = build_operator_packet(
        payload,
        log_path=phase_log_path,
        ack_path=ack_path,
        history_limit=history_limit,
    )
    contract_packet = build_contract_scoreboard(log_path=contract_log_path)
    phase_summary = dict(operator_packet.get("summary") or {})
    coverage = dict(contract_packet.get("coverage") or {})

    phase_healthy = bool(phase_summary.get("healthy"))
    full_contract_coverage = bool(coverage.get("full_coverage"))
    phase_count = int(phase_summary.get("phase_count") or 0)
    total_recent_contracts = int(contract_packet.get("total_recent") or 0)
    control_plane_healthy = phase_healthy and full_contract_coverage

    if phase_count == 0 and total_recent_contracts == 0:
        status = "unreachable"
    elif control_plane_healthy:
        status = "ok"
    else:
        status = "warning"

    operator_actions: list[Dict[str, Any]] = []
    if int(phase_summary.get("non_ok_count") or 0) > 0:
        operator_actions.append(
            {
                "id": "review_non_ok_phases",
                "title": "Review non-ok ProjectX phases",
                "reason": f"{phase_summary.get('non_ok_count', 0)} phase(s) are non-ok.",
            }
        )
    missing_types = list(contract_packet.get("missing_contract_types") or [])
    if missing_types:
        operator_actions.append(
            {
                "id": "backfill_contract_producers",
                "title": "Backfill missing ProjectX contract producers",
                "reason": f"Missing contract types: {', '.join(missing_types)}.",
            }
        )
    if total_recent_contracts == 0:
        operator_actions.append(
            {
                "id": "exercise_projectx_contracts",
                "title": "Exercise ProjectX control-plane producers",
                "reason": "No recent ProjectX contracts observed by SIMP.",
            }
        )
    if not operator_actions:
        operator_actions.append(
            {
                "id": "continue_shadow_monitoring",
                "title": "Continue shadow monitoring",
                "reason": "Phase health and contract coverage are currently stable.",
            }
        )

    return {
        "status": status,
        "generated_at": str(operator_packet.get("generated_at") or contract_packet.get("generated_at") or ""),
        "source": str(operator_packet.get("source") or "cache"),
        "phase_range": str(phase_summary.get("phase_range") or "8-20"),
        "control_plane_healthy": control_plane_healthy,
        "phase_summary": phase_summary,
        "contract_summary": contract_packet,
        "alerts": list(operator_packet.get("alerts") or []),
        "alert_count": int(operator_packet.get("alert_count") or 0),
        "acknowledged_alert_count": int(operator_packet.get("acknowledged_alert_count") or 0),
        "history": dict(operator_packet.get("history") or {}),
        "constitution": dict(operator_packet.get("constitution") or {}),
        "eval_governance": dict(operator_packet.get("eval_governance") or {}),
        "operator_actions": operator_actions,
        "watchtower": {
            "status": status,
            "message": (
                "ProjectX control plane healthy"
                if control_plane_healthy
                else (
                    "ProjectX control plane partially observable"
                    if phase_count or total_recent_contracts
                    else "ProjectX control plane unavailable"
                )
            ),
            "phase_non_ok_count": int(phase_summary.get("non_ok_count") or 0),
            "missing_contract_type_count": len(missing_types),
            "contract_coverage_ratio": coverage.get("coverage_ratio", 0.0),
        },
    }
