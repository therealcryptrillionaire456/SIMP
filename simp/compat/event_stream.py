"""
SIMP A2A Event Stream — Sprint S3 (Sprint 33) + Sprint 58 (SSE buffer)

Converts SIMP ledger/log records to A2A-compatible task events
and provides a list wrapper for event endpoints.

Sprint 58 adds EventStreamBuffer — a thread-safe ring buffer with
per-subscriber queues for SSE streaming.
"""

import threading
from collections import deque
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


# ---------------------------------------------------------------------------
# Payment-specific event builder — Sprint 45
# ---------------------------------------------------------------------------

PAYMENT_EVENT_KINDS = frozenset({
    "proposal_created",
    "approval_granted",
    "execution_started",
    "execution_succeeded",
    "execution_failed",
})


def build_payment_event(
    event_kind: str,
    proposal_id: str,
    amount: float = 0.0,
    vendor: str = "",
    connector: str = "",
    status: str = "",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a payment-specific A2A event.

    NEVER includes PAN, card details, or payment credentials.
    """
    if event_kind not in PAYMENT_EVENT_KINDS:
        raise ValueError(f"Unknown payment event kind: {event_kind!r}")

    event: Dict[str, Any] = {
        "eventKind": event_kind,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "x-simp": {
            "protocol": "simp/1.0",
            "proposal_id": proposal_id,
            "amount": amount,
            "vendor": vendor,
            "connector": connector,
            "status": status,
        },
    }

    if error:
        # Truncate error to 200 chars
        event["error"] = error[:200] + "..." if len(error) > 200 else error

    return event


# ---------------------------------------------------------------------------
# Sprint 58 — SSE Event Stream Buffer
# ---------------------------------------------------------------------------

class EventStreamBuffer:
    """Thread-safe ring buffer for SSE event streaming.

    - Fixed-size ring buffer (default 1000 events).
    - Monotonically increasing sequence numbers.
    - Per-subscriber queues via subscribe() / get_subscriber_events().
    - push() broadcasts to all active subscribers.
    """

    def __init__(self, maxlen: int = 1000):
        self._lock = threading.Lock()
        self._buffer: deque = deque(maxlen=maxlen)
        self._sequence: int = 0
        self._subscribers: Dict[str, deque] = {}

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._sequence

    def push(self, event_type: str, data: Dict[str, Any]) -> int:
        """Add an event to the buffer and broadcast to subscribers.

        Returns the assigned sequence number.
        """
        with self._lock:
            self._sequence += 1
            seq = self._sequence
            entry = {
                "sequence": seq,
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._buffer.append(entry)
            # Broadcast to all subscribers
            for sub_queue in self._subscribers.values():
                sub_queue.append(entry)
            return seq

    def get_recent(self, limit: int = 50, since_sequence: int = 0) -> List[Dict[str, Any]]:
        """Return recent events, optionally filtered by sequence."""
        with self._lock:
            events = [e for e in self._buffer if e["sequence"] > since_sequence]
            return events[-limit:]

    def subscribe(self, subscriber_id: str) -> str:
        """Register a new subscriber. Returns the subscriber_id."""
        with self._lock:
            self._subscribers[subscriber_id] = deque(maxlen=1000)
            return subscriber_id

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscriber."""
        with self._lock:
            self._subscribers.pop(subscriber_id, None)

    def get_subscriber_events(self, subscriber_id: str, max_events: int = 50) -> List[Dict[str, Any]]:
        """Drain up to max_events from a subscriber's queue."""
        with self._lock:
            queue = self._subscribers.get(subscriber_id)
            if queue is None:
                return []
            events = []
            while queue and len(events) < max_events:
                events.append(queue.popleft())
            return events


# Module-level singleton
EVENT_BUFFER = EventStreamBuffer()
