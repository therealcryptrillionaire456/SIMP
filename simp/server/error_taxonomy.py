from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
import uuid


class SimpErrorCode(Enum):
    """Canonical SIMP error codes — used across all surfaces (native + MCP)."""
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    TOOL_INVOCATION_FAILED = "TOOL_INVOCATION_FAILED"
    ROUTE_FAILED = "ROUTE_FAILED"
    STREAM_UNAVAILABLE = "STREAM_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    TIMEOUT = "TIMEOUT"
    BAD_GATEWAY = "BAD_GATEWAY"


ERROR_HTTP_MAP = {
    SimpErrorCode.INVALID_SIGNATURE: 401,
    SimpErrorCode.UNAUTHORIZED: 403,
    SimpErrorCode.NOT_FOUND: 404,
    SimpErrorCode.INVALID_REQUEST: 400,
    SimpErrorCode.TOOL_INVOCATION_FAILED: 500,
    SimpErrorCode.ROUTE_FAILED: 502,
    SimpErrorCode.STREAM_UNAVAILABLE: 503,
    SimpErrorCode.RATE_LIMITED: 429,
    SimpErrorCode.INTERNAL_ERROR: 500,
    SimpErrorCode.TIMEOUT: 504,
    SimpErrorCode.BAD_GATEWAY: 502,
}


@dataclass
class SimpError:
    """Structured error response for all SIMP surfaces."""
    code: SimpErrorCode
    message: str
    detail: Optional[Dict[str, Any]] = None
    error_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "code": self.code.value,
            "message": self.message,
            "detail": self.detail or {},
            "http_status": ERROR_HTTP_MAP.get(self.code, 500),
        }

    def to_response(self) -> Dict[str, Any]:
        """Return a full response envelope for API endpoints."""
        return {
            "success": False,
            "error": self.to_dict(),
        }
