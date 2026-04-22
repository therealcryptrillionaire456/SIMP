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
        self._last_event_id = ""
        self._recent_trade_events: Dict[str, Dict[str, Any]] = {}
        
        log.info(f"QuantumArb BRP Integrator initialized in {mode.value} mode")
    
    @property
    def bridge(self) -> BRPBridge:
        """Lazy initialization of BRP bridge."""
        if self._bridge is None:
            self._bridge = BRPBridge()
        return self._bridge

    @staticmethod
    def _interpret_brp_decision(decision: str) -> str:
        decision_value = str(decision or "").strip().upper()
        if decision_value == BRPDecision.DENY.value:
            return "block"
        if decision_value == BRPDecision.ELEVATE.value:
            return "warn"
        if decision_value in {
            BRPDecision.ALLOW.value,
            BRPDecision.SHADOW_ALLOW.value,
            BRPDecision.LOG_ONLY.value,
        }:
            return "allow"
        return "allow"

    @staticmethod
    def _trade_cache_key(market: str, action: TradeAction) -> str:
        return f"{str(market or '').strip().lower()}::{action.value}"

    def _read_incident_snapshot(self, event_id: str) -> Optional[Dict[str, Any]]:
        if not event_id:
            return None
        try:
            detail = self.bridge.read_operator_evaluation_detail(
                event_id=event_id,
                data_dir=str(self.bridge.data_dir),
            )
        except Exception:
            return None
        incident = (detail or {}).get("incident")
        if not isinstance(incident, dict):
            return None
        return {
            "alert_id": incident.get("alert_id"),
            "incident_state": incident.get("incident_state") or incident.get("state"),
            "severity": incident.get("severity"),
            "acknowledged": bool(incident.get("acknowledged")),
            "reopen_count": int(incident.get("reopen_count") or 0),
            "last_seen_at": incident.get("last_seen_at"),
            "recommendation": incident.get("recommendation"),
        }

    def _serialize_runtime_metadata(self, event: BRPEvent, response: BRPResponse) -> Dict[str, Any]:
        metadata = response.metadata if isinstance(getattr(response, "metadata", None), dict) else {}
        predictive = metadata.get("predictive_assessment") if isinstance(metadata.get("predictive_assessment"), dict) else {}
        multimodal = metadata.get("multimodal_assessment") if isinstance(metadata.get("multimodal_assessment"), dict) else {}
        controller = metadata.get("controller_assessment") if isinstance(metadata.get("controller_assessment"), dict) else {}
        payload = {
            "event_id": event.event_id,
            "decision": response.decision,
            "mode": response.mode,
            "severity": response.severity,
            "threat_score": response.threat_score,
            "confidence": response.confidence,
            "threat_tags": response.threat_tags,
            "summary": response.summary,
            "review_required": str(response.decision or "").upper() == BRPDecision.ELEVATE.value,
            "runtime": {
                "predictive_score_boost": round(float(predictive.get("score_boost") or 0.0), 4),
                "multimodal_score_boost": round(float(multimodal.get("score_boost") or 0.0), 4),
                "controller_rounds": int(controller.get("controller_rounds") or 0),
                "controller_score_delta": round(float(controller.get("score_delta") or 0.0), 4),
                "controller_confidence_delta": round(float(controller.get("confidence_delta") or 0.0), 4),
                "controller_terminal_state": controller.get("terminal_state"),
                "controller_reasoning_tags": controller.get("reasoning_tags", []),
            },
        }
        incident = self._read_incident_snapshot(event.event_id)
        if incident is not None:
            payload["incident"] = incident
        return payload
    
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
            response.event_id = response.event_id or event.event_id
            runtime_metadata = self._serialize_runtime_metadata(event, response)
            response.metadata = {
                **(response.metadata if isinstance(response.metadata, dict) else {}),
                "integrator_runtime": runtime_metadata.get("runtime", {}),
                "integrator_incident": runtime_metadata.get("incident"),
            }
            self._last_event_id = event.event_id
            self._recent_trade_events[self._trade_cache_key(context.market, context.action)] = runtime_metadata
            
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
                    "runtime": runtime_metadata.get("runtime", {}),
                    "incident_state": ((runtime_metadata.get("incident") or {}).get("incident_state")),
                },
                mode=self.mode.value,
                tags=context.tags or ["quantumarb", context.action.value],
            )
            self.bridge.ingest_observation(observation)
            
            # Log the evaluation
            self._log_evaluation(event, response, context, runtime_metadata)
            
            # Update statistics
            interpreted_decision = self._interpret_brp_decision(response.decision)
            if interpreted_decision == "block":
                self.stats["blocks"] += 1
                log.warning(f"BRP BLOCKED trade action: {context.action} for {context.market}. "
                          f"Reason: {response.summary}")
                return False, response
            elif interpreted_decision == "warn":
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
                decision=BRPDecision.ALLOW.value,
                threat_score=0.0,
                severity=BRPSeverity.INFO.value,
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
        tags: Optional[List[str]] = None,
        event_id: str = "",
    ) -> None:
        """
        Record the outcome of a trade action for BRP learning.
        
        Args:
            market: Trading market/pair
            action: Trade action that was performed
            success: Whether the action was successful
            outcome_data: Data about the outcome
            tags: Additional tags
            event_id: Original BRP event id, if known
        """
        try:
            cached_runtime = self._recent_trade_events.get(self._trade_cache_key(market, action), {})
            resolved_event_id = (
                str(event_id or "").strip()
                or str(cached_runtime.get("event_id") or "").strip()
                or str(self._last_event_id or "").strip()
                or str(uuid4())
            )
            observation = BRPObservation(
                source_agent=self.agent_id,
                event_id=resolved_event_id,
                action=action.value,
                outcome="success" if success else "failure",
                result_data={
                    "market": market,
                    "success": success,
                    "runtime": cached_runtime.get("runtime", {}),
                    "incident_state": ((cached_runtime.get("incident") or {}).get("incident_state")),
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
                    "event_id": resolved_event_id,
                    "market": market,
                    "action": action.value,
                    "success": success,
                    "outcome_data": outcome_data,
                    "runtime": cached_runtime.get("runtime", {}),
                    "incident": cached_runtime.get("incident"),
                    "tags": tags or [],
                }
                f.write(json.dumps(record) + "\n")
                
        except Exception as e:
            log.error(f"Failed to record trade outcome: {e}", exc_info=True)
    
    def _log_evaluation(
        self,
        event: BRPEvent,
        response: BRPResponse,
        context: TradeContext,
        runtime_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
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
                    "runtime": ((runtime_metadata or {}).get("runtime") or {}),
                    "incident": ((runtime_metadata or {}).get("incident")),
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
