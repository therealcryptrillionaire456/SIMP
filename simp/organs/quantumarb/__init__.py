"""
QuantumArb Organ - Integration Contract

This module defines the integration contract between QuantumArb and the SIMP A2A system.
It provides mapping functions to convert QuantumArb decision summaries to standard
AgentDecisionSummary format for consumption by FinancialOps and other A2A components.

Integration Contract Version: 1.0.0
Compatible with: SIMP A2A Core v0.7.0
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum


class QuantumArbSide(str, Enum):
    """QuantumArb side mapping to standard trading sides."""
    BULL = "bull"          # Expect price increase
    BEAR = "bear"          # Expect price decrease
    NOTRADE = "notrade"    # No clear opportunity


class QuantumArbDecision(str, Enum):
    """QuantumArb decision types."""
    EXECUTE = "execute"
    NO_OPPORTUNITY = "no_opportunity"
    RISKY = "risky"


@dataclass
@dataclass
class QuantumArbDecisionSummary:
    """
    QuantumArb's internal decision summary format.
    
    This is the format logged by QuantumArb agent in decision_summary.jsonl.
    """
    timestamp: str                    # ISO 8601 timestamp
    intent_id: str                    # Traceability ID
    source_agent: str                 # Who sent the signal
    asset_pair: str                   # Trading instrument (e.g., "BTC-USD")
    side: str                         # BULL/BEAR/NOTRADE
    decision: str                     # Uppercase decision
    arb_type: str                     # Lowercase arb type
    dry_run: bool                     # Safety flag
    confidence: float                 # 0-1 confidence score
    timesfm_used: bool                # Whether TimesFM was consulted
    rationale_preview: str            # Abbreviated rationale
    
    # Optional fields (must come after required fields in dataclass)
    timesfm_rationale: Optional[str] = None  # TimesFM insight
    venue_a: Optional[str] = None     # First exchange venue
    venue_b: Optional[str] = None     # Second exchange venue
    estimated_spread_bps: Optional[float] = None  # Estimated spread in basis points


class QuantumArbIntegrationContract:
    """
    Integration contract defining how QuantumArb maps to A2A systems.
    
    This contract ensures stable integration between QuantumArb and:
    1. A2A Core (AgentDecisionSummary)
    2. FinancialOps (safety evaluation)
    3. KashClaw (execution mapping)
    4. Dashboard (visualization)
    """
    
    @staticmethod
    def map_to_agent_decision_summary(
        quantumarb_summary: QuantumArbDecisionSummary,
        default_quantity: float = 0.0,
        default_units: str = "USD"
    ) -> Dict[str, Any]:
        """
        Map QuantumArb decision summary to standard AgentDecisionSummary format.
        
        Args:
            quantumarb_summary: QuantumArb's internal decision summary
            default_quantity: Default quantity when not specified by QuantumArb
            default_units: Default units for quantity
            
        Returns:
            Dict in AgentDecisionSummary format for A2A consumption
        """
        # Map side from QuantumArb format to standard trading format
        side_map = {
            "BULL": "buy",
            "BEAR": "sell", 
            "NOTRADE": "hold"
        }
        
        standard_side = side_map.get(quantumarb_summary.side.upper(), "hold")
        
        # Determine volatility posture based on TimesFM usage and confidence
        volatility_posture = "neutral"
        if quantumarb_summary.timesfm_used:
            if quantumarb_summary.confidence > 0.7:
                volatility_posture = "conservative"
            elif quantumarb_summary.confidence < 0.3:
                volatility_posture = "aggressive"
        
        # Build AgentDecisionSummary
        return {
            "agent_name": "quantumarb",
            "instrument": quantumarb_summary.asset_pair,
            "side": standard_side,
            "quantity": default_quantity,
            "units": default_units,
            "confidence": quantumarb_summary.confidence,
            "horizon_days": 1,  # QuantumArb typically operates on intraday horizon
            "volatility_posture": volatility_posture,
            "timesfm_used": quantumarb_summary.timesfm_used,
            "rationale": quantumarb_summary.rationale_preview,
            "timestamp": quantumarb_summary.timestamp,
            
            # QuantumArb-specific metadata (preserved for traceability)
            "x_quantumarb": {
                "intent_id": quantumarb_summary.intent_id,
                "source_agent": quantumarb_summary.source_agent,
                "decision": quantumarb_summary.decision,
                "arb_type": quantumarb_summary.arb_type,
                "dry_run": quantumarb_summary.dry_run,
                "timesfm_rationale": quantumarb_summary.timesfm_rationale,
                "venue_a": quantumarb_summary.venue_a,
                "venue_b": quantumarb_summary.venue_b,
                "estimated_spread_bps": quantumarb_summary.estimated_spread_bps,
            }
        }
    
    @staticmethod
    def validate_quantumarb_summary(summary: Dict[str, Any]) -> bool:
        """
        Validate that a QuantumArb decision summary has all required fields.
        
        Args:
            summary: Dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = {
            "timestamp": str,
            "intent_id": str,
            "source_agent": str,
            "asset_pair": str,
            "side": str,
            "decision": str,
            "arb_type": str,
            "dry_run": bool,
            "confidence": (int, float),
            "timesfm_used": bool,
            "timesfm_rationale": (str, type(None)),
            "rationale_preview": str,
        }
        
        for field, expected_type in required_fields.items():
            if field not in summary:
                return False
            
            value = summary[field]
            if isinstance(expected_type, tuple):
                if not any(isinstance(value, t) for t in expected_type):
                    return False
            elif not isinstance(value, expected_type):
                return False
        
        # Additional validation
        if not 0 <= summary["confidence"] <= 1:
            return False
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(summary["timestamp"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        
        return True
    
    @staticmethod
    def get_safety_parameters() -> Dict[str, Any]:
        """
        Get safety parameters for QuantumArb operations.
        
        Returns:
            Dictionary of safety parameters for FinancialOps
        """
        return {
            "max_confidence_threshold": 0.8,      # Block trades above this confidence
            "min_confidence_threshold": 0.2,      # Block trades below this confidence
            "required_timesfm_for_live": True,    # TimesFM required for live trades
            "max_daily_trades": 10,               # Maximum trades per day
            "position_size_limit_usd": 1000.0,    # Maximum position size
            "allowed_arb_types": ["statistical", "cross_venue"],  # Allowed arbitrage types
            "blocked_venues": [],                 # Blocked exchange venues
        }


# Module-level singleton for easy access
CONTRACT = QuantumArbIntegrationContract()


# Export public interface
__all__ = [
    "QuantumArbSide",
    "QuantumArbDecision",
    "QuantumArbDecisionSummary",
    "QuantumArbIntegrationContract",
    "CONTRACT",
]