"""
SIMP Route Contract — Standardized response envelope for /agentic/intents/route.

Defines the status enums, stream availability enum, and RouteEnvelope
dataclass that normalizes the intent routing response into a consistent,
predictable format.

Tranche 17: Streaming and Route-State Hardening.
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid


class RouteStatus(Enum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    IMMEDIATE = "immediate"
    FAILED = "failed"
    INVALID_SIGNATURE = "invalid_signature"


class StreamAvailability(Enum):
    STREAM_AVAILABLE = "stream_available"
    STREAM_UNAVAILABLE = "stream_unavailable"
    NON_STREAM_FALLBACK = "non_stream_fallback"


@dataclass
class RouteEnvelope:
    """Standardized response envelope for /agentic/intents/route."""

    intent_id: str = field(
        default_factory=lambda: f"intent_{uuid.uuid4().hex[:12]}"
    )
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    correlation_id: str = ""
    status: RouteStatus = RouteStatus.ACCEPTED
    stream_availability: StreamAvailability = StreamAvailability.STREAM_UNAVAILABLE
    stream_url: str = ""
    invocation_mode: str = "native"
    bridge_mode: str = "none"
    delivery_status: str = "pending"
    delivery_method: str = "direct"
    delivery_latency_ms: float = 0.0
    error_code: str = ""
    error_message: str = ""
    result: Optional[Dict[str, Any]] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "stream_availability": self.stream_availability.value,
            "stream_url": self.stream_url,
            "invocation_mode": self.invocation_mode,
            "bridge_mode": self.bridge_mode,
            "delivery_status": self.delivery_status,
            "delivery_method": self.delivery_method,
            "delivery_latency_ms": self.delivery_latency_ms,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "result": self.result,
            "created_at": self.created_at,
        }
