import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

@dataclass
class Agent:
    """Represents an agent in SIMP network"""
    id: str
    organization: str
    public_key: str = ""

@dataclass
class Intent:
    """SIMP Intent - request from one agent to another"""
    simp_version: str = "1.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_agent: Optional[Agent] = None
    intent_type: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    signature: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "simp_version": self.simp_version,
            "id": self.id,
            "timestamp": self.timestamp,
            "source_agent": {
                "id": self.source_agent.id,
                "organization": self.source_agent.organization,
                "public_key": self.source_agent.public_key
            } if self.source_agent else None,
            "intent": {
                "type": self.intent_type,
                "params": self.params
            },
            "signature": self.signature
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())

@dataclass
class SimpResponse:
    """Response to a SIMP intent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intent_id: str = ""
    status: str = "success"  # or "error"
    data: Dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "status": self.status,
            "data": self.data,
            "error_code": self.error_code,
            "error_message": self.error_message
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
