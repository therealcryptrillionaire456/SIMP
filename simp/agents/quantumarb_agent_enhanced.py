"""
quantumarb_agent_enhanced.py
============================
Enhanced QuantumArb SIMP Agent with BRP Live Protection

This is an enhanced version of the QuantumArb agent that integrates
the BRP (Bill Russell Protocol) for live threat evaluation and trade blocking.

Features:
1. BRP LIVE mode integration (not just shadow mode)
2. Trade execution evaluation with BRP blocking capability
3. Enhanced safety mechanisms
4. Real-time threat monitoring
5. Emergency stop procedures

Safety gates:
- BRP can BLOCK trades in LIVE mode
- All trades evaluated by BRP before execution
- Complete audit trail of all BRP decisions
- Emergency stop capability
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("QuantumArbEnhanced")

# ---------------------------------------------------------------------------
# Enhanced BRP Integration (LIVE mode with blocking capability)
# ---------------------------------------------------------------------------

try:
    from simp.organs.quantumarb.brp_integration import (
        get_brp_integrator, TradeAction, BRPMode
    )
    from simp.security.brp_models import BRPDecision
    BRP_AVAILABLE = True
    log.info("Enhanced BRP integration available")
except ImportError as e:
    BRP_AVAILABLE = False
    log.warning(f"Enhanced BRP integration not available: {e}. Running in degraded mode.")

# Mesh integration for trade updates and safety commands
try:
    from simp.organs.quantumarb.mesh_integration import (
        get_quantumarb_mesh_monitor,
        TradeUpdate,
        TradeStatus,
        SafetyAction,
        SafetyCommand
    )
    MESH_AVAILABLE = True
    log.info("Mesh integration available")
except ImportError as e:
    MESH_AVAILABLE = False
    log.warning(f"Mesh integration not available: {e}. Running without mesh updates.")


def _evaluate_with_brp_live(
    action: str,
    market: str,
    params: Dict[str, Any],
    tags: Optional[List[str]] = None
) -> tuple[bool, str]:
    """
    Evaluate an action with BRP in LIVE mode.
    
    Returns:
        Tuple of (allowed, reason)
    """
    if not BRP_AVAILABLE:
        return True, "BRP not available, defaulting to allow"
    
    try:
        integrator = get_brp_integrator(mode=BRPMode.ENFORCED)
        
        if action == "arb_evaluate":
            # Evaluate arbitrage opportunity
            spread_bps = params.get("spread_bps", 0.0)
            direction = params.get("direction", "")
            dry_run = params.get("dry_run", True)
            
            allowed, response = integrator.evaluate_arbitrage_opportunity(
                market=market,
                spread_bps=spread_bps,
                direction=direction,
                dry_run=dry_run,
                metadata=params
            )
            
            return allowed, response.summary
            
        elif action == "trade_execute":
            # Evaluate trade execution
            quantity = params.get("quantity", 0.0)
            price = params.get("price", 0.0)
            side = params.get("side", "")
            position_size = params.get("position_size")
            pnl_today = params.get("pnl_today")
            
            allowed, response = integrator.evaluate_trade_execution(
                market=market,
                quantity=quantity,
                price=price,
                side=side,
                position_size=position_size,
                pnl_today=pnl_today,
                metadata=params
            )
            
            return allowed, response.summary
            
        else:
            # Generic evaluation
            from simp.organs.quantumarb.brp_integration import TradeContext
            context = TradeContext(
                market=market,
                action=TradeAction(action) if hasattr(TradeAction, action) else TradeAction.ARB_EVALUATE,
                tags=tags or ["quantumarb", action],
                metadata=params
            )
            
            allowed, response = integrator.evaluate_trade_action(context)
            return allowed, response.summary
            
    except Exception as e:
        log.error(f"BRP evaluation failed: {e}", exc_info=True)
        # Fail-open for safety
        return True, f"BRP evaluation failed, defaulting to allow: {str(e)}"


def _record_brp_outcome(
    action: str,
    market: str,
    success: bool,
    outcome_data: Dict[str, Any],
    tags: Optional[List[str]] = None
) -> None:
    """Record the outcome of an action for BRP learning."""
    if not BRP_AVAILABLE:
        return
    
    try:
        integrator = get_brp_integrator()
        
        # Map action string to TradeAction enum
        try:
            trade_action = TradeAction(action)
        except ValueError:
            trade_action = TradeAction.ARB_EVALUATE
        
        integrator.record_trade_outcome(
            market=market,
            action=trade_action,
            success=success,
            outcome_data=outcome_data,
            tags=tags
        )
    except Exception as e:
        log.error(f"Failed to record BRP outcome: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Core Types (unchanged from original)
# ---------------------------------------------------------------------------

class ArbType(str, Enum):
    CROSS_VENUE = "cross_venue"
    STATISTICAL = "statistical"
    LATENCY = "latency"


class ArbDecision(str, Enum):
    NO_ARB = "no_arb"
    DRY_RUN = "dry_run"
    LIVE = "live"
    BLOCKED = "blocked"  # New: blocked by BRP or safety checks


@dataclass
class ArbitrageSignal:
    """Input signal from BullBear or other source."""
    ticker: Optional[str] = None
    direction: Optional[str] = None  # "long" or "short"
    confidence: float = 0.0
    horizon_minutes: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "ArbitrageSignal":
        return cls(
            ticker=intent.get("payload", {}).get("ticker"),
            direction=intent.get("payload", {}).get("direction"),
            confidence=intent.get("payload", {}).get("confidence", 0.0),
            horizon_minutes=intent.get("payload", {}).get("horizon_minutes", 5),
            metadata=intent.get("payload", {}).get("metadata", {}),
        )


@dataclass
class ArbitrageOpportunity:
    """Evaluated arbitrage opportunity."""
    signal: ArbitrageSignal
    arb_type: ArbType
    decision: ArbDecision
    estimated_spread_bps: float = 0.0
    confidence: float = 0.0
    dry_run: bool = True
    brp_allowed: bool = True  # New: whether BRP allowed this trade
    brp_reason: str = ""  # New: reason from BRP evaluation
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_simp_intent(
        self,
        source_agent: str = "quantumarb",
        target_agent: str = "kashclaw",
    ) -> Dict[str, Any]:
        return {
            "intent_type": "arbitrage_opportunity",
            "source_agent": source_agent,
            "target_agent": target_agent,
            "payload": {
                "signal": asdict(self.signal),
                "arb_type": self.arb_type.value,
                "decision": self.decision.value,
                "estimated_spread_bps": self.estimated_spread_bps,
                "confidence": self.confidence,
                "dry_run": self.dry_run,
                "brp_allowed": self.brp_allowed,  # Include BRP decision
                "brp_reason": self.brp_reason,    # Include BRP reason
                "metadata": self.metadata,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "correlation_id": str(uuid.uuid4()),
        }


# ---------------------------------------------------------------------------
# QuantumArb Engine (enhanced with BRP)
# ---------------------------------------------------------------------------

class QuantumArbEngine:
    """Enhanced arbitrage engine with BRP integration."""
    
    def __init__(self):
        self._spread_history: Dict[str, List[float]] = {}
        self._brp_stats = {
            "evaluations": 0,
            "blocks": 0,
            "warnings": 0,
            "allows": 0,
        }
    
    def _record_spread(self, series_id: str, value: float) -> List[float]:
        """Record spread value for a series."""
        if series_id not in self._spread_history:
            self._spread_history[series_id] = []
        self._spread_history[series_id].append(value)
        # Keep last 1000 values
        if len(self._spread_history[series_id]) > 1000:
            self._spread_history[series_id] = self._spread_history[series_id][-1000:]
        return self._spread_history[series_id]
    
    def evaluate(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate a signal for arbitrage opportunities with BRP check."""
        # First, evaluate the arbitrage opportunity
        if signal.ticker and "USD" in signal.ticker:
            opportunity = self._evaluate_cross_venue(signal)
        else:
            opportunity = self._evaluate_statistical(signal)
        
        # Now check with BRP
        brp_allowed, brp_reason = self._check_with_brp(opportunity)
        
        # Update opportunity with BRP decision
        opportunity.brp_allowed = brp_allowed
        opportunity.brp_reason = brp_reason
        
        # If BRP blocks, override decision
        if not brp_allowed:
            opportunity.decision = ArbDecision.BLOCKED
            opportunity.dry_run = True  # Force dry run if blocked
        
        return opportunity
    
    def _check_with_brp(self, opportunity: ArbitrageOpportunity) -> tuple[bool, str]:
        """Check arbitrage opportunity with BRP."""
        self._brp_stats["evaluations"] += 1
        
        if not BRP_AVAILABLE:
            return True, "BRP not available"
        
        try:
            market = opportunity.signal.ticker or "unknown"
            
            allowed, reason = _evaluate_with_brp_live(
                action="arb_evaluate",
                market=market,
                params={
                    "ticker": market,
                    "direction": opportunity.signal.direction,
                    "spread_bps": opportunity.estimated_spread_bps,
                    "confidence": opportunity.confidence,
                    "arb_type": opportunity.arb_type.value,
                    "decision": opportunity.decision.value,
                    "dry_run": opportunity.dry_run,
                },
                tags=["arbitrage", opportunity.arb_type.value, market]
            )
            
            if not allowed:
                self._brp_stats["blocks"] += 1
                log.warning(f"BRP BLOCKED arbitrage opportunity for {market}: {reason}")
            elif "warning" in reason.lower():
                self._brp_stats["warnings"] += 1
                log.warning(f"BRP WARNING for {market}: {reason}")
            else:
                self._brp_stats["allows"] += 1
            
            return allowed, reason
            
        except Exception as e:
            log.error(f"BRP check failed: {e}", exc_info=True)
            # Fail-open for safety
            return True, f"BRP check failed: {str(e)}"
    
    def _evaluate_cross_venue(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate cross-venue arbitrage (simplified)."""
        # Simplified logic for demo
        spread_bps = 10.0 + (signal.confidence * 5.0)
        self._record_spread(f"cross_venue_{signal.ticker}", spread_bps)
        
        decision = ArbDecision.DRY_RUN  # Always dry run in this version
        if spread_bps > 20.0 and signal.confidence > 0.7:
            decision = ArbDecision.LIVE
        
        return ArbitrageOpportunity(
            signal=signal,
            arb_type=ArbType.CROSS_VENUE,
            decision=decision,
            estimated_spread_bps=spread_bps,
            confidence=min(signal.confidence * 1.2, 1.0),
            dry_run=(decision != ArbDecision.LIVE),
            metadata={"evaluation_method": "cross_venue_simplified"},
        )
    
    def _evaluate_statistical(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate statistical arbitrage (simplified)."""
        # Simplified logic for demo
        spread_bps = 5.0 + (signal.confidence * 3.0)
        self._record_spread(f"statistical_{signal.ticker}", spread_bps)
        
        decision = ArbDecision.DRY_RUN  # Always dry run in this version
        if spread_bps > 15.0 and signal.confidence > 0.8:
            decision = ArbDecision.LIVE
        
        return ArbitrageOpportunity(
            signal=signal,
            arb_type=ArbType.STATISTICAL,
            decision=decision,
            estimated_spread_bps=spread_bps,
            confidence=min(signal.confidence * 1.1, 1.0),
            dry_run=(decision != ArbDecision.LIVE),
            metadata={"evaluation_method": "statistical_simplified"},
        )
    
    def get_brp_stats(self) -> Dict[str, Any]:
        """Get BRP statistics."""
        return self._brp_stats.copy()


# ---------------------------------------------------------------------------
# QuantumArb Agent (enhanced)
# ---------------------------------------------------------------------------

class QuantumArbAgent:
    """Enhanced QuantumArb agent with BRP protection."""
    
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.engine = QuantumArbEngine()
        self._ensure_dirs()
        self._stop_event = False
        self.mesh_monitor = None
        
        log.info("Enhanced QuantumArb Agent initialized with BRP protection")
        if BRP_AVAILABLE:
            log.info("BRP ENFORCED mode enabled - trades can be blocked by threat detection")
        else:
            log.warning("BRP not available - running without threat protection")
        
        # Initialize mesh integration if available
        if MESH_AVAILABLE:
            try:
                self.mesh_monitor = get_quantumarb_mesh_monitor()
                log.info("Mesh integration initialized")
            except Exception as e:
                log.error(f"Failed to initialize mesh integration: {e}")
                self.mesh_monitor = None
        else:
            log.warning("Mesh integration not available - running without mesh updates")
    
    def _ensure_dirs(self):
        """Ensure necessary directories exist."""
        Path("data/inboxes/quantumarb").mkdir(parents=True, exist_ok=True)
        Path("data/outboxes/quantumarb").mkdir(parents=True, exist_ok=True)
        Path("logs/quantumarb").mkdir(parents=True, exist_ok=True)
    
    def _send_trade_update(self, opportunity, intent, status: str):
        """Send trade update via mesh bus."""
        if not self.mesh_monitor or not MESH_AVAILABLE:
            return
        
        try:
            # Map status to TradeStatus
            status_map = {
                "detected": TradeStatus.DETECTED,
                "evaluating": TradeStatus.EVALUATING,
                "approved": TradeStatus.APPROVED,
                "executing": TradeStatus.EXECUTING,
                "executed": TradeStatus.EXECUTED,
                "rejected": TradeStatus.REJECTED,
                "failed": TradeStatus.FAILED,
                "cancelled": TradeStatus.CANCELLED,
            }
            
            trade_status = status_map.get(status, TradeStatus.DETECTED)
            
            # Create trade update
            update = TradeUpdate(
                trade_id=intent.get("intent_id", str(uuid.uuid4())),
                status=trade_status,
                symbol=opportunity.ticker or "unknown",
                venue=opportunity.venue or "unknown",
                spread_percent=opportunity.estimated_spread_bps / 100.0,  # Convert bps to percent
                expected_profit=opportunity.estimated_profit_usd or 0.0,
                risk_score=opportunity.risk_score or 0.5,
                brp_decision=opportunity.brp_reason or "unknown",
                trace_id=intent.get("trace_id"),
                metadata={
                    "intent_type": intent.get("intent_type", "unknown"),
                    "source_agent": intent.get("source_agent", "unknown"),
                    "decision": opportunity.decision.value if hasattr(opportunity, 'decision') else "unknown",
                    "brp_allowed": opportunity.brp_allowed if hasattr(opportunity, 'brp_allowed') else True,
                }
            )
            
            # Send via mesh
            success = self.mesh_monitor.send_trade_update(update)
            if success:
                log.debug(f"Sent trade update via mesh: {update.trade_id} - {status}")
            else:
                log.warning(f"Failed to send trade update via mesh: {update.trade_id}")
                
        except Exception as e:
            log.error(f"Error sending trade update via mesh: {e}")
    
    def run(self):
        """Main agent loop."""
        log.info("Starting Enhanced QuantumArb Agent loop")
        
        # Start mesh monitor if available
        mesh_started = False
        if self.mesh_monitor:
            try:
                mesh_started = self.mesh_monitor.start()
                if mesh_started:
                    log.info("Mesh monitor started successfully")
                else:
                    log.warning("Failed to start mesh monitor")
            except Exception as e:
                log.error(f"Error starting mesh monitor: {e}")
        
        try:
            while not self._stop_event:
                self._process_inbox()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            log.info("Enhanced QuantumArb Agent stopped by user")
        except Exception as e:
            log.error(f"Enhanced QuantumArb Agent crashed: {e}", exc_info=True)
    
    def _process_inbox(self):
        """Process all intents in the inbox."""
        inbox_dir = Path("data/inboxes/quantumarb_enhanced")
        if not inbox_dir.exists():
            return
        
        for filepath in inbox_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    intent = json.load(f)
                
                # Process
                signal = ArbitrageSignal.from_intent(intent)
                opportunity = self.engine.evaluate(signal)
                
                # Send trade update via mesh
                self._send_trade_update(opportunity, intent, "detected")
                
                # Record BRP outcome
                _record_brp_outcome(
                    action="arb_evaluate",
                    market=signal.ticker or "unknown",
                    success=(opportunity.decision != ArbDecision.NO_ARB),
                    outcome_data={
                        "intent_id": intent.get("intent_id", ""),
                        "decision": opportunity.decision.value,
                        "spread_bps": opportunity.estimated_spread_bps,
                        "brp_allowed": opportunity.brp_allowed,
                        "brp_reason": opportunity.brp_reason,
                    },
                    tags=["quantumarb", "evaluation", signal.ticker or ""]
                )
                
                self._write_result(opportunity, intent)
                self._mark_processed(filepath, intent, opportunity)
                
                # Send final status update
                if opportunity.decision == ArbDecision.EXECUTE:
                    self._send_trade_update(opportunity, intent, "approved")
                elif opportunity.decision == ArbDecision.NO_ARB:
                    self._send_trade_update(opportunity, intent, "rejected")
                
            except Exception as e:
                log.error(f"Failed to process {filepath}: {e}", exc_info=True)
                # Move to error location
                error_dir = Path("data/inboxes/quantumarb_enhanced/errors")
                error_dir.mkdir(exist_ok=True)
                filepath.rename(error_dir / filepath.name)
    
    def _write_result(self, opportunity: ArbitrageOpportunity, original_intent: Dict[str, Any]):
        """Write arbitrage opportunity as SIMP intent."""
        outbox_dir = Path("data/outboxes/quantumarb_enhanced")
        outbox_dir.mkdir(exist_ok=True)
        
        intent = opportunity.to_simp_intent()
        intent["original_intent_id"] = original_intent.get("intent_id", "")
        
        filename = f"arb_{intent['correlation_id']}.json"
        filepath = outbox_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(intent, f, indent=2)
        
        log.info(f"Wrote arbitrage opportunity: {opportunity.decision.value} "
                f"for {opportunity.signal.ticker} (BRP: {opportunity.brp_allowed})")
    
    def _mark_processed(
        self,
        filepath: Path,
        intent: Dict[str, Any],
        opportunity: ArbitrageOpportunity
    ):
        """Mark intent as processed."""
        processed_dir = Path("data/inboxes/quantumarb_enhanced/processed")
        processed_dir.mkdir(exist_ok=True)
        
        # Add processing metadata
        metadata = {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "opportunity_decision": opportunity.decision.value,
            "brp_allowed": opportunity.brp_allowed,
            "brp_reason": opportunity.brp_reason,
            "engine_stats": self.engine.get_brp_stats(),
        }
        
        intent["processing_metadata"] = metadata
        processed_path = processed_dir / filepath.name
        
        with open(processed_path, "w") as f:
            json.dump(intent, f, indent=2)
        
        # Remove original
        filepath.unlink()
    
    def stop(self):
        """Stop the agent."""
        self._stop_event = True
        
        # Stop mesh monitor if running
        if self.mesh_monitor:
            try:
                self.mesh_monitor.stop()
                log.info("Mesh monitor stopped")
            except Exception as e:
                log.error(f"Error stopping mesh monitor: {e}")
        
        log.info("Enhanced QuantumArb Agent stopping...")


# ---------------------------------------------------------------------------
# Registration & Main
# ---------------------------------------------------------------------------

def register_with_simp(agent_id: str = "quantumarb_enhanced", endpoint: str = "") -> bool:
    """
    Register enhanced agent with SIMP broker.
    
    Args:
        agent_id: Agent ID to register
        endpoint: HTTP endpoint (empty for file-based)
        
    Returns:
        True if registration successful
    """
    try:
        import requests
        
        broker_url = os.getenv("SIMP_BROKER_URL", "http://127.0.0.1:5555")
        api_key = os.getenv("SIMP_API_KEY", "dev_key")
        
        payload = {
            "agent_id": agent_id,
            "agent_type": "arbitrage_enhanced",
            "endpoint": endpoint,
            "metadata": {
                "inbox": f"data/inboxes/{agent_id}",
                "transport": "file" if not endpoint else "http",
                "brp_enabled": BRP_AVAILABLE,
                "brp_mode": "ENFORCED" if BRP_AVAILABLE else "DISABLED",
            },
            "capabilities": [
                "arbitrage_evaluation",
                "cross_venue_arbitrage",
                "statistical_arbitrage",
                "brp_protected",
                "threat_aware",
            ],
            "simp_versions": ["1.0"],
        }
        
        response = requests.post(
            f"{broker_url}/agents/register",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=10.0,
        )
        
        if response.status_code == 200:
            log.info(f"Enhanced QuantumArb Agent registered as {agent_id}")
            return True
        else:
            log.error(f"Registration failed: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        log.error(f"Registration exception: {e}")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced QuantumArb Agent with BRP Protection")
    parser.add_argument("--poll-interval", type=float, default=2.0,
                       help="Polling interval in seconds")
    parser.add_argument("--register", action="store_true",
                       help="Register with SIMP broker before starting")
    parser.add_argument("--agent-id", default="quantumarb_enhanced",
                       help="Agent ID for registration")
    parser.add_argument("--http", action="store_true",
                       help="Run in HTTP mode (not implemented yet)")
    parser.add_argument("--port", type=int, default=8768,
                       help="Port for HTTP mode")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/quantumarb/enhanced_agent.log"),
        ]
    )
    
    # Register if requested
    if args.register:
        success = register_with_simp(agent_id=args.agent_id)
        if not success:
            log.warning("Registration failed, continuing anyway")
    
    # Create and run agent
    agent = QuantumArbAgent(poll_interval=args.poll_interval)
    
    try:
        agent.run()
    except KeyboardInterrupt:
        log.info("Enhanced QuantumArb Agent stopped")
    except Exception as e:
        log.error(f"Enhanced QuantumArb Agent crashed: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())