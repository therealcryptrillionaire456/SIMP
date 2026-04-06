"""
SIMP Lifecycle State Machine + Event Envelopes — Sprint 5

Exhaustive mapping from SIMP lifecycle/delivery states to A2A task states,
plus event envelope construction with sensitive-field redaction.
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple


# ---------------------------------------------------------------------------
# State enumerations (plain classes — no enum dep needed)
# ---------------------------------------------------------------------------

class SimpLifecycleState:
    PENDING = "pending"
    QUEUED = "queued"
    EXECUTING = "executing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class A2ATaskState:
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    INPUT_REQUIRED = "input-required"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Exhaustive state map
# ---------------------------------------------------------------------------

_STATE_MAP: Dict[str, str] = {
    SimpLifecycleState.PENDING: A2ATaskState.SUBMITTED,
    SimpLifecycleState.QUEUED: A2ATaskState.SUBMITTED,
    SimpLifecycleState.EXECUTING: A2ATaskState.WORKING,
    SimpLifecycleState.IN_PROGRESS: A2ATaskState.WORKING,
    SimpLifecycleState.COMPLETED: A2ATaskState.COMPLETED,
    SimpLifecycleState.FAILED: A2ATaskState.FAILED,
    SimpLifecycleState.BLOCKED: A2ATaskState.INPUT_REQUIRED,
    SimpLifecycleState.CANCELLED: A2ATaskState.CANCELED,
    SimpLifecycleState.UNKNOWN: A2ATaskState.UNKNOWN,
}

_A2A_TERMINALS = {A2ATaskState.COMPLETED, A2ATaskState.FAILED, A2ATaskState.CANCELED}

# Delivery-status refinements
_DELIVERY_REFINEMENTS: Dict[str, str] = {
    "delivered": A2ATaskState.WORKING,
    "delivery_failed": A2ATaskState.FAILED,
    "timeout": A2ATaskState.FAILED,
    "rejected": A2ATaskState.FAILED,
}

# ---------------------------------------------------------------------------
# Sensitive-key detection
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS = re.compile(
    r"(api[_-]?key|token|secret|password|credential|auth|bearer|private[_-]?key)",
    re.IGNORECASE,
)


def _is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_PATTERNS.search(key))


# ---------------------------------------------------------------------------
# State projection
# ---------------------------------------------------------------------------


def simp_to_a2a_state(
    simp_state: str,
    delivery_status: Optional[str] = None,
) -> str:
    """
    Project a SIMP lifecycle state to an A2A task state.

    If *delivery_status* is provided it may refine the result (e.g.
    ``delivery_failed`` overrides ``executing`` → ``failed``).
    """
    base = _STATE_MAP.get(simp_state, A2ATaskState.UNKNOWN)
    if delivery_status and delivery_status in _DELIVERY_REFINEMENTS:
        refined = _DELIVERY_REFINEMENTS[delivery_status]
        # Only refine if it doesn't contradict a terminal base state
        if base not in _A2A_TERMINALS:
            base = refined
    return base


def is_terminal(a2a_state: str) -> bool:
    return a2a_state in _A2A_TERMINALS


def is_non_terminal(a2a_state: str) -> bool:
    return a2a_state not in _A2A_TERMINALS


# ---------------------------------------------------------------------------
# Event envelope builders
# ---------------------------------------------------------------------------


def _safe_payload(data: Optional[Dict[str, Any]], max_str_len: int = 200) -> Dict[str, Any]:
    """Return a redacted, truncated copy of *data*."""
    if not data:
        return {}
    out: Dict[str, Any] = {}
    for k, v in data.items():
        if _is_sensitive_key(k):
            out[k] = "[REDACTED]"
        elif isinstance(v, str) and len(v) > max_str_len:
            out[k] = v[:max_str_len] + "..."
        else:
            out[k] = v
    return out


def build_progress_event(
    task_id: str,
    simp_state: str,
    intent_type: str = "",
    data: Optional[Dict[str, Any]] = None,
    sequence: int = 0,
) -> Dict[str, Any]:
    """Build an A2A-compatible progress event envelope."""
    a2a = simp_to_a2a_state(simp_state)
    return {
        "taskId": task_id,
        "state": a2a,
        "terminal": is_terminal(a2a),
        "eventKind": "status_change",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sequence": sequence,
        "data": _safe_payload(data),
        "x-simp": {
            "simpState": simp_state,
            "intentType": intent_type,
            "protocol": "simp/1.0",
        },
    }


def build_completion_event(
    task_id: str,
    result: Optional[Dict[str, Any]] = None,
    intent_type: str = "",
    sequence: int = 0,
) -> Dict[str, Any]:
    """Build an A2A task-completed event envelope."""
    return {
        "taskId": task_id,
        "state": A2ATaskState.COMPLETED,
        "terminal": True,
        "eventKind": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sequence": sequence,
        "result": _safe_payload(result),
        "x-simp": {
            "simpState": SimpLifecycleState.COMPLETED,
            "intentType": intent_type,
            "protocol": "simp/1.0",
        },
    }


def build_failure_event(
    task_id: str,
    error: str = "",
    intent_type: str = "",
    sequence: int = 0,
) -> Dict[str, Any]:
    """Build an A2A task-failed event envelope."""
    # Truncate error for safety
    safe_error = error[:200] + "..." if len(error) > 200 else error
    return {
        "taskId": task_id,
        "state": A2ATaskState.FAILED,
        "terminal": True,
        "eventKind": "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sequence": sequence,
        "error": safe_error,
        "x-simp": {
            "simpState": SimpLifecycleState.FAILED,
            "intentType": intent_type,
            "protocol": "simp/1.0",
        },
    }


def events_from_intent_history(
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Reconstruct an A2A event sequence from SIMP broker intent records.

    Each record is expected to have at least ``intent_id`` and ``status``.
    """
    events: List[Dict[str, Any]] = []
    for idx, rec in enumerate(records):
        intent_id = rec.get("intent_id", "")
        status = rec.get("status", "unknown")
        intent_type = rec.get("intent_type", "")
        if status == "completed":
            events.append(build_completion_event(intent_id, intent_type=intent_type, sequence=idx))
        elif status == "failed":
            events.append(build_failure_event(intent_id, error=rec.get("error", ""), intent_type=intent_type, sequence=idx))
        else:
            events.append(build_progress_event(intent_id, status, intent_type=intent_type, sequence=idx))
    return events
