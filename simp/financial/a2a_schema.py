"""
A2A/FinancialOps core schemas for SIMP system.

This module defines pure, side-effect-free data structures for:
- Agent decision summaries (from QuantumArb, KashClaw, Kloutbot)
- Portfolio posture analysis
- A2A execution plans

All schemas are designed to be:
- Deterministic (pure functions only)
- Side-effect-free (no file I/O, network, DB, RPC)
- Safe to log and inspect (no secrets, no credentials)
- Compatible with A2A protocol requirements
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Union
from enum import Enum
import re
from datetime import datetime


class Side(str, Enum):
    """Trading side enumeration."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class RiskPosture(str, Enum):
    """Risk posture classification."""
    CONSERVATIVE = "conservative"
    NEUTRAL = "neutral"
    AGGRESSIVE = "aggressive"


class ExecutionMode(str, Enum):
    """Execution mode for A2A plans."""
    SIMULATED_ONLY = "simulated_only"
    LIVE_CANDIDATE = "live_candidate"


@dataclass
class AgentDecisionSummary:
    """
    Summary of a single agent's trading decision.
    
    This represents the output from agents like QuantumArb, KashClaw, and Kloutbot
    after they've analyzed market conditions and made a recommendation.
    
    Fields:
        agent_name: Identifier of the agent (e.g., "quantumarb", "kashclaw", "kloutbot")
        instrument: Trading instrument or asset pair (e.g., "BTC-USD", "ETH-USD")
        side: Recommended action (buy/sell/hold)
        quantity: Amount to trade (positive float)
        units: Unit of measurement (e.g., "USD", "BTC", "shares")
        confidence: Confidence score from 0.0 to 1.0 (optional)
        horizon_days: Time horizon in days (optional)
        volatility_posture: Volatility assessment (optional)
        timesfm_used: Whether TimesFM was used in the analysis
        rationale: Brief explanation of the decision (optional)
        timestamp: ISO 8601 timestamp of the decision
    """
    
    agent_name: str
    instrument: str
    side: Side
    quantity: float
    units: str
    
    # Optional fields with defaults
    confidence: Optional[float] = None
    horizon_days: Optional[int] = None
    volatility_posture: Optional[str] = None
    timesfm_used: bool = False
    rationale: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        """Validate the decision summary after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate the decision summary fields."""
        # Agent name validation
        if not self.agent_name or not isinstance(self.agent_name, str):
            raise ValueError("agent_name must be a non-empty string")
        
        # Instrument validation
        if not self.instrument or not isinstance(self.instrument, str):
            raise ValueError("instrument must be a non-empty string")
        
        # Side validation
        if not isinstance(self.side, Side):
            try:
                self.side = Side(self.side)
            except ValueError:
                raise ValueError(f"side must be one of {[s.value for s in Side]}")
        
        # Quantity validation
        if not isinstance(self.quantity, (int, float)):
            raise ValueError("quantity must be a number")
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        # HOLD can have 0 quantity, BUY/SELL must have positive quantity
        if self.side != Side.HOLD and self.quantity <= 0:
            raise ValueError("quantity must be positive for BUY/SELL decisions")
        
        # Units validation
        if not self.units or not isinstance(self.units, str):
            raise ValueError("units must be a non-empty string")
        
        # Confidence validation
        if self.confidence is not None:
            if not isinstance(self.confidence, (int, float)):
                raise ValueError("confidence must be a number")
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError("confidence must be between 0.0 and 1.0")
        
        # Horizon validation
        if self.horizon_days is not None:
            if not isinstance(self.horizon_days, int):
                raise ValueError("horizon_days must be an integer")
            if self.horizon_days <= 0:
                raise ValueError("horizon_days must be positive")
        
        # TimesFM validation
        if not isinstance(self.timesfm_used, bool):
            raise ValueError("timesfm_used must be a boolean")
        
        # Rationale validation
        if self.rationale is not None and not isinstance(self.rationale, str):
            raise ValueError("rationale must be a string or None")
        
        # Timestamp validation
        if not isinstance(self.timestamp, str):
            raise ValueError("timestamp must be a string")
        # Basic ISO 8601 format check
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$'
        if not re.match(iso_pattern, self.timestamp):
            raise ValueError("timestamp must be in ISO 8601 format")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "agent_name": self.agent_name,
            "instrument": self.instrument,
            "side": self.side.value,
            "quantity": self.quantity,
            "units": self.units,
            "confidence": self.confidence,
            "horizon_days": self.horizon_days,
            "volatility_posture": self.volatility_posture,
            "timesfm_used": self.timesfm_used,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AgentDecisionSummary":
        """Create from dictionary representation."""
        return cls(**data)


@dataclass
class PortfolioPosture:
    """
    Aggregate portfolio posture derived from multiple agent decisions.
    
    This represents the consolidated view of risk and exposure across
    all instruments and agents.
    
    Fields:
        aggregate_exposure: Dict mapping instrument -> net exposure in base units
        risk_posture: Overall risk classification
        max_leverage: Maximum allowed leverage (optional)
        per_instrument_caps: Dict mapping instrument -> max position size (optional)
        constraints: List of high-level constraints (optional)
        timestamp: ISO 8601 timestamp of the posture analysis
    """
    
    aggregate_exposure: Dict[str, float]
    risk_posture: RiskPosture
    
    # Optional fields with defaults
    max_leverage: Optional[float] = None
    per_instrument_caps: Optional[Dict[str, float]] = None
    constraints: Optional[List[str]] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        """Validate the portfolio posture after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate the portfolio posture fields."""
        # Aggregate exposure validation
        if not isinstance(self.aggregate_exposure, dict):
            raise ValueError("aggregate_exposure must be a dictionary")
        for instrument, exposure in self.aggregate_exposure.items():
            if not isinstance(instrument, str) or not instrument:
                raise ValueError("instrument keys must be non-empty strings")
            if not isinstance(exposure, (int, float)):
                raise ValueError("exposure values must be numbers")
        
        # Risk posture validation
        if not isinstance(self.risk_posture, RiskPosture):
            try:
                self.risk_posture = RiskPosture(self.risk_posture)
            except ValueError:
                raise ValueError(f"risk_posture must be one of {[r.value for r in RiskPosture]}")
        
        # Max leverage validation
        if self.max_leverage is not None:
            if not isinstance(self.max_leverage, (int, float)):
                raise ValueError("max_leverage must be a number")
            if self.max_leverage <= 0:
                raise ValueError("max_leverage must be positive")
        
        # Per-instrument caps validation
        if self.per_instrument_caps is not None:
            if not isinstance(self.per_instrument_caps, dict):
                raise ValueError("per_instrument_caps must be a dictionary or None")
            for instrument, cap in self.per_instrument_caps.items():
                if not isinstance(instrument, str) or not instrument:
                    raise ValueError("instrument keys must be non-empty strings")
                if not isinstance(cap, (int, float)):
                    raise ValueError("cap values must be numbers")
                if cap <= 0:
                    raise ValueError("cap values must be positive")
        
        # Constraints validation
        if self.constraints is not None:
            if not isinstance(self.constraints, list):
                raise ValueError("constraints must be a list or None")
            for constraint in self.constraints:
                if not isinstance(constraint, str):
                    raise ValueError("constraint items must be strings")
        
        # Timestamp validation
        if not isinstance(self.timestamp, str):
            raise ValueError("timestamp must be a string")
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$'
        if not re.match(iso_pattern, self.timestamp):
            raise ValueError("timestamp must be in ISO 8601 format")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "aggregate_exposure": self.aggregate_exposure,
            "risk_posture": self.risk_posture.value,
            "max_leverage": self.max_leverage,
            "per_instrument_caps": self.per_instrument_caps,
            "constraints": self.constraints,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PortfolioPosture":
        """Create from dictionary representation."""
        return cls(**data)


@dataclass
class A2APlan:
    """
    A2A execution plan combining agent decisions and portfolio posture.
    
    This is the main outbound payload that can be sent to an external
    executor or logged for audit purposes.
    
    Fields:
        decisions: List of agent decision summaries
        portfolio_posture: Derived portfolio posture
        execution_allowed: Whether execution is permitted
        execution_reason: Reason for execution decision
        execution_mode: Simulated vs live execution
        safety_checks_passed: List of safety checks that passed
        safety_checks_failed: List of safety checks that failed
        timestamp: ISO 8601 timestamp of the plan
    """
    
    decisions: List[AgentDecisionSummary]
    portfolio_posture: PortfolioPosture
    execution_allowed: bool = False
    execution_reason: str = "Default: execution disabled in this phase"
    execution_mode: ExecutionMode = ExecutionMode.SIMULATED_ONLY
    safety_checks_passed: List[str] = field(default_factory=list)
    safety_checks_failed: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        """Validate the A2A plan after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate the A2A plan fields."""
        # Decisions validation
        if not isinstance(self.decisions, list):
            raise ValueError("decisions must be a list")
        for decision in self.decisions:
            if not isinstance(decision, AgentDecisionSummary):
                raise ValueError("decisions must contain AgentDecisionSummary objects")
        
        # Portfolio posture validation
        if not isinstance(self.portfolio_posture, PortfolioPosture):
            raise ValueError("portfolio_posture must be a PortfolioPosture object")
        
        # Execution allowed validation
        if not isinstance(self.execution_allowed, bool):
            raise ValueError("execution_allowed must be a boolean")
        
        # Execution reason validation
        if not isinstance(self.execution_reason, str):
            raise ValueError("execution_reason must be a string")
        
        # Execution mode validation
        if not isinstance(self.execution_mode, ExecutionMode):
            try:
                self.execution_mode = ExecutionMode(self.execution_mode)
            except ValueError:
                raise ValueError(f"execution_mode must be one of {[m.value for m in ExecutionMode]}")
        
        # Safety checks validation
        if not isinstance(self.safety_checks_passed, list):
            raise ValueError("safety_checks_passed must be a list")
        for check in self.safety_checks_passed:
            if not isinstance(check, str):
                raise ValueError("safety_checks_passed items must be strings")
        
        if not isinstance(self.safety_checks_failed, list):
            raise ValueError("safety_checks_failed must be a list")
        for check in self.safety_checks_failed:
            if not isinstance(check, str):
                raise ValueError("safety_checks_failed items must be strings")
        
        # Timestamp validation
        if not isinstance(self.timestamp, str):
            raise ValueError("timestamp must be a string")
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$'
        if not re.match(iso_pattern, self.timestamp):
            raise ValueError("timestamp must be in ISO 8601 format")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "portfolio_posture": self.portfolio_posture.to_dict(),
            "execution_allowed": self.execution_allowed,
            "execution_reason": self.execution_reason,
            "execution_mode": self.execution_mode.value,
            "safety_checks_passed": self.safety_checks_passed,
            "safety_checks_failed": self.safety_checks_failed,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "A2APlan":
        """Create from dictionary representation."""
        # Convert nested dictionaries back to objects
        decisions = [AgentDecisionSummary.from_dict(d) for d in data.get("decisions", [])]
        portfolio_posture = PortfolioPosture.from_dict(data.get("portfolio_posture", {}))
        
        return cls(
            decisions=decisions,
            portfolio_posture=portfolio_posture,
            execution_allowed=data.get("execution_allowed", False),
            execution_reason=data.get("execution_reason", "Default: execution disabled in this phase"),
            execution_mode=data.get("execution_mode", ExecutionMode.SIMULATED_ONLY),
            safety_checks_passed=data.get("safety_checks_passed", []),
            safety_checks_failed=data.get("safety_checks_failed", []),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        )


# Validation helper functions
def validate_agent_decision_summary(data: Dict) -> AgentDecisionSummary:
    """Validate and create an AgentDecisionSummary from dictionary data."""
    return AgentDecisionSummary.from_dict(data)


def validate_portfolio_posture(data: Dict) -> PortfolioPosture:
    """Validate and create a PortfolioPosture from dictionary data."""
    return PortfolioPosture.from_dict(data)


def validate_a2a_plan(data: Dict) -> A2APlan:
    """Validate and create an A2APlan from dictionary data."""
    return A2APlan.from_dict(data)