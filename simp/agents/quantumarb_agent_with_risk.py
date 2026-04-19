#!/usr/bin/env python3.10
"""
QuantumArb Agent with Risk Framework Integration

Enhanced QuantumArb agent that integrates:
1. BRP protection (Bill Russell Protocol)
2. Risk framework with position sizing and limits
3. Monitoring and alerting integration

This agent implements Phase 2 (risk framework) and Phase 3 (monitoring)
of the 7-phase live trading transition plan.
"""

import json
import time
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import uuid
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from enum import Enum

# Import BRP modules
try:
    from simp.security.brp_models import BRPEvent, BRPOutcome
    BRP_AVAILABLE = True
except ImportError:
    BRP_AVAILABLE = False
    logging.warning("BRP models not available - running without BRP")

# Import risk framework
try:
    from risk_framework_config import RiskFramework, RiskLevel, AssetClass
    RISK_FRAMEWORK_AVAILABLE = True
except ImportError:
    RISK_FRAMEWORK_AVAILABLE = False
    logging.warning("Risk framework not available - running without risk limits")

# Import monitoring system
try:
    from monitoring_alerting_system import TradeMonitor, AlertLevel
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    logging.warning("Monitoring system not available - running without monitoring")

# Configure logging
log = logging.getLogger("QuantumArbRisk")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
log.addHandler(handler)

# Also log to file
file_handler = logging.FileHandler('quantumarb_risk_agent.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
log.addHandler(file_handler)

class ArbType(Enum):
    """Types of arbitrage opportunities."""
    CROSS_EXCHANGE = "cross_exchange"
    STATISTICAL = "statistical"
    TRIANGULAR = "triangular"

class ArbDecision(Enum):
    """Arbitrage decision outcomes."""
    EXECUTE = "execute"
    NO_ARB = "no_arb"
    DRY_RUN = "dry_run"
    RISK_LIMIT = "risk_limit"
    BRP_BLOCKED = "brp_blocked"

@dataclass
class ArbitrageSignal:
    """Arbitrage signal from intent."""
    ticker: str
    exchange_a: str
    exchange_b: str
    spread_percent: float
    volume: float
    timestamp: datetime
    signal_id: str
    
    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "ArbitrageSignal":
        """Create ArbitrageSignal from SIMP intent."""
        return cls(
            ticker=intent.get("parameters", {}).get("symbol", "unknown"),
            exchange_a=intent.get("parameters", {}).get("exchange_a", "unknown"),
            exchange_b=intent.get("parameters", {}).get("exchange_b", "unknown"),
            spread_percent=float(intent.get("parameters", {}).get("spread_percent", 0.0)),
            volume=float(intent.get("parameters", {}).get("volume", 0.0)),
            timestamp=datetime.fromisoformat(intent.get("timestamp", datetime.now(timezone.utc).isoformat())),
            signal_id=intent.get("intent_id", str(uuid.uuid4()))
        )

@dataclass
class ArbitrageOpportunity:
    """Evaluated arbitrage opportunity."""
    signal: ArbitrageSignal
    decision: ArbDecision
    estimated_spread_bps: float
    estimated_profit_usd: float
    position_size_usd: float
    stop_loss_percent: float
    brp_allowed: bool
    brp_reason: str
    risk_allowed: bool
    risk_reason: str
    risk_position_size: float
    
    def to_simp_intent(self) -> Dict[str, Any]:
        """Convert to SIMP intent format."""
        return {
            "intent_type": "arbitrage_execution",
            "source_agent": "quantumarb_risk",
            "target_agent": "auto",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": str(uuid.uuid4()),
            "parameters": {
                "symbol": self.signal.ticker,
                "exchange_a": self.signal.exchange_a,
                "exchange_b": self.signal.exchange_b,
                "spread_bps": self.estimated_spread_bps,
                "estimated_profit_usd": self.estimated_profit_usd,
                "position_size_usd": self.position_size_usd,
                "stop_loss_percent": self.stop_loss_percent,
                "decision": self.decision.value,
                "brp_allowed": self.brp_allowed,
                "brp_reason": self.brp_reason,
                "risk_allowed": self.risk_allowed,
                "risk_reason": self.risk_reason,
                "risk_position_size": self.risk_position_size,
            }
        }

class QuantumArbEngineWithRisk:
    """QuantumArb engine with integrated risk framework."""
    
    def __init__(self, risk_config_file: str = "risk_config_conservative.json"):
        self.risk_framework = None
        self.monitor = None
        
        if RISK_FRAMEWORK_AVAILABLE:
            try:
                self.risk_framework = RiskFramework(risk_config_file)
                log.info(f"Risk framework loaded from {risk_config_file}")
                log.info(f"Risk level: {self.risk_framework.risk_params.risk_level}")
                log.info(f"Account size: ${self.risk_framework.risk_params.account_size_usd:.2f}")
                log.info(f"Max risk per trade: ${self.risk_framework.risk_params.max_risk_per_trade_usd:.2f}")
            except Exception as e:
                log.error(f"Failed to load risk framework: {e}")
                self.risk_framework = None
        
        if MONITORING_AVAILABLE:
            try:
                self.monitor = TradeMonitor()
                log.info("Monitoring system initialized")
            except Exception as e:
                log.error(f"Failed to initialize monitoring: {e}")
                self.monitor = None
    
    def evaluate(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate arbitrage opportunity with risk framework."""
        # Calculate estimated spread and profit
        estimated_spread_bps = signal.spread_percent * 100  # Convert % to bps
        estimated_profit_usd = signal.volume * signal.spread_percent / 100
        
        # Default values
        position_size_usd = signal.volume
        stop_loss_percent = 5.0  # Default 5% stop loss
        brp_allowed = True
        brp_reason = "BRP not available"
        risk_allowed = True
        risk_reason = "Risk framework not available"
        risk_position_size = position_size_usd
        
        # Check with BRP if available
        if BRP_AVAILABLE:
            brp_allowed, brp_reason = self._check_with_brp(signal, estimated_spread_bps)
        
        # Check with risk framework if available
        if self.risk_framework is not None:
            risk_allowed, risk_reason, risk_position_size = self._check_with_risk_framework(
                signal, estimated_spread_bps, stop_loss_percent
            )
        
        # Determine final decision
        if not brp_allowed:
            decision = ArbDecision.BRP_BLOCKED
        elif not risk_allowed:
            decision = ArbDecision.RISK_LIMIT
        elif estimated_spread_bps < 10:  # Minimum 10 bps spread
            decision = ArbDecision.NO_ARB
        else:
            decision = ArbDecision.DRY_RUN  # Sandbox mode for now
        
        # Create opportunity
        opportunity = ArbitrageOpportunity(
            signal=signal,
            decision=decision,
            estimated_spread_bps=estimated_spread_bps,
            estimated_profit_usd=estimated_profit_usd,
            position_size_usd=position_size_usd,
            stop_loss_percent=stop_loss_percent,
            brp_allowed=brp_allowed,
            brp_reason=brp_reason,
            risk_allowed=risk_allowed,
            risk_reason=risk_reason,
            risk_position_size=risk_position_size
        )
        
        # Record with monitor if available
        if self.monitor is not None:
            self._record_with_monitor(signal, opportunity)
        
        return opportunity
    
    def _check_with_brp(self, signal: ArbitrageSignal, spread_bps: float) -> Tuple[bool, str]:
        """Check arbitrage opportunity with BRP."""
        try:
            # Simulate BRP check (in real implementation, this would call BRP service)
            # For now, always allow in sandbox mode
            if spread_bps > 50:  # Very large spread might be suspicious
                return False, "Spread too large (possible data error)"
            return True, "BRP evaluation passed"
        except Exception as e:
            log.error(f"BRP check failed: {e}")
            return False, f"BRP check failed: {e}"
    
    def _check_with_risk_framework(self, signal: ArbitrageSignal, spread_bps: float, 
                                  stop_loss_percent: float) -> Tuple[bool, str, float]:
        """Check arbitrage opportunity with risk framework."""
        try:
            # Determine asset class
            asset_class = self._get_asset_class(signal.ticker)
            
            # Calculate position size based on risk framework
            position_size = self.risk_framework.calculate_position_size(
                signal.ticker, stop_loss_percent, asset_class
            )
            
            # Check if trade is allowed
            allowed, reason = self.risk_framework.check_trade_allowed(
                signal.ticker, position_size, asset_class
            )
            
            return allowed, reason, position_size
            
        except Exception as e:
            log.error(f"Risk framework check failed: {e}")
            return False, f"Risk framework check failed: {e}", 0.0
    
    def _get_asset_class(self, symbol: str) -> AssetClass:
        """Determine asset class from symbol."""
        symbol_lower = symbol.lower()
        if any(crypto in symbol_lower for crypto in ["btc", "eth", "sol", "ada", "dot", "matic", "avax", "link"]):
            return AssetClass.CRYPTO
        elif any(forex in symbol_lower for forex in ["eur", "gbp", "jpy", "aud", "cad", "chf"]):
            return AssetClass.FOREX
        elif any(stock in symbol_lower for stock in ["aapl", "googl", "msft", "amzn", "tsla", "spy", "qqq"]):
            return AssetClass.STOCKS
        else:
            return AssetClass.CRYPTO  # Default to crypto
    
    def _record_with_monitor(self, signal: ArbitrageSignal, opportunity: ArbitrageOpportunity):
        """Record trade evaluation with monitoring system."""
        try:
            self.monitor.record_intent({
                "intent_id": signal.signal_id,
                "timestamp": signal.timestamp.isoformat(),
                "symbol": signal.ticker,
                "exchange_a": signal.exchange_a,
                "exchange_b": signal.exchange_b,
                "spread_percent": signal.spread_percent,
                "volume": signal.volume
            })
            
            self.monitor.record_brp_decision({
                "intent_id": signal.signal_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": "ALLOW" if opportunity.brp_allowed else "BLOCK",
                "reason": opportunity.brp_reason,
                "threat_score": 0.0 if opportunity.brp_allowed else 1.0
            })
            
            self.monitor.record_risk_decision({
                "intent_id": signal.signal_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": "ALLOW" if opportunity.risk_allowed else "BLOCK",
                "reason": opportunity.risk_reason,
                "position_size": opportunity.risk_position_size,
                "allowed_position": opportunity.risk_position_size if opportunity.risk_allowed else 0.0
            })
            
        except Exception as e:
            log.error(f"Failed to record with monitor: {e}")

class QuantumArbAgentWithRisk:
    """QuantumArb agent with integrated risk framework and monitoring."""
    
    def __init__(self, poll_interval: float = 2.0, 
                 risk_config: str = "risk_config_conservative.json"):
        self.poll_interval = poll_interval
        self.engine = QuantumArbEngineWithRisk(risk_config)
        self._ensure_dirs()
        self._stop_event = False
        
        log.info("=" * 60)
        log.info("QUANTUMARB AGENT WITH RISK FRAMEWORK")
        log.info("=" * 60)
        log.info(f"Poll interval: {poll_interval}s")
        log.info(f"Risk config: {risk_config}")
        log.info("Inbox: data/inboxes/quantumarb_risk")
        log.info("Outbox: data/outboxes/quantumarb_risk")
        
        if BRP_AVAILABLE:
            log.info("✅ BRP protection: ENABLED")
        else:
            log.warning("⚠️ BRP protection: NOT AVAILABLE")
            
        if self.engine.risk_framework is not None:
            log.info("✅ Risk framework: ENABLED")
            params = self.engine.risk_framework.risk_params
            log.info(f"   Account size: ${params.account_size_usd:.2f}")
            log.info(f"   Max risk/trade: ${params.max_risk_per_trade_usd:.2f}")
            log.info(f"   Daily loss limit: ${params.daily_loss_limit_usd:.2f}")
        else:
            log.warning("⚠️ Risk framework: NOT AVAILABLE")
            
        if self.engine.monitor is not None:
            log.info("✅ Monitoring system: ENABLED")
        else:
            log.warning("⚠️ Monitoring system: NOT AVAILABLE")
        
        log.info("=" * 60)
    
    def _ensure_dirs(self):
        """Ensure necessary directories exist."""
        Path("data/inboxes/quantumarb_risk").mkdir(parents=True, exist_ok=True)
        Path("data/outboxes/quantumarb_risk").mkdir(parents=True, exist_ok=True)
        Path("data/inboxes/quantumarb_risk/processed").mkdir(parents=True, exist_ok=True)
        Path("data/inboxes/quantumarb_risk/errors").mkdir(parents=True, exist_ok=True)
        Path("logs/quantumarb_risk").mkdir(parents=True, exist_ok=True)
    
    def run(self):
        """Main agent loop."""
        log.info("Starting QuantumArb Agent with Risk Framework")
        try:
            while not self._stop_event:
                self._process_inbox()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            log.info("QuantumArb Agent stopped by user")
        except Exception as e:
            log.error(f"QuantumArb Agent crashed: {e}", exc_info=True)
    
    def _process_inbox(self):
        """Process all intents in the inbox."""
        inbox_dir = Path("data/inboxes/quantumarb_risk")
        if not inbox_dir.exists():
            return
        
        for filepath in inbox_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    intent = json.load(f)
                
                # Process
                signal = ArbitrageSignal.from_intent(intent)
                opportunity = self.engine.evaluate(signal)
                
                self._write_result(opportunity, intent)
                self._mark_processed(filepath, intent, opportunity)
                
                log.info(f"Processed {signal.ticker}: {opportunity.decision.value} "
                        f"(BRP: {opportunity.brp_allowed}, Risk: {opportunity.risk_allowed})")
                
            except Exception as e:
                log.error(f"Failed to process {filepath}: {e}", exc_info=True)
                # Move to error location
                error_dir = Path("data/inboxes/quantumarb_risk/errors")
                error_dir.mkdir(exist_ok=True)
                filepath.rename(error_dir / filepath.name)
    
    def _write_result(self, opportunity: ArbitrageOpportunity, original_intent: Dict[str, Any]):
        """Write arbitrage opportunity as SIMP intent."""
        outbox_dir = Path("data/outboxes/quantumarb_risk")
        outbox_dir.mkdir(exist_ok=True)
        
        intent = opportunity.to_simp_intent()
        intent["original_intent_id"] = original_intent.get("intent_id", "")
        
        filename = f"arb_risk_{intent['correlation_id']}.json"
        filepath = outbox_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(intent, f, indent=2)
        
        # Also log to monitor if available
        if self.engine.monitor is not None:
            try:
                self.engine.monitor.record_order_execution({
                    "intent_id": original_intent.get("intent_id", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "symbol": opportunity.signal.ticker,
                    "position_size": opportunity.risk_position_size,
                    "price": 0.0,  # Unknown in sandbox
                    "side": "buy",  # Default for arbitrage
                    "status": "filled" if opportunity.decision == ArbDecision.EXECUTE else "rejected",
                    "reason": f"BRP: {opportunity.brp_reason}, Risk: {opportunity.risk_reason}"
                })
            except Exception as e:
                log.error(f"Failed to record order execution: {e}")
    
    def _mark_processed(
        self,
        filepath: Path,
        intent: Dict[str, Any],
        opportunity: ArbitrageOpportunity
    ):
        """Mark intent as processed."""
        processed_dir = Path("data/inboxes/quantumarb_risk/processed")
        processed_dir.mkdir(exist_ok=True)
        
        # Add processing metadata
        metadata = {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "opportunity_decision": opportunity.decision.value,
            "brp_allowed": opportunity.brp_allowed,
            "brp_reason": opportunity.brp_reason,
            "risk_allowed": opportunity.risk_allowed,
            "risk_reason": opportunity.risk_reason,
            "risk_position_size": opportunity.risk_position_size,
            "estimated_profit_usd": opportunity.estimated_profit_usd,
            "estimated_spread_bps": opportunity.estimated_spread_bps,
        }
        
        intent["processing_metadata"] = metadata
        processed_path = processed_dir / filepath.name
        
        with open(processed_path, "w") as f:
            json.dump(intent, f, indent=2)
    
    def stop(self):
        """Stop the agent."""
        self._stop_event = True
        log.info("QuantumArb Agent stopping...")

def register_with_simp(agent_id: str = "quantumarb_risk", endpoint: str = "") -> bool:
    """Register this agent with the SIMP broker."""
    try:
        import requests
        
        broker_url = "http://127.0.0.1:5555"
        api_key = os.environ.get("SIMP_API_KEY", "781002cryptrillionaire456")
        
        registration_data = {
            "agent_id": agent_id,
            "agent_type": "arbitrage_risk",
            "endpoint": endpoint,
            "metadata": {
                "brp_enabled": BRP_AVAILABLE,
                "risk_framework_enabled": RISK_FRAMEWORK_AVAILABLE,
                "monitoring_enabled": MONITORING_AVAILABLE,
                "inbox": "data/inboxes/quantumarb_risk",
                "transport": "file"
            },
            "simp_versions": ["1.0"]
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }
        
        response = requests.post(
            f"{broker_url}/agents/register",
            json=registration_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            log.info(f"Successfully registered as {agent_id} with SIMP broker")
            return True
        else:
            log.error(f"Failed to register with SIMP broker: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log.error(f"Failed to register with SIMP broker: {e}")
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="QuantumArb Agent with Risk Framework")
    parser.add_argument("--poll-interval", type=float, default=2.0,
                       help="Poll interval in seconds (default: 2.0)")
    parser.add_argument("--risk-config", type=str, default="risk_config_conservative.json",
                       help="Risk configuration file (default: risk_config_conservative.json)")
    parser.add_argument("--agent-id", type=str, default="quantumarb_risk",
                       help="Agent ID for SIMP registration (default: quantumarb_risk)")
    parser.add_argument("--register", action="store_true",
                       help="Register with SIMP broker on startup")
    
    args = parser.parse_args()
    
    # Create and run agent
    agent = QuantumArbAgentWithRisk(
        poll_interval=args.poll_interval,
        risk_config=args.risk_config
    )
    
    # Register with SIMP broker if requested
    if args.register:
        register_with_simp(args.agent_id)
    
    # Run agent
    try:
        agent.run()
    except KeyboardInterrupt:
        log.info("Shutting down QuantumArb Agent with Risk Framework")
        agent.stop()

if __name__ == "__main__":
    main()