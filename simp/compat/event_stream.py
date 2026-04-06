"""
SIMP A2A Event Stream — Sprint S3 (Sprint 33)

Converts SIMP ledger/log records to A2A-compatible task events
and provides a list wrapper for event endpoints.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from simp.compat.lifecycle_map import (
    simp_to_a2a_state,
    is_terminal,
    _is_sensitive_key,
)


# ---------------------------------------------------------------------------
# Single event builder
# ---------------------------------------------------------------------------


def build_a2a_event(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a SIMP ledger/log record to an A2A-style task event.

    NEVER includes: api_key values, token values, raw error stacktraces
    (truncated to 200 chars).
    """
    intent_id = record.get("intent_id", "")
    simp_state = record.get("status", "unknown")
    a2a_state = simp_to_a2a_state(simp_state, record.get("delivery_status"))
    terminal = is_terminal(a2a_state)

    # Determine event kind
    if simp_state == "completed":
        event_kind = "completed"
    elif simp_state == "failed":
        event_kind = "error"
    else:
        event_kind = "status_change"

    # Truncate error
    error = record.get("error", "")
    if isinstance(error, str) and len(error) > 200:
        error = error[:200] + "..."

    event: Dict[str, Any] = {
        "taskId": intent_id,
        "state": a2a_state,
        "terminal": terminal,
        "eventKind": event_kind,
        "timestamp": record.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "sequence": record.get("sequence", 0),
        "x-simp": {},
    }

    # Populate x-simp namespace (filter sensitive keys)
    x_simp: Dict[str, Any] = {}
    for key, field_name in [
        ("intentId", "intent_id"),
        ("simpState", "status"),
        ("intentType", "intent_type"),
        ("deliveryStatus", "delivery_status"),
        ("sourceAgent", "source_agent"),
        ("targetAgent", "target_agent"),
    ]:
        val = record.get(field_name)
        if val is not None and not _is_sensitive_key(field_name):
            x_simp[key] = val

    event["x-simp"] = x_simp

    if error:
        event["error"] = error

    return event


# ---------------------------------------------------------------------------
# Events list builder
# ---------------------------------------------------------------------------


def build_a2a_events_list(
    ledger_records: List[Dict[str, Any]],
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Wrap multiple SIMP records as an A2A events list.

    - Filters out records with no intent_id.
    - Sorts by timestamp descending.
    - Caps at *limit* (max 100).
    """
    limit = max(1, min(limit, 100))

    # Filter records with an intent_id
    filtered = [r for r in ledger_records if r.get("intent_id")]

    # Sort by timestamp descending (most recent first)
    filtered.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

    # Cap
    filtered = filtered[:limit]

    events = [build_a2a_event(r) for r in filtered]

    return {
        "events": events,
        "count": len(events),
        "x-simp": {
            "protocol": "simp/1.0",
            "total": len(events),
            "limit": limit,
        },
    }
