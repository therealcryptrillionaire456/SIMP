"""SIMP-side ProjectX phase status cache.

Stores bounded snapshots of ProjectX Phase 8-20 control-plane status so SIMP
can serve the latest known state even when the ProjectX guard is temporarily
unreachable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_PHASE_STATUS_LOG = Path("data") / "projectx_phase_status.jsonl"
MAX_FIELD_LEN = 4096
MAX_PHASES = 32


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_FIELD_LEN]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= MAX_PHASES * 8:
                break
            out[str(key)[:128]] = _trim(item)
        return out
    if isinstance(value, list):
        return [_trim(item) for item in value[:200]]
    return value


def normalize_phase_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("ProjectX phase status payload must be a JSON object")

    record = _trim(dict(payload))
    phases = record.get("phases")
    if phases is not None and not isinstance(phases, dict):
        raise ValueError("ProjectX phase status payload must include object 'phases'")

    record["schema_version"] = str(record.get("schema_version") or "projectx.phase-status.v1")
    record["status"] = str(record.get("status") or "ok")
    record["generated_at"] = str(record.get("generated_at") or utc_now_iso())
    record["source_agent"] = str(record.get("source_agent") or "projectx_native")
    record["phase_range"] = str(record.get("phase_range") or "8-20")
    record["phases"] = phases if isinstance(phases, dict) else {}
    return record


def append_phase_status(payload: Dict[str, Any], *, log_path: Path = DEFAULT_PHASE_STATUS_LOG) -> Dict[str, Any]:
    record = normalize_phase_status(payload)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_latest_phase_status(*, log_path: Path = DEFAULT_PHASE_STATUS_LOG) -> Optional[Dict[str, Any]]:
    if not log_path.exists():
        return None
    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None
