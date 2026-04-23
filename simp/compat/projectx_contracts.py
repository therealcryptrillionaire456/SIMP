"""ProjectX/SIMP contract store.

This module is the SIMP-side boundary for ProjectX producers. It accepts a
small set of stable JSON contracts and stores them append-only so broker,
dashboard, and watchtower surfaces can observe ProjectX progress without
depending on ProjectX internals.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


CONTRACT_TYPES = {
    "mission_lifecycle_event",
    "validation_evidence",
    "policy_decision",
    "memory_episode",
    "scoreboard_metric",
}

DEFAULT_CONTRACT_LOG = Path("data") / "projectx_contracts.jsonl"
MAX_FIELD_LEN = 4096


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_FIELD_LEN]
    if isinstance(value, dict):
        return {str(k)[:128]: _trim(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_trim(item) for item in value[:200]]
    return value


def normalize_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("ProjectX contract payload must be a JSON object")

    contract_type = str(payload.get("contract_type") or payload.get("type") or "").strip()
    if contract_type not in CONTRACT_TYPES:
        raise ValueError(f"unsupported ProjectX contract_type: {contract_type!r}")

    record = _trim(dict(payload))
    record["schema_version"] = str(record.get("schema_version") or "projectx.contract.v1")
    record["contract_type"] = contract_type
    record["record_id"] = str(record.get("record_id") or f"pxc-{uuid.uuid4().hex[:12]}")
    record["timestamp"] = str(record.get("timestamp") or utc_now_iso())
    record["source_agent"] = str(record.get("source_agent") or "projectx_native")
    return record


def append_contract(payload: Dict[str, Any], *, log_path: Path = DEFAULT_CONTRACT_LOG) -> Dict[str, Any]:
    record = normalize_contract(payload)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_contracts(
    *,
    log_path: Path = DEFAULT_CONTRACT_LOG,
    limit: int = 50,
    contract_type: Optional[str] = None,
    mission_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    if contract_type and contract_type not in CONTRACT_TYPES:
        raise ValueError(f"unsupported ProjectX contract_type: {contract_type!r}")
    if not log_path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if contract_type and row.get("contract_type") != contract_type:
            continue
        if mission_id and row.get("mission_id") != mission_id:
            continue
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def contract_summary(*, log_path: Path = DEFAULT_CONTRACT_LOG) -> Dict[str, Any]:
    rows = read_contracts(log_path=log_path, limit=500)
    counts = {contract_type: 0 for contract_type in sorted(CONTRACT_TYPES)}
    latest_by_type: Dict[str, Dict[str, Any]] = {}
    mission_ids = set()

    for row in rows:
        contract_type = str(row.get("contract_type") or "")
        if contract_type in counts:
            counts[contract_type] += 1
            latest_by_type.setdefault(contract_type, row)
        if row.get("mission_id"):
            mission_ids.add(str(row["mission_id"]))

    missing_contract_types = [key for key, value in counts.items() if value == 0]
    return {
        "status": "ok",
        "generated_at": utc_now_iso(),
        "total_recent": len(rows),
        "counts": counts,
        "latest_by_type": latest_by_type,
        "mission_count": len(mission_ids),
        "missing_contract_types": missing_contract_types,
        "contract_types": sorted(CONTRACT_TYPES),
    }


def append_many_contracts(payloads: Iterable[Dict[str, Any]], *, log_path: Path = DEFAULT_CONTRACT_LOG) -> List[Dict[str, Any]]:
    records = []
    for payload in payloads:
        records.append(append_contract(payload, log_path=log_path))
    return records
