#!/usr/bin/env python3.10
"""
Gate 2.5 Enhanced SOL Microscopic Trading Agent

Enhanced features:
1. Multi-factor risk scoring (5 factors)
2. Size tiers based on risk score
3. Limit order execution simulation
4. Enhanced monitoring and alerts
5. Performance tracking
"""

import json
import time
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("quantumarb_gate2.5")

# Data models
class ArbType(str, Enum):
    CROSS_VENUE = "cross_venue"
    TRIANGULAR = "triangular"

@dataclass
class ArbitrageSignal:
    """Arbitrage signal from detector."""
    signal_id: str
    arb_type: ArbType
    symbol_a: str
    symbol_b: str
    venue_a: str
    venue_b: str
    spread_pct: float
    expected_return_pct: float
    confidence: float
    timestamp: str
    metadata: Dict[str, Any]

@dataclass
class ArbitrageOpportunity:
    """Evaluated arbitrage opportunity."""
    signal: ArbitrageSignal
    decision: str  # "execute", "reject_risk", "reject_slippage", etc.
    decision_reason: str
    position_size_usd: float
    expected_pnl_usd: float
    risk_score: float
    metadata: Dict[str, Any]

@dataclass
class ExecutionResult:
    """Trade execution result."""
    trade_id: str
    timestamp: str
    symbol: str
    side: str
    quantity: float
    price: float
    notional_usd: float
    fees_usd: float
    slippage_pct: float
    pnl_usd: float
    status: str
    metadata: Dict[str, Any]

class MultiFactorRiskScorer:
    """Multi-factor risk scoring for Gate 2.5."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.factors = config.get("risk_management", {}).get("factors", {})
        self.symbol_params = config.get("risk_management", {}).get("symbol_specific", {}).get("SOL-USD", {})
        
    def calculate_risk_score(self, signal: ArbitrageSignal) -> float:
        """Calculate multi-factor risk score."""
        try:
            # Factor 1: Spread (35%)
            spread_score = self._calculate_spread_score(signal.spread_pct)
            
            # Factor 2: Confidence (30%)
            confidence_score = self._calculate_confidence_score(signal.confidence)
            
            # Factor 3: Liquidity (15%)
            liquidity_score = self._calculate_liquidity_score(signal.symbol_a)
            
            # Factor 4: Volatility (12%)
            volatility_score = self._calculate_volatility_score(signal.symbol_a)
            
            # Factor 5: Slippage (8%)
            slippage_score = self._calculate_slippage_score(signal.expected_return_pct)
            
            # Weighted sum
            weights = self.factors
            risk_score = (
                spread_score * weights.get("spread", {}).get("weight", 0.35) +
                confidence_score * weights.get("confidence", {}).get("weight", 0.30) +
                liquidity_score * weights.get("liquidity", {}).get("weight", 0.15) +
                volatility_score * weights.get("volatility", {}).get("weight", 0.12) +
                slippage_score * weights.get("slippage", {}).get("weight", 0.08)
            )
            
            # Normalize to 0-1 range
            risk_score = max(0.0, min(1.0, risk_score))
            
            logger.info(f"Risk score breakdown: spread={spread_score:.3f}, confidence={confidence_score:.3f}, "
                       f"liquidity={liquidity_score:.3f}, volatility={volatility_score:.3f}, "
                       f"slippage={slippage_score:.3f}, total={risk_score:.3f}")
            
            return risk_score
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 0.0
    
    def _calculate_spread_score(self, spread_pct: float) -> float:
        """Calculate spread factor score."""
        spread_config = self.factors.get("spread", {})
        min_spread = spread_config.get("min", 0.02)
        max_spread = spread_config.get("max", 0.30)
        normalization = spread_config.get("normalization", 0.25)
        
        if spread_pct < min_spread:
            return 0.0
        elif spread_pct > max_spread:
            return 1.0
        else:
            # Normalize to 0-1 range
            normalized = (spread_pct - min_spread) / (max_spread - min_spread)
            # Apply normalization factor
            return min(1.0, normalized / normalization)
    
    def _calculate_confidence_score(self, confidence: float) -> float:
        """Calculate confidence factor score."""
        confidence_config = self.factors.get("confidence", {})
        min_confidence = confidence_config.get("min", 0.75)
        
        if confidence < min_confidence:
            return 0.0
        else:
            # Scale from min_confidence to 1.0
            return (confidence - min_confidence) / (1.0 - min_confidence)
    
    def _calculate_liquidity_score(self, symbol: str) -> float:
        """Calculate liquidity factor score."""
        # For SOL-USD, assume high liquidity
        return self.symbol_params.get("liquidity_score", 0.9)
    
    def _calculate_volatility_score(self, symbol: str) -> float:
        """Calculate volatility factor score."""
        # Inverse of volatility - higher volatility = lower score
        volatility_factor = self.symbol_params.get("volatility_factor", 0.8)
        # Simulate recent volatility (would come from market data)
        recent_volatility = random.uniform(0.15, 0.25)
        # Higher recent volatility = lower score
        return max(0.0, 1.0 - (recent_volatility * volatility_factor))
    
    def _calculate_slippage_score(self, expected_return: float) -> float:
        """Calculate slippage factor score."""
        slippage_config = self.factors.get("slippage", {})
        max_slippage = slippage_config.get("max", 0.03)
        
        # Estimate slippage as percentage of expected return
        # Higher expected return = lower estimated slippage impact
        estimated_slippage_impact = random.uniform(0.005, 0.02)
        
        if estimated_slippage_impact > max_slippage:
            return 0.0
        else:
            return 1.0 - (estimated_slippage_impact / max_slippage)

class QuantumArbGate2_5:
    """Gate 2.5 Enhanced SOL Microscopic Trading Agent."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self.risk_scorer = MultiFactorRiskScorer(self.config)
        self.session_id = f"gate2.5_{int(time.time())}"
        
        # Setup directories
        self.data_dir = Path("data/quantumarb_gate2.5")
        self.decisions_dir = self.data_dir / "decisions"
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        
        # Session tracking
        self.session_start = datetime.now()
        self.trades_executed = 0
        self.total_pnl = 0.0
        self.opportunities_evaluated = 0
        self.decisions = {
            "execute": 0,
            "reject_risk": 0,
            "reject_slippage": 0,
            "reject_confidence": 0,
            "reject_symbol": 0
        }
        
        logger.info(f"Gate 2.5 Agent initialized with session ID: {self.session_id}")
        logger.info(f"Config loaded: {self.config.get('mode', 'unknown')}")
        logger.info(f"Target trades: {self.config.get('targets', {}).get('total_trades', 50)}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def _generate_test_signal(self) -> ArbitrageSignal:
        """Generate a test arbitrage signal for SOL-USD."""
        signal_id = f"sol_gate2.5_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Generate realistic SOL parameters
        spread = random.uniform(0.03, 0.15)  # 0.03% to 0.15%
        confidence = random.uniform(0.78, 0.95)
        expected_return = spread - random.uniform(0.005, 0.015)  # Account for fees/slippage
        
        return ArbitrageSignal(
            signal_id=signal_id,
            arb_type=ArbType.CROSS_VENUE,
            symbol_a="SOL-USD",
            symbol_b="SOL-USD",
            venue_a="coinbase",
            venue_b="coinbase",
            spread_pct=round(spread, 4),
            expected_return_pct=round(expected_return, 4),
            confidence=round(confidence, 2),
            timestamp=datetime.now().isoformat(),
            metadata={
                "gate": "2.5",
                "market": "SOL-USD",
                "microscopic": True,
                "enhanced": True,
                "test_signal": True
            }
        )
    
    def _get_position_size(self, risk_score: float) -> float:
        """Get position size based on risk score tier."""
        size_tiers = self.config.get("position_sizing", {}).get("size_tiers", {})
        
        # Find appropriate tier
        for tier_name, tier_config in size_tiers.items():
            if risk_score >= tier_config.get("risk_score", 0.0):
                size = tier_config.get("size", 0.25)
                logger.info(f"Risk score {risk_score:.3f} → Tier {tier_name} → Size ${size:.2f}")
                return size
        
        # Fallback to default
        default_size = self.config.get("position_sizing", {}).get("default_notional", 0.25)
        logger.info(f"Risk score {risk_score:.3f} → Default tier → Size ${default_size:.2f}")
        return default_size
    
    def _evaluate_opportunity(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate arbitrage opportunity with enhanced risk scoring."""
        self.opportunities_evaluated += 1
        
        # Check symbol
        if signal.symbol_a != "SOL-USD":
            return ArbitrageOpportunity(
                signal=signal,
                decision="reject_symbol",
                decision_reason=f"Symbol {signal.symbol_a} not in configured symbols (SOL-USD only)",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                risk_score=0.0,
                metadata={"rejection_reason": "wrong_symbol"}
            )
        
        # Check confidence
        min_confidence = self.config.get("risk_management", {}).get("factors", {}).get("confidence", {}).get("min", 0.75)
        if signal.confidence < min_confidence:
            return ArbitrageOpportunity(
                signal=signal,
                decision="reject_confidence",
                decision_reason=f"Confidence {signal.confidence:.2f} < minimum {min_confidence}",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                risk_score=0.0,
                metadata={"rejection_reason": "low_confidence"}
            )
        
        # Calculate risk score
        risk_score = self.risk_scorer.calculate_risk_score(signal)
        
        # Check minimum risk score
        min_score = self.config.get("risk_management", {}).get("minimum_score", 0.55)
        if risk_score < min_score:
            return ArbitrageOpportunity(
                signal=signal,
                decision="reject_risk",
                decision_reason=f"Risk score {risk_score:.3f} < minimum {min_score}",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                risk_score=risk_score,
                metadata={"rejection_reason": "low_risk_score"}
            )
        
        # Get position size based on risk score
        position_size = self._get_position_size(risk_score)
        
        # Calculate expected P&L
        expected_pnl = position_size * (signal.expected_return_pct / 100)
        
        # Simulate slippage check
        max_slippage_bps = self.config.get("execution", {}).get("max_slippage_bps", 10)
        estimated_slippage = random.uniform(2, 8)  # 2-8 bps
        
        if estimated_slippage > max_slippage_bps:
            return ArbitrageOpportunity(
                signal=signal,
                decision="reject_slippage",
                decision_reason=f"Estimated slippage {estimated_slippage:.1f}bps > max {max_slippage_bps}bps",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                risk_score=risk_score,
                metadata={"rejection_reason": "high_slippage"}
            )
        
        # Approved!
        return ArbitrageOpportunity(
            signal=signal,
            decision="execute",
            decision_reason=f"Approved: risk score {risk_score:.3f}, spread {signal.spread_pct:.4f}%, confidence {signal.confidence:.2f}",
            position_size_usd=position_size,
            expected_pnl_usd=expected_pnl,
            risk_score=risk_score,
            metadata={
                "approved": True,
                "estimated_slippage_bps": estimated_slippage,
                "size_tier": "determined_by_risk"
            }
        )
    
    def _execute_trade(self, opportunity: ArbitrageOpportunity) -> ExecutionResult:
        """Execute trade with enhanced features (limit orders, partial fills)."""
        trade_id = f"trade_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Simulate limit order execution
        order_type = self.config.get("execution", {}).get("default_order_type", "limit")
        time_in_force = self.config.get("execution", {}).get("time_in_force", "IOC")
        
        # Simulate partial fill
        allow_partial = self.config.get("execution", {}).get("allow_partial_fills", True)
        min_fill = self.config.get("execution", {}).get("min_fill_percentage", 70)
        
        if allow_partial:
            fill_percentage = random.uniform(min_fill, 100.0)
        else:
            fill_percentage = 100.0
        
        # Calculate executed quantities
        executed_notional = opportunity.position_size_usd * (fill_percentage / 100)
        
        # Simulate price improvement for limit orders
        price_improvement_target = self.config.get("execution", {}).get("price_improvement_target", 0.005)
        price_improvement = random.uniform(0, price_improvement_target * 2)
        
        # Calculate P&L with fees and slippage
        fees_rate = 0.001  # 0.1%
        fees = executed_notional * fees_rate
        actual_pnl = opportunity.expected_pnl_usd * (fill_percentage / 100) - fees
        
        # Simulate slippage
        slippage_pct = random.uniform(0.001, 0.005)  # 0.1-0.5%
        
        result = ExecutionResult(
            trade_id=trade_id,
            timestamp=datetime.now().isoformat(),
            symbol=opportunity.signal.symbol_a,
            side=random.choice(["buy", "sell"]),
            quantity=executed_notional / 100,  # Rough SOL price ~$100
            price=100.0,
            notional_usd=executed_notional,
            fees_usd=fees,
            slippage_pct=slippage_pct,
            pnl_usd=actual_pnl,
            status="filled" if fill_percentage >= min_fill else "partially_filled",
            metadata={
                "gate": "2.5",
                "order_type": order_type,
                "time_in_force": time_in_force,
                "fill_percentage": fill_percentage,
                "price_improvement_pct": price_improvement,
                "limit_order": True,
                "partial_fill": fill_percentage < 100.0
            }
        )
        
        logger.info(f"Trade executed: {trade_id}, Size: ${executed_notional:.4f}, "
                   f"Fill: {fill_percentage:.1f}%, P&L: ${actual_pnl:.6f}, "
                   f"Slippage: {slippage_pct:.4f}%, Price improvement: {price_improvement:.4f}%")
        
        return result
    
    def _save_decision(self, signal: ArbitrageSignal, opportunity: ArbitrageOpportunity, 
                      execution_result: Optional[ExecutionResult] = None):
        """Save decision and execution result."""
        decision_data = {
            "timestamp": datetime.now().isoformat(),
            "signal": asdict(signal),
            "opportunity": asdict(opportunity),
            "execution_result": asdict(execution_result) if execution_result else None,
            "session_id": self.session_id,
            "gate": "2.5"
        }
        
        filename = self.decisions_dir / f"{signal.signal_id}.json"
        with open(filename, 'w') as f:
            json.dump(decision_data, f, indent=2)
        
        # Update session tracking
        self.decisions[opportunity.decision] += 1
        
        if opportunity.decision == "execute" and execution_result:
            self.trades_executed += 1
            self.total_pnl += execution_result.pnl_usd
    
    def _check_session_complete(self) -> bool:
        """Check if session completion criteria are met."""
        targets = self.config.get("targets", {})
        total_target = targets.get("total_trades", 50)
        min_for_success = targets.get("min_for_success", 40)
        
        if self.trades_executed >= total_target:
            logger.info(f"✅ Target reached: {self.trades_executed}/{total_target} trades")
            return True
        elif self.trades_executed >= min_for_success:
            logger.info(f"✅ Minimum for success reached: {self.trades_executed}/{min_for_success} trades")
            # Could continue to target, but minimum met
            return False
        else:
            return False
    
    def _save_session_summary(self):
        """Save session summary."""
        session_duration = (datetime.now() - self.session_start).total_seconds() / 60
        
        summary = {
            "session_id": self.session_id,
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "session_duration_minutes": round(session_duration, 2),
            "trades_executed": self.trades_executed,
            "total_pnl": round(self.total_pnl, 6),
            "opportunities_evaluated": self.opportunities_evaluated,
            "decisions": self.decisions,
            "config_file": self.config_path,
            "gate": "2.5",
            "completion_status": "complete" if self.trades_executed >= self.config.get("targets", {}).get("min_for_success", 40) else "incomplete"
        }
        
        summary_path = self.data_dir / f"session_summary_{self.session_id}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Session summary saved: {summary_path}")
        
        # Print summary
        print("\n" + "="*60)
        print("GATE 2.5 SESSION SUMMARY")
        print("="*60)
        print(f"Session ID: {self.session_id}")
        print(f"Duration: {session_duration:.1f} minutes")
        print(f"Trades Executed: {self.trades_executed}")
        print(f"Total P&L: ${self.total_pnl:.6f}")
        print(f"Opportunities Evaluated: {self.opportunities_evaluated}")
        print("\nDecision Breakdown:")
        for decision, count in self.decisions.items():
            if count > 0:
                print(f"  {decision}: {count}")
        print("="*60)
    
    def run_session(self):
        """Run Gate 2.5 trading session."""
        logger.info("Starting Gate 2.5 trading session...")
        logger.info(f"Target: {self.config.get('targets', {}).get('total_trades', 50)} trades")
        logger.info(f"Minimum for success: {self.config.get('targets', {}).get('min_for_success', 40)} trades")
        
        try:
            while not self._check_session_complete():
                # Generate test signal
                signal = self._generate_test_signal()
                
                # Evaluate opportunity
                opportunity = self._evaluate_opportunity(signal)
                
                # Process based on decision
                execution_result = None
                if opportunity.decision == "execute":
                    # Execute trade
                    execution_result = self._execute_trade(opportunity)
                
                # Save decision
                self._save_decision(signal, opportunity, execution_result)
                
                # Log progress
                if self.trades_executed % 10 == 0 and self.trades_executed > 0:
                    logger.info(f"Progress: {self.trades_executed} trades executed, P&L: ${self.total_pnl:.6f}")
                
                # Small delay between evaluations
                time.sleep(random.uniform(0.5, 1.5))
            
            # Session complete
            logger.info("Gate 2.5 session completed successfully!")
            
        except KeyboardInterrupt:
            logger.info("Session interrupted by user")
        except Exception as e:
            logger.error(f"Session error: {e}")
        finally:
            # Save session summary
            self._save_session_summary()
            
            # Check if minimum success criteria met
            min_for_success = self.config.get("targets", {}).get("min_for_success", 40)
            if self.trades_executed >= min_for_success:
                logger.info(f"✅ GATE 2.5 SUCCESS: {self.trades_executed}/{min_for_success} minimum trades executed")
            else:
                logger.warning(f"⚠️ GATE 2.5 INCOMPLETE: {self.trades_executed}/{min_for_success} trades (minimum not met)")

def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3.10 quantumarb_gate2.5.py <config_path>")
        print("Example: python3.10 quantumarb_gate2.5.py config/gate2.5_enhanced_sol.json")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    # Create and run agent
    agent = QuantumArbGate2_5(config_path)
    agent.run_session()

if __name__ == "__main__":
    main()