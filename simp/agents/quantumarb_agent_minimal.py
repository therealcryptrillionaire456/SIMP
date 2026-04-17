#!/usr/bin/env python3.10
"""
QuantumArb Agent - Minimal Phase 4
Minimal working version for immediate operation.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("quantumarb_minimal")

class ArbType(str, Enum):
    """Types of arbitrage opportunities."""
    CROSS_VENUE = "cross_venue"
    STATISTICAL = "statistical"

class ArbDecision(str, Enum):
    """Arbitrage decision outcomes."""
    EXECUTE = "execute"
    REJECT_RISK = "reject_risk"
    REJECT_SLIPPAGE = "reject_slippage"

@dataclass
class ArbitrageSignal:
    """Signal for arbitrage opportunity."""
    signal_id: str
    arb_type: ArbType
    symbol_a: str
    symbol_b: str
    venue_a: str
    venue_b: str
    spread_pct: float
    expected_return_pct: float
    timestamp: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "ArbitrageSignal":
        """Create signal from SIMP intent."""
        return cls(
            signal_id=intent.get("signal_id", str(uuid.uuid4())),
            arb_type=ArbType(intent.get("arb_type", "cross_venue")),
            symbol_a=intent["symbol_a"],
            symbol_b=intent["symbol_b"],
            venue_a=intent["venue_a"],
            venue_b=intent["venue_b"],
            spread_pct=float(intent["spread_pct"]),
            expected_return_pct=float(intent.get("expected_return_pct", 0.0)),
            timestamp=intent.get("timestamp", datetime.utcnow().isoformat()),
            confidence=float(intent.get("confidence", 0.0)),
            metadata=intent.get("metadata", {})
        )

@dataclass
class ArbitrageOpportunity:
    """Evaluated arbitrage opportunity."""
    opportunity_id: str
    signal: ArbitrageSignal
    decision: ArbDecision
    decision_reason: str
    position_size_usd: float
    expected_pnl_usd: float
    max_slippage_pct: float
    risk_score: float
    timestamp: str
    
    def to_simp_intent(self, source_agent: str = "quantumarb_minimal") -> Dict[str, Any]:
        """Convert to SIMP intent format."""
        return {
            "intent_type": "arbitrage_execution",
            "source_agent": source_agent,
            "target_agent": "auto",
            "timestamp": self.timestamp,
            "payload": {
                "opportunity_id": self.opportunity_id,
                "signal": asdict(self.signal),
                "decision": self.decision.value,
                "decision_reason": self.decision_reason,
                "position_size_usd": self.position_size_usd,
                "expected_pnl_usd": self.expected_pnl_usd,
                "max_slippage_pct": self.max_slippage_pct,
                "risk_score": self.risk_score
            }
        }

class QuantumArbEngineMinimal:
    """Minimal arbitrage engine for Phase 4."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        logger.info(f"QuantumArbEngineMinimal initialized for Phase 4 microscopic trading")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration."""
        default_config = {
            "risk": {
                "max_position_size_usd": 0.10,  # $0.10 microscopic
                "max_daily_loss_usd": 1.00,     # $1.00 daily limit
                "min_spread_pct": 0.01,         # 0.01% minimum
                "max_slippage_pct": 0.05,       # 0.05% maximum
                "risk_score_threshold": 0.5     # 50% threshold for Gate 1 microscopic testing
            }
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    import copy
                    merged = copy.deepcopy(default_config)
                    self._deep_update(merged, user_config)
                    return merged
            except Exception as e:
                logger.error(f"Error loading config {config_path}: {e}")
        
        return default_config
    
    def _deep_update(self, target: Dict, source: Dict) -> None:
        """Deep update dictionary."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
    
    def evaluate(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate arbitrage opportunity."""
        logger.info(f"Evaluating arbitrage signal: {signal.signal_id}")
        
        # Check minimum spread threshold
        min_spread = self.config["risk"]["min_spread_pct"]
        if signal.spread_pct < min_spread:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                reason=f"Spread {signal.spread_pct:.4f}% below minimum {min_spread:.4f}%",
                risk_score=0.0
            )
        
        # Calculate position size (microscopic)
        max_position = self.config["risk"]["max_position_size_usd"]
        position_size = max_position  # Use max for now
        
        # Estimate slippage (simplified)
        slippage = 0.03  # Conservative 0.03% estimate
        max_slippage = self.config["risk"]["max_slippage_pct"]
        
        if slippage > max_slippage:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_SLIPPAGE,
                reason=f"Estimated slippage {slippage:.4f}% exceeds maximum {max_slippage:.4f}%",
                risk_score=0.0
            )
        
        # Calculate expected P&L (adjusted for slippage)
        expected_return = signal.expected_return_pct - slippage
        expected_pnl = position_size * expected_return / 100
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(signal, slippage)
        risk_threshold = self.config["risk"]["risk_score_threshold"]
        
        if risk_score < risk_threshold:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                reason=f"Risk score {risk_score:.2f} below threshold {risk_threshold:.2f}",
                risk_score=risk_score
            )
        
        # Create approved opportunity
        return ArbitrageOpportunity(
            opportunity_id=str(uuid.uuid4()),
            signal=signal,
            decision=ArbDecision.EXECUTE,
            decision_reason=f"Approved: spread={signal.spread_pct:.4f}%, risk={risk_score:.2f}",
            position_size_usd=position_size,
            expected_pnl_usd=expected_pnl,
            max_slippage_pct=slippage,
            risk_score=risk_score,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def _calculate_risk_score(self, signal: ArbitrageSignal, slippage: float) -> float:
        """Calculate risk score optimized for microscopic trading."""
        # For microscopic trading ($0.01-$0.10), we adjust scoring:
        # - Spreads are smaller but still meaningful
        # - Confidence is critical
        # - Slippage has less impact at small sizes
        
        # Normalize spread to 0.5% (more realistic for microscopic)
        spread_score = min(signal.spread_pct / 0.5, 1.0)
        
        # Confidence from signal (critical for microscopic)
        confidence_score = signal.confidence
        
        # Slippage penalty (less severe for microscopic)
        slippage_penalty = max(0, 1.0 - (slippage / 0.2))  # 0.2% threshold
        
        # Adjusted weights for microscopic trading:
        # - Spread: 40% (still important)
        # - Confidence: 40% (more important for small trades)
        # - Slippage: 20% (less impact at small sizes)
        risk_score = (
            spread_score * 0.4 +
            confidence_score * 0.4 +
            slippage_penalty * 0.2
        )
        
        return min(max(risk_score, 0.0), 1.0)
    
    def _create_rejected_opportunity(self, signal: ArbitrageSignal,
                                   decision: ArbDecision,
                                   reason: str,
                                   risk_score: float = 0.0) -> ArbitrageOpportunity:
        """Create rejected opportunity."""
        return ArbitrageOpportunity(
            opportunity_id=str(uuid.uuid4()),
            signal=signal,
            decision=decision,
            decision_reason=reason,
            position_size_usd=0.0,
            expected_pnl_usd=0.0,
            max_slippage_pct=0.0,
            risk_score=risk_score,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "status": "operational",
            "phase": 4,
            "trading_mode": "microscopic",
            "max_position_usd": self.config["risk"]["max_position_size_usd"],
            "min_spread_pct": self.config["risk"]["min_spread_pct"],
            "timestamp": datetime.utcnow().isoformat()
        }

class QuantumArbAgentMinimal:
    """Minimal Phase 4 QuantumArb agent."""
    
    def __init__(self, poll_interval: float = 2.0, config_path: Optional[str] = None):
        self.poll_interval = poll_interval
        self.config_path = config_path
        self.engine = QuantumArbEngineMinimal(config_path)
        
        # Agent directories
        self.base_dir = Path("data/quantumarb_minimal")
        self.inbox_dir = self.base_dir / "inbox"
        self.outbox_dir = self.base_dir / "outbox"
        self._ensure_dirs()
        
        logger.info(f"QuantumArbAgentMinimal initialized with poll interval {poll_interval}s")
    
    def _ensure_dirs(self):
        """Ensure agent directories exist."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
    
    async def run(self):
        """Main agent loop."""
        logger.info("Starting QuantumArbAgentMinimal...")
        
        try:
            while True:
                # Process inbox
                self._process_inbox()
                
                # Log status periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    self._log_status()
                
                await asyncio.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Agent stopped by user")
        except Exception as e:
            logger.error(f"Agent crashed: {e}")
            raise
    
    def _process_inbox(self):
        """Process incoming intents."""
        for intent_file in self.inbox_dir.glob("*.json"):
            try:
                with open(intent_file, 'r') as f:
                    intent = json.load(f)
                
                # Process based on intent type
                intent_type = intent.get("intent_type")
                
                if intent_type == "arbitrage_signal":
                    self._process_arbitrage_signal(intent)
                elif intent_type == "status_query":
                    self._process_status_query(intent)
                else:
                    logger.warning(f"Unknown intent type: {intent_type}")
                
                # Move to processed
                processed_dir = self.inbox_dir / "processed"
                processed_dir.mkdir(exist_ok=True)
                intent_file.rename(processed_dir / intent_file.name)
                
            except Exception as e:
                logger.error(f"Error processing {intent_file}: {e}")
                # Move to error directory
                error_dir = self.inbox_dir / "error"
                error_dir.mkdir(exist_ok=True)
                intent_file.rename(error_dir / intent_file.name)
    
    def _process_arbitrage_signal(self, intent: Dict[str, Any]):
        """Process arbitrage signal intent."""
        try:
            # Convert to signal
            signal = ArbitrageSignal.from_intent(intent.get("payload", {}))
            
            # Evaluate opportunity
            opportunity = self.engine.evaluate(signal)
            
            # Log decision
            self._log_decision_summary(signal, opportunity)
            
            # Write result
            result_file = self._write_result(signal, opportunity)
            logger.info(f"Processed signal {signal.signal_id}, result: {result_file}")
            
        except Exception as e:
            logger.error(f"Error processing arbitrage signal: {e}")
    
    def _process_status_query(self, intent: Dict[str, Any]):
        """Process status query intent."""
        query_type = intent.get("payload", {}).get("query_type", "metrics")
        
        if query_type == "metrics":
            response = self.engine.get_performance_metrics()
        elif query_type == "configuration":
            response = self.engine.config
        elif query_type == "health":
            response = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "phase": 4,
                "trading_mode": "microscopic"
            }
        else:
            response = {"error": f"Unknown query type: {query_type}"}
        
        # Write response
        query_id = intent.get("query_id", str(uuid.uuid4()))
        response_file = self.outbox_dir / f"status_response_{query_id}.json"
        with open(response_file, 'w') as f:
            json.dump(response, f, indent=2)
    
    def _log_decision_summary(self, signal: ArbitrageSignal, opportunity: ArbitrageOpportunity):
        """Log decision summary."""
        summary = {
            "signal_id": signal.signal_id,
            "spread_pct": signal.spread_pct,
            "decision": opportunity.decision.value,
            "reason": opportunity.decision_reason,
            "position_size_usd": opportunity.position_size_usd,
            "expected_pnl_usd": opportunity.expected_pnl_usd,
            "risk_score": opportunity.risk_score,
            "timestamp": opportunity.timestamp
        }
        
        logger.info(f"Decision: {summary}")
        
        # Save to log file
        log_file = self.base_dir / "decisions.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(summary) + "\n")
    
    def _write_result(self, signal: ArbitrageSignal, opportunity: ArbitrageOpportunity) -> Path:
        """Write processing result to outbox."""
        result = {
            "signal_id": signal.signal_id,
            "processing_time": datetime.utcnow().isoformat(),
            "opportunity": asdict(opportunity),
            "engine_state": self.engine.get_performance_metrics()
        }
        
        result_file = self.outbox_dir / f"result_{signal.signal_id}.json"
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result_file
    
    def _log_status(self):
        """Log status periodically."""
        metrics = self.engine.get_performance_metrics()
        logger.info(f"Status: Phase {metrics['phase']}, {metrics['trading_mode']} trading")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="QuantumArb Agent Minimal")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--poll-interval", type=float, default=2.0,
                       help="Poll interval in seconds")
    
    args = parser.parse_args()
    
    # Create and run agent
    agent = QuantumArbAgentMinimal(
        poll_interval=args.poll_interval,
        config_path=args.config
    )
    
    # Run agent
    asyncio.run(agent.run())

if __name__ == "__main__":
    main()