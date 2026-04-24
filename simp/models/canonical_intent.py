"""Canonical SIMP intent schema — single source of truth.

This is the schema authority. ProjectX and all agents should reference this
for the definitive view of intent structure, types, and routing semantics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


# === Intent Type Registry ===
# Every valid intent type and its metadata.
# ProjectX should sync this registry into its protocol KB.

INTENT_TYPE_REGISTRY = {
    # Core protocol types
    "code_task": {"task_type": "implementation", "description": "Code implementation task"},
    "code_editing": {"task_type": "implementation", "description": "Code modification/refactoring"},
    "planning": {"task_type": "architecture", "description": "Architecture and planning"},
    "research": {"task_type": "research", "description": "Research and information gathering"},
    "market_analysis": {"task_type": "analysis", "description": "Market analysis and prediction"},
    "trade_execution": {"task_type": "implementation", "description": "Trade execution on exchanges"},
    "orchestration": {"task_type": "architecture", "description": "Multi-agent orchestration command"},
    "scaffolding": {"task_type": "scaffold", "description": "Project scaffolding and setup"},
    "test_harness": {"task_type": "test", "description": "Test creation and execution"},
    "prediction_signal": {"task_type": "analysis", "description": "Predictive signal generation"},
    "arbitrage": {"task_type": "implementation", "description": "Arbitrage opportunity execution"},
    "arbitrage_opportunity": {"task_type": "implementation", "description": "Arbitrage opportunity detection and execution"},
    "spec": {"task_type": "spec", "description": "Specification writing"},
    "architecture": {"task_type": "architecture", "description": "Architecture design"},
    "docs": {"task_type": "docs", "description": "Documentation generation"},
    # Computer use types
    "computer_use": {"task_type": "implementation", "description": "Computer-use action execution"},
    "computer_use_design_review": {"task_type": "research", "description": "Design review via computer-use"},
    # Self-improvement types
    "improve_tree": {"task_type": "analysis", "description": "Decision tree optimization request"},
    "native_agent_repo_scan": {"task_type": "analysis", "description": "ProjectX repo introspection scan"},
    # New types for expanded routing
    "code_review": {"task_type": "test", "description": "Code review and quality assessment"},
    "summarization": {"task_type": "docs", "description": "Content summarization"},
    "submit_goal": {"task_type": "architecture", "description": "High-level goal submission for decomposition"},
    # Legacy/extended types (backward compat with existing agents and tests)
    "test": {"task_type": "test", "description": "Generic test intent"},
    "system_test": {"task_type": "test", "description": "System-level test intent"},
    "research_request": {"task_type": "research", "description": "Research request from agent"},
    "research_finding": {"task_type": "research", "description": "Research finding report"},
    "detect_signal": {"task_type": "analysis", "description": "Signal detection"},
    "analyze_patterns": {"task_type": "analysis", "description": "Pattern analysis"},
    "vectorize": {"task_type": "implementation", "description": "Vectorization task"},
    "generate_strategy": {"task_type": "analysis", "description": "Strategy generation"},
    "validate_action": {"task_type": "test", "description": "Action validation"},
    "trade_signal": {"task_type": "analysis", "description": "Trade signal emission"},
    "arbitrage_check": {"task_type": "analysis", "description": "Arbitrage opportunity check"},
    "orchestration_command": {"task_type": "architecture", "description": "Orchestration command"},
    "check_status": {"task_type": "research", "description": "Status check request"},
    "status_check": {"task_type": "research", "description": "Diagnostic status check"},
    "health_check": {"task_type": "research", "description": "Agent health check request"},
    "get_status": {"task_type": "research", "description": "Structured runtime status query"},
    "get_statistics": {"task_type": "analysis", "description": "Agent metrics and statistics query"},
    "get_deployment_status": {"task_type": "research", "description": "Quantum deployment status query"},
    "solve_quantum_problem": {"task_type": "analysis", "description": "Quantum-assisted problem solving request"},
    "optimize_portfolio": {"task_type": "analysis", "description": "Quantum portfolio optimization request"},
    "evolve_quantum_skills": {"task_type": "analysis", "description": "Quantum skill evolution request"},
    "replan": {"task_type": "architecture", "description": "Replanning request"},
}

# Required fields for every intent
REQUIRED_FIELDS = ["intent_id", "source_agent", "intent_type", "params"]

# Optional fields
OPTIONAL_FIELDS = [
    "target_agent",
    "simp_version",
    "timestamp",
    "signature",
    "priority",
    "ttl_seconds",
    "trace_id",
    "correlation_id",
    "metadata",
    "invocation_mode",
    "_sig_nonce",
    "_sig_exp",
    "_sig_iat",
    "_sig_kid",
]


@dataclass
class CanonicalIntent:
    """The single canonical intent format for SIMP protocol.

    Both the Intent dataclass (simp/intent.py) and broker dict format
    are mapped to/from this canonical form.
    """
    intent_id: str = field(default_factory=lambda: f"intent:{uuid.uuid4()}")
    simp_version: str = "1.0"
    source_agent: str = ""  # Agent ID string
    target_agent: str = ""  # Agent ID string (optional — broker resolves)
    intent_type: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signature: str = ""
    priority: str = "medium"  # critical, high, medium, low
    ttl_seconds: int = 300
    trace_id: str = ""
    correlation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    invocation_mode: str = "native"
    _sig_nonce: str = ""
    _sig_exp: Optional[float] = None
    _sig_iat: Optional[float] = None
    _sig_kid: str = ""

    def validate(self) -> List[str]:
        """Validate this intent against the canonical schema. Returns list of errors."""
        errors = []
        if not self.source_agent:
            errors.append("source_agent is required")
        if not self.intent_type:
            errors.append("intent_type is required")
        if self.intent_type and self.intent_type not in INTENT_TYPE_REGISTRY:
            errors.append(f"Unknown intent_type: '{self.intent_type}'. Known types: {sorted(INTENT_TYPE_REGISTRY.keys())}")
        if not isinstance(self.params, dict):
            errors.append("params must be a dict")
        if not isinstance(self.metadata, dict):
            errors.append("metadata must be a dict")
        if self.priority not in ("critical", "high", "medium", "low"):
            errors.append(f"Invalid priority: '{self.priority}'")
        if self.ttl_seconds < 0:
            errors.append("ttl_seconds must be non-negative")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to flat dict for broker consumption."""
        return {
            "intent_id": self.intent_id,
            "simp_version": self.simp_version,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "intent_type": self.intent_type,
            "params": self.params,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "priority": self.priority,
            "ttl_seconds": self.ttl_seconds,
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "invocation_mode": self.invocation_mode,
            "_sig_nonce": self._sig_nonce,
            "_sig_exp": self._sig_exp,
            "_sig_iat": self._sig_iat,
            "_sig_kid": self._sig_kid,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalIntent":
        """Create from any dict format (legacy Intent dict or broker dict).

        Handles both the Intent dataclass format (nested source_agent object)
        and the broker flat dict format (source_agent as string).
        """
        # Handle nested source_agent (from Intent dataclass)
        source = data.get("source_agent", "")
        if isinstance(source, dict):
            source = source.get("id", "")

        # Handle nested intent (from Intent dataclass)
        intent_type = data.get("intent_type", "")
        params = data.get("params", {})
        if "intent" in data and isinstance(data["intent"], dict):
            intent_type = intent_type or data["intent"].get("type", "")
            params = params or data["intent"].get("params", {})

        return cls(
            intent_id=data.get("intent_id", data.get("id", f"intent:{uuid.uuid4()}")),
            simp_version=data.get("simp_version", "1.0"),
            source_agent=source,
            target_agent=data.get("target_agent", ""),
            intent_type=intent_type,
            params=params,
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            signature=data.get("signature", ""),
            priority=data.get("priority", "medium"),
            ttl_seconds=int(data.get("ttl_seconds", 300) or 0),
            trace_id=data.get("trace_id", ""),
            correlation_id=data.get("correlation_id", ""),
            metadata=data.get("metadata", {}) or {},
            invocation_mode=data.get("invocation_mode", "native"),
            _sig_nonce=data.get("_sig_nonce", ""),
            _sig_exp=data.get("_sig_exp"),
            _sig_iat=data.get("_sig_iat"),
            _sig_kid=data.get("_sig_kid", ""),
        )

    def get_task_type(self) -> str:
        """Map this intent to a TaskLedger task type."""
        entry = INTENT_TYPE_REGISTRY.get(self.intent_type, {})
        return entry.get("task_type", "implementation")
