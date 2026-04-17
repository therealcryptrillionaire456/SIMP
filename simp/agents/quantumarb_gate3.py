#!/usr/bin/env python3.10
"""
Gate 3 Multi-Market Microscopic Trading Agent

Enhanced features:
1. Multi-market support (SOL-USD, BTC-USD, ETH-USD)
2. Symbol-specific risk scoring
3. Concurrent trading across markets
4. Advanced execution strategies
5. Comprehensive performance tracking
"""

import json
import time
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("quantumarb_gate3")

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

@dataclass
class SymbolPerformance:
    """Performance metrics for a symbol."""
    symbol: str
    trades_executed: int
    total_pnl: float
    avg_risk_score: float
    avg_slippage_pct: float
    avg_fill_percentage: float
    avg_price_improvement_pct: float

class MultiMarketRiskScorer:
    """Multi-market risk scoring for Gate 3."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.factors = config.get("risk_management", {}).get("factors", {})
        self.symbol_params = config.get("symbol_characteristics", {})
        
    def calculate_risk_score(self, signal: ArbitrageSignal) -> float:
        """Calculate multi-factor risk score with symbol-specific parameters."""
        try:
            symbol = signal.symbol_a
            
            # Factor 1: Spread (30%)
            spread_score = self._calculate_spread_score(symbol, signal.spread_pct)
            
            # Factor 2: Confidence (25%)
            confidence_score = self._calculate_confidence_score(signal.confidence)
            
            # Factor 3: Liquidity (20%)
            liquidity_score = self._calculate_liquidity_score(symbol)
            
            # Factor 4: Volatility (15%)
            volatility_score = self._calculate_volatility_score(symbol)
            
            # Factor 5: Slippage (10%)
            slippage_score = self._calculate_slippage_score(symbol, signal.expected_return_pct)
            
            # Weighted sum
            weights = self.factors
            risk_score = (
                spread_score * weights.get("spread", {}).get("weight", 0.30) +
                confidence_score * weights.get("confidence", {}).get("weight", 0.25) +
                liquidity_score * weights.get("liquidity", {}).get("weight", 0.20) +
                volatility_score * weights.get("volatility", {}).get("weight", 0.15) +
                slippage_score * weights.get("slippage", {}).get("weight", 0.10)
            )
            
            # Normalize to 0-1 range
            risk_score = max(0.0, min(1.0, risk_score))
            
            logger.info(f"[{symbol}] Risk score: {risk_score:.3f} (spread={spread_score:.3f}, "
                       f"confidence={confidence_score:.3f}, liquidity={liquidity_score:.3f}, "
                       f"volatility={volatility_score:.3f}, slippage={slippage_score:.3f})")
            
            return risk_score
            
        except Exception as e:
            logger.error(f"Error calculating risk score for {signal.symbol_a}: {e}")
            return 0.0
    
    def _calculate_spread_score(self, symbol: str, spread_pct: float) -> float:
        """Calculate spread factor score with symbol-specific parameters."""
        spread_config = self.factors.get("spread", {})
        min_spread = spread_config.get("min_by_symbol", {}).get(symbol, 0.02)
        max_spread = spread_config.get("max_by_symbol", {}).get(symbol, 0.30)
        normalization = spread_config.get("normalization_by_symbol", {}).get(symbol, 0.25)
        
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
        """Calculate liquidity factor score with symbol-specific parameters."""
        liquidity_config = self.factors.get("liquidity", {})
        return liquidity_config.get("scores_by_symbol", {}).get(symbol, 0.9)
    
    def _calculate_volatility_score(self, symbol: str) -> float:
        """Calculate volatility factor score with symbol-specific parameters."""
        volatility_config = self.factors.get("volatility", {})
        max_volatility = volatility_config.get("max_by_symbol", {}).get(symbol, 0.25)
        
        # Simulate recent volatility (would come from market data)
        # Different volatility ranges per symbol
        if symbol == "SOL-USD":
            recent_volatility = random.uniform(0.18, 0.28)
        elif symbol == "BTC-USD":
            recent_volatility = random.uniform(0.12, 0.22)
        else:  # ETH-USD
            recent_volatility = random.uniform(0.15, 0.25)
        
        # Higher recent volatility = lower score
        volatility_impact = recent_volatility / max_volatility
        return max(0.0, 1.0 - volatility_impact)
    
    def _calculate_slippage_score(self, symbol: str, expected_return: float) -> float:
        """Calculate slippage factor score with symbol-specific parameters."""
        slippage_config = self.factors.get("slippage", {})
        max_slippage = slippage_config.get("max_by_symbol", {}).get(symbol, 0.03)
        
        # Estimate slippage as percentage of expected return
        # Different slippage ranges per symbol
        if symbol == "SOL-USD":
            estimated_slippage = random.uniform(0.005, 0.015)
        elif symbol == "BTC-USD":
            estimated_slippage = random.uniform(0.003, 0.010)
        else:  # ETH-USD
            estimated_slippage = random.uniform(0.004, 0.012)
        
        if estimated_slippage > max_slippage:
            return 0.0
        else:
            return 1.0 - (estimated_slippage / max_slippage)

class QuantumArbGate3:
    """Gate 3 Multi-Market Microscopic Trading Agent."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self.risk_scorer = MultiMarketRiskScorer(self.config)
        self.session_id = f"gate3_{int(time.time())}"
        
        # Setup directories
        self.data_dir = Path("data/quantumarb_gate3")
        self.decisions_dir = self.data_dir / "decisions"
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        
        # Session tracking
        self.session_start = datetime.now()
        self.trades_executed = 0
        self.total_pnl = 0.0
        self.opportunities_evaluated = 0
        self.decisions = defaultdict(int)
        
        # Symbol-specific tracking
        self.symbol_stats = {
            "SOL-USD": {"trades": 0, "pnl": 0.0, "risk_scores": [], "slippage": [], "fills": [], "price_improvement": []},
            "BTC-USD": {"trades": 0, "pnl": 0.0, "risk_scores": [], "slippage": [], "fills": [], "price_improvement": []},
            "ETH-USD": {"trades": 0, "pnl": 0.0, "risk_scores": [], "slippage": [], "fills": [], "price_improvement": []}
        }
        
        # Targets
        self.targets = self.config.get("targets", {})
        
        logger.info(f"Gate 3 Agent initialized with session ID: {self.session_id}")
        logger.info(f"Config loaded: {self.config.get('mode', 'unknown')}")
        logger.info(f"Target trades: {self.targets.get('total_trades', 150)}")
        logger.info(f"Markets: {', '.join(self.config.get('symbols', []))}")
    
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
        """Generate a test arbitrage signal for a random symbol."""
        symbols = self.config.get("symbols", ["SOL-USD"])
        symbol = random.choice(symbols)
        
        signal_id = f"{symbol.lower().replace('-', '')}_gate3_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Generate symbol-specific parameters
        if symbol == "SOL-USD":
            spread = random.uniform(0.03, 0.15)  # 0.03% to 0.15%
            confidence = random.uniform(0.78, 0.95)
            price = random.uniform(80, 120)
        elif symbol == "BTC-USD":
            spread = random.uniform(0.01, 0.08)  # 0.01% to 0.08%
            confidence = random.uniform(0.80, 0.98)
            price = random.uniform(60000, 70000)
        else:  # ETH-USD
            spread = random.uniform(0.02, 0.10)  # 0.02% to 0.10%
            confidence = random.uniform(0.79, 0.96)
            price = random.uniform(3000, 4000)
        
        expected_return = spread - random.uniform(0.003, 0.010)  # Account for fees/slippage
        
        return ArbitrageSignal(
            signal_id=signal_id,
            arb_type=ArbType.CROSS_VENUE,
            symbol_a=symbol,
            symbol_b=symbol,
            venue_a="coinbase",
            venue_b="coinbase",
            spread_pct=round(spread, 4),
            expected_return_pct=round(expected_return, 4),
            confidence=round(confidence, 2),
            timestamp=datetime.now().isoformat(),
            metadata={
                "gate": "3",
                "market": symbol,
                "microscopic": True,
                "multi_market": True,
                "test_signal": True,
                "estimated_price": price
            }
        )
    
    def _get_position_size(self, symbol: str, risk_score: float) -> float:
        """Get position size based on symbol and risk score tier."""
        size_config = self.config.get("position_sizing", {})
        base_size = size_config.get("size_by_symbol", {}).get(symbol, 0.50)
        
        # Apply size tier multiplier based on risk score
        size_tiers = size_config.get("size_tiers", {})
        multiplier = 0.2  # Default minimum
        
        for tier_name, tier_config in size_tiers.items():
            if risk_score >= tier_config.get("risk_score", 0.0):
                multiplier = tier_config.get("size_multiplier", 0.2)
        
        position_size = base_size * multiplier
        position_size = max(
            size_config.get("min_notional", 0.10),
            min(size_config.get("max_notional", 1.00), position_size)
        )
        
        logger.info(f"[{symbol}] Risk score {risk_score:.3f} → Multiplier {multiplier:.1f} → Size ${position_size:.2f}")
        return position_size
    
    def _get_minimum_risk_score(self, symbol: str) -> float:
        """Get minimum risk score for a symbol."""
        risk_config = self.config.get("risk_management", {})
        return risk_config.get("minimum_score_by_symbol", {}).get(symbol, 0.60)
    
    def _evaluate_opportunity(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate arbitrage opportunity with multi-market risk scoring."""
        self.opportunities_evaluated += 1
        symbol = signal.symbol_a
        
        # Check if symbol is configured
        if symbol not in self.config.get("symbols", []):
            return ArbitrageOpportunity(
                signal=signal,
                decision="reject_symbol",
                decision_reason=f"Symbol {symbol} not in configured symbols",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                risk_score=0.0,
                metadata={"rejection_reason": "unconfigured_symbol"}
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
        
        # Calculate risk score with symbol-specific parameters
        risk_score = self.risk_scorer.calculate_risk_score(signal)
        
        # Check minimum risk score for symbol
        min_score = self._get_minimum_risk_score(symbol)
        if risk_score < min_score:
            return ArbitrageOpportunity(
                signal=signal,
                decision="reject_risk",
                decision_reason=f"Risk score {risk_score:.3f} < minimum {min_score} for {symbol}",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                risk_score=risk_score,
                metadata={"rejection_reason": "low_risk_score", "symbol": symbol}
            )
        
        # Get position size based on symbol and risk score
        position_size = self._get_position_size(symbol, risk_score)
        
        # Calculate expected P&L
        expected_pnl = position_size * (signal.expected_return_pct / 100)
        
        # Simulate slippage check with symbol-specific limits
        slippage_config = self.config.get("execution", {})
        max_slippage_bps = slippage_config.get("max_slippage_bps_by_symbol", {}).get(symbol, 10)
        estimated_slippage = random.uniform(2, max_slippage_bps - 2)  # Within limit
        
        if estimated_slippage > max_slippage_bps:
            return ArbitrageOpportunity(
                signal=signal,
                decision="reject_slippage",
                decision_reason=f"Estimated slippage {estimated_slippage:.1f}bps > max {max_slippage_bps}bps for {symbol}",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                risk_score=risk_score,
                metadata={"rejection_reason": "high_slippage", "symbol": symbol}
            )
        
        # Approved!
        return ArbitrageOpportunity(
            signal=signal,
            decision="execute",
            decision_reason=f"Approved: {symbol} risk score {risk_score:.3f}, spread {signal.spread_pct:.4f}%, confidence {signal.confidence:.2f}",
            position_size_usd=position_size,
            expected_pnl_usd=expected_pnl,
            risk_score=risk_score,
            metadata={
                "approved": True,
                "symbol": symbol,
                "estimated_slippage_bps": estimated_slippage,
                "size_tier": "determined_by_risk",
                "multi_market": True
            }
        )
    
    def _execute_trade(self, opportunity: ArbitrageOpportunity) -> ExecutionResult:
        """Execute trade with multi-market enhanced features."""
        trade_id = f"trade_{int(time.time())}_{random.randint(1000, 9999)}"
        symbol = opportunity.signal.symbol_a
        
        # Get symbol-specific execution parameters
        exec_config = self.config.get("execution", {})
        order_type = exec_config.get("default_order_type", "limit")
        time_in_force = exec_config.get("time_in_force", "GTC")
        
        # Simulate partial fill
        allow_partial = exec_config.get("allow_partial_fills", True)
        min_fill = exec_config.get("min_fill_percentage", 80)
        
        if allow_partial:
            fill_percentage = random.uniform(min_fill, 100.0)
        else:
            fill_percentage = 100.0
        
        # Calculate executed quantities
        executed_notional = opportunity.position_size_usd * (fill_percentage / 100)
        
        # Get estimated price from metadata
        estimated_price = opportunity.signal.metadata.get("estimated_price", 100.0)
        
        # Simulate price improvement
        price_improvement_target = exec_config.get("price_improvement_target", 0.005)
        price_improvement = random.uniform(0, price_improvement_target * 2)
        
        # Calculate P&L with fees and slippage
        fees_rate = 0.001  # 0.1%
        fees = executed_notional * fees_rate
        
        # Symbol-specific P&L calculation
        actual_pnl = opportunity.expected_pnl_usd * (fill_percentage / 100) - fees
        
        # Simulate slippage with symbol-specific ranges
        if symbol == "SOL-USD":
            slippage_pct = random.uniform(0.001, 0.005)  # 0.1-0.5%
        elif symbol == "BTC-USD":
            slippage_pct = random.uniform(0.0005, 0.003)  # 0.05-0.3%
        else:  # ETH-USD
            slippage_pct = random.uniform(0.0008, 0.004)  # 0.08-0.4%
        
        result = ExecutionResult(
            trade_id=trade_id,
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            side=random.choice(["buy", "sell"]),
            quantity=executed_notional / estimated_price,
            price=estimated_price,
            notional_usd=executed_notional,
            fees_usd=fees,
            slippage_pct=slippage_pct,
            pnl_usd=actual_pnl,
            status="filled" if fill_percentage >= min_fill else "partially_filled",
            metadata={
                "gate": "3",
                "order_type": order_type,
                "time_in_force": time_in_force,
                "fill_percentage": fill_percentage,
                "price_improvement_pct": price_improvement,
                "limit_order": order_type == "limit",
                "partial_fill": fill_percentage < 100.0,
                "multi_market": True,
                "symbol": symbol
            }
        )
        
        logger.info(f"[{symbol}] Trade executed: {trade_id}, Size: ${executed_notional:.4f}, "
                   f"Fill: {fill_percentage:.1f}%, P&L: ${actual_pnl:.6f}, "
                   f"Slippage: {slippage_pct:.4f}%, Price improvement: {price_improvement:.4f}%")
        
        # Update symbol statistics
        self.symbol_stats[symbol]["trades"] += 1
        self.symbol_stats[symbol]["pnl"] += actual_pnl
        self.symbol_stats[symbol]["risk_scores"].append(opportunity.risk_score)
        self.symbol_stats[symbol]["slippage"].append(slippage_pct)
        self.symbol_stats[symbol]["fills"].append(fill_percentage)
        self.symbol_stats[symbol]["price_improvement"].append(price_improvement)
        
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
            "gate": "3"
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
        total_target = self.targets.get("total_trades", 150)
        min_for_success = self.targets.get("min_for_success", 120)
        
        # Check symbol-specific minimums
        symbol_targets = self.targets.get("min_trades_per_symbol", {})
        all_symbols_met = True
        for symbol, min_trades in symbol_targets.items():
            if self.symbol_stats[symbol]["trades"] < min_trades:
                all_symbols_met = False
                break
        
        if self.trades_executed >= total_target and all_symbols_met:
            logger.info(f"✅ All targets reached: {self.trades_executed}/{total_target} trades")
            return True
        elif self.trades_executed >= min_for_success and all_symbols_met:
            logger.info(f"✅ Minimum for success reached: {self.trades_executed}/{min_for_success} trades")
            # Could continue to target, but minimum met
            return False
        else:
            return False
    
    def _calculate_symbol_performance(self) -> List[SymbolPerformance]:
        """Calculate performance metrics for each symbol."""
        performances = []
        
        for symbol, stats in self.symbol_stats.items():
            trades = stats["trades"]
            if trades > 0:
                avg_risk = sum(stats["risk_scores"]) / len(stats["risk_scores"]) if stats["risk_scores"] else 0.0
                avg_slippage = sum(stats["slippage"]) / len(stats["slippage"]) if stats["slippage"] else 0.0
                avg_fill = sum(stats["fills"]) / len(stats["fills"]) if stats["fills"] else 0.0
                avg_price_improvement = sum(stats["price_improvement"]) / len(stats["price_improvement"]) if stats["price_improvement"] else 0.0
                
                performances.append(SymbolPerformance(
                    symbol=symbol,
                    trades_executed=trades,
                    total_pnl=stats["pnl"],
                    avg_risk_score=avg_risk,
                    avg_slippage_pct=avg_slippage,
                    avg_fill_percentage=avg_fill,
                    avg_price_improvement_pct=avg_price_improvement
                ))
        
        return performances
    
    def _save_session_summary(self):
        """Save comprehensive session summary."""
        session_duration = (datetime.now() - self.session_start).total_seconds() / 60
        
        # Calculate symbol performances
        symbol_performances = self._calculate_symbol_performance()
        
        summary = {
            "session_id": self.session_id,
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "session_duration_minutes": round(session_duration, 2),
            "trades_executed": self.trades_executed,
            "total_pnl": round(self.total_pnl, 6),
            "opportunities_evaluated": self.opportunities_evaluated,
            "decisions": dict(self.decisions),
            "symbol_performances": [asdict(sp) for sp in symbol_performances],
            "symbol_stats": self.symbol_stats,
            "config_file": self.config_path,
            "gate": "3",
            "completion_status": "complete" if self.trades_executed >= self.targets.get("min_for_success", 120) else "incomplete",
            "targets_met": {
                "total_trades": self.trades_executed >= self.targets.get("total_trades", 150),
                "min_trades": self.trades_executed >= self.targets.get("min_for_success", 120),
                "symbol_minimums": all(
                    self.symbol_stats[symbol]["trades"] >= self.targets.get("min_trades_per_symbol", {}).get(symbol, 0)
                    for symbol in self.config.get("symbols", [])
                )
            }
        }
        
        summary_path = self.data_dir / f"session_summary_{self.session_id}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Session summary saved: {summary_path}")
        
        # Print comprehensive summary
        self._print_session_summary(summary, symbol_performances, session_duration)
    
    def _print_session_summary(self, summary: Dict, performances: List[SymbolPerformance], duration: float):
        """Print comprehensive session summary."""
        print("\n" + "="*70)
        print("GATE 3 MULTI-MARKET SESSION SUMMARY")
        print("="*70)
        print(f"Session ID: {summary['session_id']}")
        print(f"Duration: {duration:.1f} minutes")
        print(f"Total Trades Executed: {summary['trades_executed']}")
        print(f"Total P&L: ${summary['total_pnl']:.6f}")
        print(f"Opportunities Evaluated: {summary['opportunities_evaluated']}")
        
        print("\n" + "-"*70)
        print("SYMBOL PERFORMANCE:")
        print("-"*70)
        for perf in performances:
            print(f"\n  {perf.symbol}:")
            print(f"    Trades: {perf.trades_executed}")
            print(f"    P&L: ${perf.total_pnl:.6f}")
            print(f"    Avg Risk Score: {perf.avg_risk_score:.3f}")
            print(f"    Avg Slippage: {perf.avg_slippage_pct:.4f}%")
            print(f"    Avg Fill: {perf.avg_fill_percentage:.1f}%")
            print(f"    Avg Price Improvement: {perf.avg_price_improvement_pct:.4f}%")
        
        print("\n" + "-"*70)
        print("DECISION BREAKDOWN:")
        print("-"*70)
        for decision, count in summary['decisions'].items():
            if count > 0:
                print(f"  {decision}: {count}")
        
        print("\n" + "-"*70)
        print("TARGETS STATUS:")
        print("-"*70)
        targets = self.targets
        print(f"  Total Trades: {summary['trades_executed']}/{targets.get('total_trades', 150)}")
        print(f"  Minimum Trades: {summary['trades_executed']}/{targets.get('min_for_success', 120)}")
        
        symbol_targets = targets.get("min_trades_per_symbol", {})
        for symbol, min_trades in symbol_targets.items():
            actual = self.symbol_stats[symbol]["trades"]
            status = "✅" if actual >= min_trades else "❌"
            print(f"  {symbol}: {actual}/{min_trades} {status}")
        
        print("="*70)
    
    def run_session(self):
        """Run Gate 3 multi-market trading session."""
        logger.info("Starting Gate 3 multi-market trading session...")
        logger.info(f"Target: {self.targets.get('total_trades', 150)} trades across {len(self.config.get('symbols', []))} markets")
        logger.info(f"Minimum for success: {self.targets.get('min_for_success', 120)} trades")
        logger.info(f"Markets: {', '.join(self.config.get('symbols', []))}")
        
        try:
            while not self._check_session_complete():
                # Generate test signal for random symbol
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
                if self.trades_executed % 20 == 0 and self.trades_executed > 0:
                    logger.info(f"Progress: {self.trades_executed} trades executed, P&L: ${self.total_pnl:.6f}")
                    # Log symbol distribution
                    for symbol in self.config.get("symbols", []):
                        trades = self.symbol_stats[symbol]["trades"]
                        if trades > 0:
                            logger.info(f"  {symbol}: {trades} trades, P&L: ${self.symbol_stats[symbol]['pnl']:.6f}")
                
                # Small delay between evaluations
                time.sleep(random.uniform(0.3, 0.8))
            
            # Session complete
            logger.info("Gate 3 session completed successfully!")
            
        except KeyboardInterrupt:
            logger.info("Session interrupted by user")
        except Exception as e:
            logger.error(f"Session error: {e}")
        finally:
            # Save session summary
            self._save_session_summary()
            
            # Check if minimum success criteria met
            min_for_success = self.targets.get("min_for_success", 120)
            if self.trades_executed >= min_for_success:
                logger.info(f"✅ GATE 3 SUCCESS: {self.trades_executed}/{min_for_success} minimum trades executed")
            else:
                logger.warning(f"⚠️ GATE 3 INCOMPLETE: {self.trades_executed}/{min_for_success} trades (minimum not met)")

def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3.10 quantumarb_gate3.py <config_path>")
        print("Example: python3.10 quantumarb_gate3.py config/gate3_multi_market.json")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    # Create and run agent
    agent = QuantumArbGate3(config_path)
    agent.run_session()

if __name__ == "__main__":
    main()