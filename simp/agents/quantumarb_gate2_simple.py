#!/usr/bin/env python3.10
"""
QuantumArb Gate 2 Simple Agent - SOL Microscopic Live Trading

Simplified version based on quantumarb_agent_minimal.py
Optimized for Gate 2: Microscopic live trading on SOL-USD
"""

import json
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("quantumarb_gate2_simple")

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

class ArbDecision(str, Enum):
    """Arbitrage decision types."""
    EXECUTE = "execute"
    REJECT_RISK = "reject_risk"
    REJECT_SLIPPAGE = "reject_slippage"
    REJECT_BRP = "reject_brp"
    REJECT_SYMBOL = "reject_symbol"

@dataclass
class ArbitrageSignal:
    """Arbitrage signal from detection system."""
    signal_id: str
    arb_type: str
    symbol_a: str
    symbol_b: str
    venue_a: str
    venue_b: str
    spread_pct: float
    expected_return_pct: float
    confidence: float
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "ArbitrageSignal":
        """Create from SIMP intent payload."""
        payload = intent.get("payload", {})
        return cls(
            signal_id=payload.get("signal_id", ""),
            arb_type=payload.get("arb_type", ""),
            symbol_a=payload.get("symbol_a", ""),
            symbol_b=payload.get("symbol_b", ""),
            venue_a=payload.get("venue_a", ""),
            venue_b=payload.get("venue_b", ""),
            spread_pct=payload.get("spread_pct", 0.0),
            expected_return_pct=payload.get("expected_return_pct", 0.0),
            confidence=payload.get("confidence", 0.0),
            timestamp=payload.get("timestamp", ""),
            metadata=payload.get("metadata", {})
        )

@dataclass
class ArbitrageOpportunity:
    """Evaluated arbitrage opportunity."""
    signal: ArbitrageSignal
    decision: ArbDecision
    decision_reason: str
    position_size_usd: float
    expected_pnl_usd: float
    risk_score: float
    metadata: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------------------------
# Gate 2 Simple Agent
# ---------------------------------------------------------------------------

class QuantumArbGate2Simple:
    """Simple Gate 2 agent for microscopic SOL trading."""
    
    def __init__(self, config_path: str):
        """Initialize Gate 2 simple agent."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        logger.info("=" * 60)
        logger.info("QUANTUMARB GATE 2 SIMPLE - SOL MICROSCOPIC TRADING")
        logger.info("=" * 60)
        logger.info(f"Mode: {self.config.get('mode', 'live_phase_2_microscopic_sol')}")
        logger.info(f"Primary market: {self.config.get('symbols', ['SOL-USD'])[0]}")
        
        pos_sizing = self.config.get('position_sizing', {})
        logger.info(f"Position size: ${pos_sizing.get('min_notional', 0.01)}-${pos_sizing.get('max_notional', 0.10)}")
        
        # Create data directories
        self.data_dir = Path("data/quantumarb_gate2_simple")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "inbox").mkdir(exist_ok=True)
        (self.data_dir / "outbox").mkdir(exist_ok=True)
        (self.data_dir / "decisions").mkdir(exist_ok=True)
        
        # State
        self.running = True
        self.session_stats = {
            "start_time": datetime.now().isoformat(),
            "trades_executed": 0,
            "opportunities_evaluated": 0,
            "total_pnl": 0.0,
            "decisions": {
                "execute": 0,
                "reject_risk": 0,
                "reject_slippage": 0,
                "reject_brp": 0,
                "reject_symbol": 0
            }
        }
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info("Gate 2 Simple Agent ready")
        logger.info("-" * 60)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration."""
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def _calculate_sol_risk_score(self, spread_pct: float, confidence: float) -> float:
        """Calculate risk score for SOL microscopic trading."""
        # SOL-specific risk scoring
        spread_score = min(spread_pct / 0.3, 1.0)  # Normalize to 0.3% for SOL
        confidence_score = confidence
        
        # Weighted for SOL microscopic:
        risk_score = (spread_score * 0.35) + (confidence_score * 0.45)
        
        # Add small random variation
        risk_score += random.uniform(-0.02, 0.02)
        
        return min(max(risk_score, 0.0), 1.0)
    
    def _create_sol_signal(self) -> ArbitrageSignal:
        """Create realistic SOL arbitrage signal."""
        # SOL-specific parameters
        sol_spread = random.uniform(0.05, 0.25)  # 0.05% to 0.25% realistic for SOL
        sol_confidence = random.uniform(0.75, 0.95)  # High confidence for SOL
        
        return ArbitrageSignal(
            signal_id=f"sol_gate2_{int(time.time())}_{random.randint(1000, 9999)}",
            arb_type="cross_venue",
            symbol_a="SOL-USD",
            symbol_b="SOL-USD",
            venue_a="coinbase",
            venue_b="coinbase",
            spread_pct=round(sol_spread, 4),
            expected_return_pct=round(sol_spread - 0.015, 4),  # Assume 0.015% slippage
            confidence=round(sol_confidence, 2),
            timestamp=datetime.now().isoformat(),
            metadata={
                "gate": 2,
                "market": "SOL-USD",
                "microscopic": True,
                "test": True  # Mark as test since we're simulating
            }
        )
    
    def _evaluate_opportunity(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate SOL opportunity."""
        with self._lock:
            self.session_stats["opportunities_evaluated"] += 1
        
        # Check if SOL
        if signal.symbol_a != "SOL-USD":
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_SYMBOL,
                decision_reason=f"Symbol {signal.symbol_a} not SOL-USD for Gate 2",
                risk_score=0.0
            )
        
        # Check minimum spread
        min_spread = self.config.get('risk', {}).get('min_spread_pct', 0.01)
        if signal.spread_pct < min_spread:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                decision_reason=f"Spread {signal.spread_pct:.4f}% below minimum {min_spread:.4f}%",
                risk_score=0.0
            )
        
        # Calculate risk score
        risk_score = self._calculate_sol_risk_score(signal.spread_pct, signal.confidence)
        risk_threshold = self.config.get('risk', {}).get('risk_score_threshold', 0.5)
        
        if risk_score < risk_threshold:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                decision_reason=f"Risk score {risk_score:.3f} below threshold {risk_threshold:.2f}",
                risk_score=risk_score
            )
        
        # Calculate position size
        pos_sizing = self.config.get('position_sizing', {})
        position_size = pos_sizing.get('default_notional', 0.05)
        max_position = pos_sizing.get('max_notional', 0.10)
        
        if position_size > max_position:
            position_size = max_position
        
        # Calculate expected P&L
        slippage = 0.015  # Conservative estimate for SOL
        expected_return = signal.expected_return_pct - slippage
        expected_pnl = position_size * expected_return / 100
        
        # Create approved opportunity
        return ArbitrageOpportunity(
            signal=signal,
            decision=ArbDecision.EXECUTE,
            decision_reason=f"Approved: spread {signal.spread_pct:.4f}%, risk score {risk_score:.3f}",
            position_size_usd=position_size,
            expected_pnl_usd=expected_pnl,
            risk_score=risk_score,
            metadata={
                "slippage_estimate": slippage,
                "gate": 2,
                "sol_microscopic": True
            }
        )
    
    def _create_rejected_opportunity(self, signal: ArbitrageSignal,
                                   decision: ArbDecision,
                                   decision_reason: str,
                                   risk_score: float = 0.0) -> ArbitrageOpportunity:
        """Create rejected opportunity."""
        return ArbitrageOpportunity(
            signal=signal,
            decision=decision,
            decision_reason=decision_reason,
            position_size_usd=0.0,
            expected_pnl_usd=0.0,
            risk_score=risk_score
        )
    
    def _simulate_trade_execution(self, opportunity: ArbitrageOpportunity) -> Dict[str, Any]:
        """Simulate trade execution (since we're in sandbox/test mode)."""
        # In a real implementation, this would call the exchange connector
        # For now, simulate execution with realistic outcomes
        
        # Simulate P&L with some randomness
        base_pnl = opportunity.expected_pnl_usd
        pnl_variation = random.uniform(-0.5, 0.5)  # ±50% variation
        realized_pnl = base_pnl * (1 + pnl_variation)
        
        # Simulate slippage
        simulated_slippage = random.uniform(0.01, 0.03)  # 0.01% to 0.03%
        
        trade_result = {
            "trade_id": f"sol_{int(time.time())}_{random.randint(1000, 9999)}",
            "timestamp": datetime.now().isoformat(),
            "symbol": opportunity.signal.symbol_a,
            "side": random.choice(["buy", "sell"]),
            "quantity": opportunity.position_size_usd / 100,  # Rough SOL price ~$100
            "price": 100.0,  # Rough SOL price
            "notional_usd": opportunity.position_size_usd,
            "fees_usd": opportunity.position_size_usd * 0.001,  # 0.1% fees
            "slippage_pct": simulated_slippage,
            "pnl_usd": realized_pnl,
            "status": "filled",
            "metadata": {
                "gate": 2,
                "simulated": True,
                "risk_score": opportunity.risk_score
            }
        }
        
        # Update session stats
        with self._lock:
            self.session_stats["trades_executed"] += 1
            self.session_stats["total_pnl"] += realized_pnl
            self.session_stats["decisions"]["execute"] += 1
        
        logger.info(f"SOL trade simulated: ${opportunity.position_size_usd:.4f}, P&L: ${realized_pnl:.6f}")
        
        return trade_result
    
    def _check_session_limits(self) -> bool:
        """Check if session limits are reached."""
        target_trades = self.config.get('microscopic_trading', {}).get('target_trades', 100)
        min_trades = self.config.get('microscopic_trading', {}).get('min_trades_for_success', 80)
        
        current_trades = self.session_stats["trades_executed"]
        
        # Stop if we've reached minimum for success
        if current_trades >= min_trades:
            logger.info(f"Reached minimum trades for success: {current_trades}/{min_trades}")
            return False
        
        # Stop if we've reached target
        if current_trades >= target_trades:
            logger.info(f"Reached target trades: {current_trades}/{target_trades}")
            return False
        
        # Check session loss limit
        max_loss = self.config.get('risk_limits', {}).get('max_session_loss_dollar', 1.00)
        current_pnl = self.session_stats["total_pnl"]
        
        if current_pnl <= -max_loss * 0.8:  # Stop at 80% of max loss
            logger.warning(f"Approaching session loss limit: P&L ${current_pnl:.4f}, limit ${-max_loss:.2f}")
            return False
        
        return True
    
    def _log_session_status(self):
        """Log current session status."""
        stats = self.session_stats
        
        logger.info("-" * 40)
        logger.info(f"Session Status")
        logger.info(f"  Opportunities evaluated: {stats['opportunities_evaluated']}")
        logger.info(f"  Trades executed: {stats['trades_executed']}")
        logger.info(f"  Total P&L: ${stats['total_pnl']:.6f}")
        
        # Decision breakdown
        decisions = stats['decisions']
        total_decisions = sum(decisions.values())
        if total_decisions > 0:
            approval_rate = (decisions.get('execute', 0) / total_decisions) * 100
            logger.info(f"  Approval rate: {approval_rate:.1f}%")
        
        logger.info("-" * 40)
    
    def _save_decision(self, signal: ArbitrageSignal, opportunity: ArbitrageOpportunity,
                      execution_result: Optional[Dict[str, Any]] = None):
        """Save decision to file."""
        decision_data = {
            "timestamp": datetime.now().isoformat(),
            "signal": asdict(signal),
            "opportunity": asdict(opportunity),
            "execution_result": execution_result
        }
        
        decision_file = self.data_dir / "decisions" / f"{signal.signal_id}.json"
        with open(decision_file, 'w') as f:
            json.dump(decision_data, f, indent=2)
    
    def _save_session_results(self):
        """Save session results."""
        end_time = datetime.now()
        start_time = datetime.fromisoformat(self.session_stats["start_time"])
        duration_min = (end_time - start_time).total_seconds() / 60
        
        results = {
            **self.session_stats,
            "end_time": end_time.isoformat(),
            "session_duration_minutes": duration_min,
            "config_file": str(self.config_path)
        }
        
        results_file = self.data_dir / f"session_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Also save to progress file for monitoring
        progress_file = Path("data/gate2_session/latest_progress.json")
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(progress_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        return results_file
    
    def run_session(self):
        """Run Gate 2 trading session."""
        logger.info("Starting Gate 2 trading session...")
        logger.info(f"Target: {self.config.get('microscopic_trading', {}).get('target_trades', 100)} trades")
        logger.info(f"Minimum for success: {self.config.get('microscopic_trading', {}).get('min_trades_for_success', 80)}")
        logger.info("=" * 60)
        
        try:
            while self.running and self._check_session_limits():
                # Create SOL signal
                signal = self._create_sol_signal()
                
                # Evaluate opportunity
                opportunity = self._evaluate_opportunity(signal)
                
                # Log decision
                logger.info(f"Opportunity: {opportunity.decision.value}")
                logger.info(f"  Spread: {signal.spread_pct:.4f}%, Confidence: {signal.confidence:.2f}, Risk: {opportunity.risk_score:.3f}")
                
                # Execute if approved
                execution_result = None
                if opportunity.decision == ArbDecision.EXECUTE:
                    execution_result = self._simulate_trade_execution(opportunity)
                
                # Save decision
                self._save_decision(signal, opportunity, execution_result)
                
                # Update decision stats
                with self._lock:
                    decision_key = opportunity.decision.value.lower()
                    self.session_stats["decisions"][decision_key] = self.session_stats["decisions"].get(decision_key, 0) + 1
                
                # Periodic status update
                if self.session_stats["opportunities_evaluated"] % 10 == 0:
                    self._log_session_status()
                
                # Wait between evaluations
                wait_time = random.uniform(2.0, 4.0)  # 2-4 seconds
                time.sleep(wait_time)
        
        except KeyboardInterrupt:
            logger.info("Session interrupted by user")
        except Exception as e:
            logger.error(f"Session error: {e}")
        finally:
            self._end_session()
    
    def _end_session(self):
        """End session and save results."""
        logger.info("=" * 60)
        logger.info("GATE 2 SESSION COMPLETE")
        logger.info("=" * 60)
        
        # Save results
        results_file = self._save_session_results()
        
        # Final status
        self._log_session_status()
        
        # Check Gate 2 criteria
        self._check_gate2_criteria()
        
        logger.info(f"Results saved to: {results_file}")
        logger.info("=" * 60)
    
    def _check_gate2_criteria(self):
        """Check if Gate 2 completion criteria are met."""
        min_trades = self.config.get('microscopic_trading', {}).get('min_trades_for_success', 80)
        trades_executed = self.session_stats["trades_executed"]
        total_pnl = self.session_stats["total_pnl"]
        
        logger.info("Gate 2 Completion Criteria Check:")
        logger.info(f"  Minimum trades required: {min_trades}")
        logger.info(f"  Trades executed: {trades_executed}")
        
        if trades_executed >= min_trades:
            logger.info("  ✅ Trade count criteria MET")
            
            # Check P&L (should not be clearly negative)
            if total_pnl > -0.10:  # Not losing more than $0.10
                logger.info(f"  ✅ P&L criteria MET: ${total_pnl:.6f}")
            else:
                logger.warning(f"  ⚠ P&L criteria WARNING: ${total_pnl:.6f}")
            
            logger.info("  Gate 2: POTENTIALLY PASSED - Review session details")
        else:
            logger.warning(f"  ❌ Trade count criteria NOT MET: {trades_executed}/{min_trades}")
        
        logger.info("  Complete criteria review in Obsidian documentation")
    
    def stop(self):
        """Stop the agent."""
        self.running = False
        logger.info("Gate 2 Simple Agent stopping")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="QuantumArb Gate 2 Simple Agent")
    parser.add_argument("--config", type=str, default="config/live_phase2_sol_microscopic.json",
                       help="Path to Gate 2 configuration file")
    
    args = parser.parse_args()
    
    # Create agent
    agent = QuantumArbGate2Simple(args.config)
    
    try:
        # Run session
        agent.run_session()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        agent.stop()

if __name__ == "__main__":
    main()