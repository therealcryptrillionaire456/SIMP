"""
Bill Russell Protocol (BRP) - Typed Schemas and Enums

Defines the core data contracts for the BRP supervisor layer:
- BRPEvent: Pre-action event submitted for evaluation
- BRPPlan: Multi-step plan submitted for review
- BRPObservation: Post-action observation record
- BRPResponse: Evaluation result returned by the bridge

Default mode is shadow/advisory - never enforced blocking unless
the action is clearly restricted and high-risk.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BRPDecision(str, Enum):
    """Possible BRP evaluation decisions."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    ELEVATE = "ELEVATE"
    LOG_ONLY = "LOG_ONLY"
    SHADOW_ALLOW = "SHADOW_ALLOW"


class BRPMode(str, Enum):
    """Operational modes for BRP evaluation."""
    ENFORCED = "enforced"
    ADVISORY = "advisory"
    SHADOW = "shadow"
    DISABLED = "disabled"


class BRPSeverity(str, Enum):
    """Severity levels for BRP events."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class BRPEventType(str, Enum):
    """Categories of BRP events."""
    TRADE_EXECUTION = "trade_execution"
    PLAN_REVIEW = "plan_review"
    WITHDRAWAL = "withdrawal"
    ADMIN_ACTION = "admin_action"
    ARBITRAGE = "arbitrage"
    OBSERVATION = "observation"
    GENERIC = "generic"


# ---------------------------------------------------------------------------
# High-risk action identifiers that trigger ELEVATE/DENY in enforced mode
# ---------------------------------------------------------------------------

RESTRICTED_ACTIONS = frozenset({
    "withdrawal",
    "admin_delete",
    "key_rotation",
    "fund_transfer",
    "permission_escalation",
    "contract_deploy",
})


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------

@dataclass
class BRPEvent:
    """
    Pre-action event submitted for BRP evaluation.

    Emitted by a goose *before* a material action (e.g. trade execution).
    schema_version: brp.event.v1
    """
    schema_version: str = "brp.event.v1"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source_agent: str = ""
    event_type: str = BRPEventType.GENERIC.value
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    mode: str = BRPMode.SHADOW.value
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "event_type": self.event_type,
            "action": self.action,
            "params": self.params,
            "context": self.context,
            "mode": self.mode,
            "tags": self.tags,
        }


@dataclass
class BRPPlan:
    """
    Multi-step plan submitted for BRP review.

    Emitted by Mother Goose / orchestrator before releasing a plan.
    schema_version: brp.plan.v1
    """
    schema_version: str = "brp.plan.v1"
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source_agent: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    mode: str = BRPMode.SHADOW.value
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "steps": self.steps,
            "context": self.context,
            "mode": self.mode,
            "tags": self.tags,
        }


@dataclass
class BRPObservation:
    """
    Post-action observation submitted after execution.

    Emitted by a goose *after* a material action completes (or fails).
    schema_version: brp.observation.v1
    """
    schema_version: str = "brp.observation.v1"
    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source_agent: str = ""
    event_id: str = ""  # correlates back to the pre-action BRPEvent
    action: str = ""
    outcome: str = ""  # "success", "failure", "partial"
    result_data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    mode: str = BRPMode.SHADOW.value
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "event_id": self.event_id,
            "action": self.action,
            "outcome": self.outcome,
            "result_data": self.result_data,
            "context": self.context,
            "mode": self.mode,
            "tags": self.tags,
        }


@dataclass
class BRPResponse:
    """
    Evaluation result returned by the BRP bridge.

    Contains the decision, threat assessment, and audit metadata.
    """
    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""  # correlates to BRPEvent.event_id or BRPPlan.plan_id
    decision: str = BRPDecision.SHADOW_ALLOW.value
    mode: str = BRPMode.SHADOW.value
    severity: str = BRPSeverity.INFO.value
    threat_score: float = 0.0  # 0.0 (safe) to 1.0 (critical threat)
    confidence: float = 1.0  # 0.0 to 1.0
    threat_tags: List[str] = field(default_factory=list)
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "event_id": self.event_id,
            "decision": self.decision,
            "mode": self.mode,
            "severity": self.severity,
            "threat_score": self.threat_score,
            "confidence": self.confidence,
            "threat_tags": self.threat_tags,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
