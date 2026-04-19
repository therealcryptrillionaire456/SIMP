"""
BRP (Bill Russell Protocol) Integration for QuantumArb Trading System.

This module provides enhanced BRP integration for the QuantumArb trading system,
enabling real-time threat evaluation, trade blocking, and security monitoring.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4

from simp.security.brp_bridge import BRPBridge
from simp.security.brp_models import (
    BRPEvent, BRPEventType, BRPMode, BRPSeverity, 
    BRPResponse, BRPObservation, BRPDecision
)

log = logging.getLogger(__name__)


class TradeAction(str, Enum):
    """Trading actions that can be evaluated by BRP."""
    ARB_EVALUATE = "arb_evaluate"
    TRADE_EXECUTE = "trade_execute"
    POSITION_UPDATE = "position_update"
    RISK_CHECK = "risk_check"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class TradeContext:
    """Context for a trading action being evaluated by BRP."""
    market: str
    action: TradeAction
    quantity: Optional[float] = None
    price: Optional[float] = None
    side: Optional[str] = None  # "buy" or "sell"
    spread_bps: Optional[float] = None
    position_size: Optional[float] = None
    pnl_today: Optional[float] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for BRP params."""
        result = {
            "market": self.market,
            "action": self.action.value,
            "quantity": self.quantity,
            "price": self.price,
            "side": self.side,
            "spread_bps": self.spread_bps,
            "position_size": self.position_size,
            "pnl_today": self.pnl_today,
            "tags": self.tags or [],
        }
        if self.metadata:
            result.update(self.metadata)
        return result


class QuantumArbBRPIntegrator:
    """
    Enhanced BRP integration for QuantumArb trading system.
    
    Provides real-time threat evaluation, trade blocking, and security monitoring
    for all trading activities.
    """
    
    def __init__(self, agent_id: str = "quantumarb", mode: BRPMode = BRPMode.ENFORCED):
        """
        Initialize the BRP integrator.
        
        Args:
            agent_id: ID of the agent using this integrator
            mode: BRP mode (SHADOW or LIVE). In LIVE mode, BRP can block trades.
        """
        self.agent_id = agent_id
        self.mode = mode
        self._bridge = None
        self._log_dir = Path("logs") / "quantumarb" / "brp"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            "evaluations": 0,
            "blocks": 0,
            "warnings": 0,
            "allows": 0,
            "errors": 0,
        }
        
        log.info(f"QuantumArb BRP Integrator initialized in {mode.value} mode")
    
    @property
    def bridge(self) -> BRPBridge:
        """Lazy initialization of BRP bridge."""
        if self._bridge is None:
            self._bridge = BRPBridge()
        return self._bridge
    
    def evaluate_trade_action(self, context: TradeContext) -> Tuple[bool, BRPResponse]:
        """
        Evaluate a trading action using BRP.
        
        Args:
            context: Trading context to evaluate
            
        Returns:
            Tuple of (allowed, response) where allowed is True if action is permitted
        """
        self.stats["evaluations"] += 1
        
        try:
            # Create BRP event
            event = BRPEvent(
                source_agent=self.agent_id,
                event_type=BRPEventType.ARBITRAGE.value,
                action=context.action.value,
                params=context.to_dict(),
                mode=self.mode.value,
                tags=context.tags or ["quantumarb", context.action.value],
            )
            
            # Evaluate with BRP
            response = self.bridge.evaluate_event(event)
            
            # Record observation
            observation = BRPObservation(
                source_agent=self.agent_id,
                event_id=event.event_id,
                action=context.action.value,
                outcome="evaluated",
                result_data={
                    "decision": response.decision,
                    "threat_score": response.threat_score,
                    "severity": response.severity,
                    "summary": response.summary,
                },
                mode=self.mode.value,
                tags=context.tags or ["quantumarb", context.action.value],
            )
            self.bridge.ingest_observation(observation)
            
            # Log the evaluation
            self._log_evaluation(event, response, context)
            
            # Update statistics
            if response.decision == "block":
                self.stats["blocks"] += 1
                log.warning(f"BRP BLOCKED trade action: {context.action} for {context.market}. "
                          f"Reason: {response.summary}")
                return False, response
            elif response.decision == "warn":
                self.stats["warnings"] += 1
                log.warning(f"BRP WARNING for trade action: {context.action} for {context.market}. "
                          f"Reason: {response.summary}")
                return True, response
            else:
                self.stats["allows"] += 1
                return True, response
                
        except Exception as e:
            self.stats["errors"] += 1
            log.error(f"BRP evaluation failed: {e}", exc_info=True)
            # On error, default to allowing (fail-open for safety)
            return True, BRPResponse(
                decision="allow",
                threat_score=0.0,
                severity="info",
                summary=f"BRP evaluation failed, defaulting to allow: {str(e)}",
                event_id=str(uuid4()),
            )
    
    def evaluate_arbitrage_opportunity(
        self, 
        market: str, 
        spread_bps: float,
        direction: str,
        dry_run: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, BRPResponse]:
        """
        Evaluate an arbitrage opportunity using BRP.
        
        Args:
            market: Trading market/pair
            spread_bps: Spread in basis points
            direction: Trade direction ("long" or "short")
            dry_run: Whether this is a dry run
            metadata: Additional metadata
            
        Returns:
            Tuple of (allowed, response)
        """
        context = TradeContext(
            market=market,
            action=TradeAction.ARB_EVALUATE,
            side=direction,
            spread_bps=spread_bps,
            tags=["arbitrage", "evaluation", market],
            metadata={
                "dry_run": dry_run,
                "direction": direction,
                "spread_bps": spread_bps,
                **(metadata or {}),
            }
        )
        
        return self.evaluate_trade_action(context)
    
    def evaluate_trade_execution(
        self,
        market: str,
        quantity: float,
        price: float,
        side: str,
        position_size: Optional[float] = None,
        pnl_today: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, BRPResponse]:
        """
        Evaluate a trade execution using BRP.
        
        Args:
            market: Trading market/pair
            quantity: Trade quantity
            price: Trade price
            side: Trade side ("buy" or "sell")
            position_size: Current position size in this market
            pnl_today: P&L for today so far
            metadata: Additional metadata
            
        Returns:
            Tuple of (allowed, response)
        """
        context = TradeContext(
            market=market,
            action=TradeAction.TRADE_EXECUTE,
            quantity=quantity,
            price=price,
            side=side,
            position_size=position_size,
            pnl_today=pnl_today,
            tags=["trade", "execution", market, side],
            metadata={
                "quantity": quantity,
                "price": price,
                "side": side,
                "position_size": position_size,
                "pnl_today": pnl_today,
                **(metadata or {}),
            }
        )
        
        return self.evaluate_trade_action(context)
    
    def record_trade_outcome(
        self,
        market: str,
        action: TradeAction,
        success: bool,
        outcome_data: Dict[str, Any],
        tags: Optional[List[str]] = None
    ) -> None:
        """
        Record the outcome of a trade action for BRP learning.
        
        Args:
            market: Trading market/pair
            action: Trade action that was performed
            success: Whether the action was successful
            outcome_data: Data about the outcome
            tags: Additional tags
        """
        try:
            observation = BRPObservation(
                source_agent=self.agent_id,
                event_id=str(uuid4()),
                action=action.value,
                outcome="success" if success else "failure",
                result_data={
                    "market": market,
                    "success": success,
                    **outcome_data,
                },
                mode=self.mode.value,
                tags=(tags or []) + ["quantumarb", action.value, market, "outcome"],
            )
            
            self.bridge.ingest_observation(observation)
            
            # Log the outcome
            log_file = self._log_dir / "trade_outcomes.jsonl"
            with open(log_file, "a") as f:
                record = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "market": market,
                    "action": action.value,
                    "success": success,
                    "outcome_data": outcome_data,
                    "tags": tags or [],
                }
                f.write(json.dumps(record) + "\n")
                
        except Exception as e:
            log.error(f"Failed to record trade outcome: {e}", exc_info=True)
    
    def _log_evaluation(self, event: BRPEvent, response: BRPResponse, context: TradeContext) -> None:
        """Log BRP evaluation to file."""
        try:
            log_file = self._log_dir / "evaluations.jsonl"
            with open(log_file, "a") as f:
                record = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "event_id": event.event_id,
                    "action": event.action,
                    "market": context.market,
                    "decision": response.decision,
                    "threat_score": response.threat_score,
                    "severity": response.severity,
                    "summary": response.summary,
                    "context": context.to_dict(),
                    "mode": self.mode.value,
                }
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            log.error(f"Failed to log BRP evaluation: {e}", exc_info=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return {
            **self.stats,
            "mode": self.mode.value,
            "log_dir": str(self._log_dir),
        }
    
    def emergency_stop(self, reason: str) -> BRPResponse:
        """
        Trigger an emergency stop through BRP.
        
        Args:
            reason: Reason for emergency stop
            
        Returns:
            BRP response
        """
        try:
            event = BRPEvent(
                source_agent=self.agent_id,
                event_type=BRPEventType.EMERGENCY.value,
                action=TradeAction.EMERGENCY_STOP.value,
                params={"reason": reason},
                mode=BRPMode.ENFORCED.value,
                tags=["quantumarb", "emergency", "stop"],
            )
            
            response = self.bridge.evaluate_event(event)
            
            # Log emergency stop
            emergency_log = self._log_dir / "emergency_stops.jsonl"
            with open(emergency_log, "a") as f:
                record = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "reason": reason,
                    "decision": response.decision,
                    "threat_score": response.threat_score,
                    "severity": response.severity,
                    "summary": response.summary,
                }
                f.write(json.dumps(record) + "\n")
            
            log.critical(f"EMERGENCY STOP triggered: {reason}. BRP response: {response.summary}")
            return response
            
        except Exception as e:
            log.error(f"Emergency stop failed: {e}", exc_info=True)
            # Return a blocking response even if BRP fails
            return BRPResponse(
                decision="block",
                threat_score=1.0,
                severity="critical",
                summary=f"Emergency stop triggered but BRP failed: {str(e)}",
                event_id=str(uuid4()),
            )


# Global instance for easy access
_brp_integrator = None


def get_brp_integrator(agent_id: str = "quantumarb", mode: BRPMode = BRPMode.ENFORCED) -> QuantumArbBRPIntegrator:
    """
    Get or create the global BRP integrator instance.
    
    Args:
        agent_id: Agent ID for the integrator
        mode: BRP mode (defaults to LIVE for production)
        
    Returns:
        QuantumArbBRPIntegrator instance
    """
    global _brp_integrator
    if _brp_integrator is None:
        _brp_integrator = QuantumArbBRPIntegrator(agent_id=agent_id, mode=mode)
    return _brp_integrator


def set_brp_mode(mode: BRPMode) -> None:
    """
    Set the BRP mode for the global integrator.
    
    Args:
        mode: New BRP mode
    """
    global _brp_integrator
    if _brp_integrator is not None:
        # Create new integrator with new mode
        _brp_integrator = QuantumArbBRPIntegrator(
            agent_id=_brp_integrator.agent_id,
            mode=mode
        )
        log.info(f"BRP mode changed to {mode.value}")


if __name__ == "__main__":
    # Test the BRP integrator
    import sys
    logging.basicConfig(level=logging.INFO)
    
    integrator = get_brp_integrator(mode=BRPMode.SHADOW)
    
    # Test arbitrage evaluation
    allowed, response = integrator.evaluate_arbitrage_opportunity(
        market="BTC-USD",
        spread_bps=15.5,
        direction="long",
        dry_run=True
    )
    print(f"Arbitrage evaluation: allowed={allowed}, decision={response.decision}, summary={response.summary}")
    
    # Test trade execution evaluation
    allowed, response = integrator.evaluate_trade_execution(
        market="BTC-USD",
        quantity=0.1,
        price=50000.0,
        side="buy",
        position_size=0.5,
        pnl_today=250.0
    )
    print(f"Trade execution: allowed={allowed}, decision={response.decision}, summary={response.summary}")
    
    # Record outcome
    integrator.record_trade_outcome(
        market="BTC-USD",
        action=TradeAction.TRADE_EXECUTE,
        success=True,
        outcome_data={"profit_usd": 125.0, "fees_usd": 2.5}
    )
    
    print(f"Stats: {integrator.get_stats()}")
    print("BRP integration test completed successfully")