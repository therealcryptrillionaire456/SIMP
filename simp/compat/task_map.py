"""
SIMP A2A Task Translation — Sprint 2

Allowlist-gated mapping from A2A task types to SIMP CanonicalIntent types,
plus state projection and A2A TaskStatus construction.
"""

from typing import Dict, Tuple, Optional, Any, List
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# A2A task type → SIMP intent type allowlist
# ---------------------------------------------------------------------------

A2A_TO_SIMP_INTENT: Dict[str, str] = {
    "planning": "planning",
    "research": "research",
    "code_task": "code_task",
    "status_check": "status_check",
    "capability_query": "capability_query",
    "ping": "ping",
    "health_check": "native_agent_health_check",
    "task_audit": "native_agent_task_audit",
    "security_audit": "native_agent_security_audit",
    "repo_scan": "native_agent_repo_scan",
}

# Aliases
_ALIASES: Dict[str, str] = {
    "plan": "planning",
    "analyze": "research",
    "analysis": "research",
    "code": "code_task",
    "status": "status_check",
    "capabilities": "capability_query",
    "heartbeat": "ping",
    "health": "health_check",
    "audit": "task_audit",
    "scan": "repo_scan",
}

# ---------------------------------------------------------------------------
# SIMP state → A2A state projection
# ---------------------------------------------------------------------------

_SIMP_TO_A2A_STATE: Dict[str, str] = {
    "pending": "submitted",
    "queued": "submitted",
    "executing": "working",
    "in_progress": "working",
    "completed": "completed",
    "failed": "failed",
    "blocked": "input-required",
    "cancelled": "canceled",
    "unknown": "unknown",
}

_A2A_TERMINAL_STATES = {"completed", "failed", "canceled"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def translate_a2a_to_simp(task_type: str) -> Tuple[str, Optional[str]]:
    """
    Translate an A2A task type to its SIMP intent type.

    Returns (simp_intent_type, None) on success, or
    ("", error_message) if the task type is not in the allowlist.
    """
    # Direct match
    if task_type in A2A_TO_SIMP_INTENT:
        return A2A_TO_SIMP_INTENT[task_type], None
    # Alias match
    canonical = _ALIASES.get(task_type)
    if canonical and canonical in A2A_TO_SIMP_INTENT:
        return A2A_TO_SIMP_INTENT[canonical], None
    return "", f"Unknown A2A task type: {task_type}"


def validate_a2a_payload(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate that an incoming A2A task payload has the required fields.

    Required: task_type (str).
    Optional: input (dict), task_id (str).
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object"
    if "task_type" not in payload:
        return False, "Missing required field: task_type"
    if not isinstance(payload["task_type"], str):
        return False, "task_type must be a string"
    return True, None


def simp_state_to_a2a(simp_state: str) -> str:
    """Project a SIMP lifecycle state to an A2A task state."""
    return _SIMP_TO_A2A_STATE.get(simp_state, "unknown")


def is_a2a_terminal(a2a_state: str) -> bool:
    """Return True if the A2A state is terminal."""
    return a2a_state in _A2A_TERMINAL_STATES


def build_a2a_task_status(
    task_id: str,
    simp_state: str,
    intent_type: str = "",
    message: str = "",
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build an A2A TaskStatus response from SIMP task state.
    """
    a2a_state = simp_state_to_a2a(simp_state)
    status: Dict[str, Any] = {
        "taskId": task_id,
        "state": a2a_state,
        "terminal": is_a2a_terminal(a2a_state),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "x-simp": {
            "simpState": simp_state,
            "intentType": intent_type,
            "protocol": "simp/1.0",
        },
    }
    if message:
        status["message"] = message
    if result:
        status["result"] = result
    return status
