"""
SIMP Server Validation Models — Pydantic schemas for request validation.

These complement the request_guards module with structured Pydantic models.

- AgentRegistration: Used in http_server.py for registration endpoint validation.
- ResponseRecording: Used for response recording validation.
- IntentRequest: Superseded by CanonicalIntent (simp.models.canonical_intent).
  The canonical schema is the single source of truth for intent structure and types.
  This model is retained only for reference; all new intent validation should use
  CanonicalIntent.from_dict() and CanonicalIntent.validate().
"""

import re
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional

# ISO 8601 datetime pattern
_ISO_8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)


class IntentRequest(BaseModel):
    """Pydantic model for validating intent routing requests.

    NOTE: Superseded by CanonicalIntent (simp.models.canonical_intent) as of Sprint 17.
    Use CanonicalIntent.from_dict() for intent normalization and validation.
    """
    user_id: str = Field(default="", min_length=0, max_length=100)
    intent: str = Field(..., min_length=1, max_length=100)
    parameters: Dict = Field(default_factory=dict)


class AgentRegistration(BaseModel):
    """Pydantic model for validating agent registration requests."""
    agent_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-:.]+$")
    agent_name: str = Field(default="", max_length=255)
    agent_type: str = Field(default="generic", max_length=64)
    capabilities: List[str] = Field(default_factory=list)
    endpoint: str = Field(default="", max_length=256)
    public_key: Optional[str] = Field(default=None, max_length=4096)

    @field_validator("capabilities")
    @classmethod
    def cap_length(cls, v):
        for cap in v:
            if len(cap) > 50:
                raise ValueError(f"capability '{cap[:20]}...' exceeds 50 chars")
        return v


class ResponseRecording(BaseModel):
    """Pydantic model for validating response recording requests."""
    response_id: str = Field(..., min_length=1, max_length=100)
    content: str = Field(default="", max_length=10000)
    timestamp: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def valid_timestamp(cls, v):
        if v is not None and not _ISO_8601_RE.match(v):
            raise ValueError("timestamp must be ISO 8601 format")
        return v
