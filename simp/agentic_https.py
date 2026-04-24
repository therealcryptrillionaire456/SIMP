"""
SIMP Agentic HTTPS

Canonical request/response wrappers for native SIMP agent invocation.
This keeps the core contract typed and local while remaining easy to expose
over broker HTTP, mesh, or direct in-process execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from simp.models.canonical_intent import CanonicalIntent


@dataclass
class AgentIdentity:
    """Cryptographic and addressing identity for an agent."""

    agent_id: str
    public_key: str = ""
    endpoint: str = ""
    trust_state: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgenticIntentRequest:
    """Request envelope for native SIMP intent invocation."""

    intent: CanonicalIntent
    identity: Optional[AgentIdentity] = None
    transport: str = "broker_http"
    invocation_mode: str = "http_native"
    expect_stream: bool = False
    ttl_seconds: int = 300
    trace_id: str = ""
    correlation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_intent: Dict[str, Any] = field(default_factory=dict)

    def to_broker_payload(self) -> Dict[str, Any]:
        if self.raw_intent and self.raw_intent.get("signature"):
            return dict(self.raw_intent)
        payload = self.intent.to_dict()
        if payload.get("signature"):
            # Signed payloads must remain byte-for-byte stable after signing.
            return payload
        payload["ttl_seconds"] = self.ttl_seconds
        payload["trace_id"] = self.trace_id or payload.get("trace_id", "")
        payload["correlation_id"] = self.correlation_id or payload.get("correlation_id", "")
        payload["invocation_mode"] = self.invocation_mode
        metadata = dict(payload.get("metadata", {}) or {})
        metadata.update(self.metadata)
        metadata.setdefault("transport", self.transport)
        metadata.setdefault("expect_stream", self.expect_stream)
        if self.identity is not None:
            metadata.setdefault("identity", self.identity.to_dict())
            if self.identity.public_key:
                metadata.setdefault("public_key", self.identity.public_key)
        payload["metadata"] = metadata
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgenticIntentRequest":
        if "intent" in data:
            raw_intent = dict(data.get("intent") or {})
            intent = CanonicalIntent.from_dict(raw_intent)
            identity_data = data.get("identity")
            identity = AgentIdentity(**identity_data) if isinstance(identity_data, dict) else None
            return cls(
                intent=intent,
                identity=identity,
                transport=str(data.get("transport") or "broker_http"),
                invocation_mode=str(data.get("invocation_mode") or "http_native"),
                expect_stream=bool(data.get("expect_stream", False)),
                ttl_seconds=int(data.get("ttl_seconds") or 300),
                trace_id=str(data.get("trace_id") or ""),
                correlation_id=str(data.get("correlation_id") or ""),
                metadata=dict(data.get("metadata") or {}),
                raw_intent=raw_intent,
            )

        # Allow direct canonical intent payloads to remain valid.
        raw_intent = dict(data)
        return cls(
            intent=CanonicalIntent.from_dict(raw_intent),
            transport="broker_http",
            invocation_mode=str(data.get("invocation_mode") or "http_native"),
            expect_stream=bool(data.get("expect_stream", False)),
            ttl_seconds=int(data.get("ttl_seconds") or 300),
            trace_id=str(data.get("trace_id") or ""),
            correlation_id=str(data.get("correlation_id") or ""),
            metadata=dict(data.get("metadata") or {}),
            raw_intent=raw_intent,
        )


@dataclass
class AgenticIntentResponse:
    """Uniform response envelope for agentic-HTTPS requests."""

    status: str
    success: bool
    intent_id: str = ""
    target_agent: str = ""
    task_id: str = ""
    error_code: str = ""
    error_message: str = ""
    delivery_status: str = ""
    delivery_method: str = ""
    invocation_mode: str = "http_native"
    trace_id: str = ""
    correlation_id: str = ""
    stream_endpoint: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "success": self.success,
            "intent_id": self.intent_id,
            "target_agent": self.target_agent,
            "task_id": self.task_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "delivery_status": self.delivery_status,
            "delivery_method": self.delivery_method,
            "invocation_mode": self.invocation_mode,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "stream_endpoint": self.stream_endpoint,
            "payload": self.payload,
        }

    @classmethod
    def from_route_result(
        cls,
        result: Dict[str, Any],
        *,
        invocation_mode: str,
        trace_id: str = "",
        correlation_id: str = "",
        stream_endpoint: str = "",
    ) -> "AgenticIntentResponse":
        success = str(result.get("status")) not in {"error", "failed"}
        delivery_method = ""
        mesh_routing = result.get("mesh_routing")
        if isinstance(mesh_routing, dict):
            delivery_method = str(mesh_routing.get("delivery_method") or "")
        if not delivery_method:
            delivery_method = str(result.get("delivery_method") or "")
        return cls(
            status=str(result.get("status") or "error"),
            success=success,
            intent_id=str(result.get("intent_id") or ""),
            target_agent=str(result.get("target_agent") or ""),
            task_id=str(result.get("task_id") or ""),
            error_code=str(result.get("error_code") or ""),
            error_message=str(result.get("error_message") or result.get("error") or ""),
            delivery_status=str(result.get("delivery_status") or ""),
            delivery_method=delivery_method,
            invocation_mode=invocation_mode,
            trace_id=trace_id or str(result.get("trace_id") or ""),
            correlation_id=correlation_id or str(result.get("correlation_id") or ""),
            stream_endpoint=stream_endpoint,
            payload=dict(result),
        )


def build_contract_description() -> Dict[str, Any]:
    """Return the published agentic-HTTPS contract description."""
    return {
        "protocol": "agentic_https",
        "version": "1.0",
        "identity_fields": ["agent_id", "public_key", "endpoint", "trust_state"],
        "request_fields": [
            "intent",
            "identity",
            "transport",
            "invocation_mode",
            "expect_stream",
            "ttl_seconds",
            "trace_id",
            "correlation_id",
            "metadata",
        ],
        "response_fields": [
            "status",
            "success",
            "intent_id",
            "target_agent",
            "task_id",
            "error_code",
            "error_message",
            "delivery_status",
            "delivery_method",
            "invocation_mode",
            "trace_id",
            "correlation_id",
            "stream_endpoint",
            "payload",
        ],
        "streaming": {
            "mode": "sse",
            "task_stream_template": "/tasks/{task_id}/stream",
        },
        "invocation_modes": [
            "native",
            "mesh_native",
            "http_native",
            "external_bridge",
            "mcp_bridge",
        ],
        "errors": [
            "BROKER_NOT_RUNNING",
            "VALIDATION_FAILED",
            "INVALID_SIGNATURE",
            "AGENT_NOT_FOUND",
            "BRP_DENIED",
            "BRP_REVIEW_REQUIRED",
            "TIMEOUT",
            "INTERNAL_ERROR",
        ],
    }
