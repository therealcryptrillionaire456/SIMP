#!/usr/bin/env python3.10
"""
QuantumArb Agent - Phase 4 Simplified
Simplified version without optional dependencies for immediate operation.
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

# Phase 4 imports
from simp.organs.quantumarb.exchange_connector import (
    ExchangeConnector, Order, OrderSide, OrderType, OrderStatus,
    create_exchange_connector, ExchangeError, InsufficientFundsError
)
from simp.organs.quantumarb.executor import TradeExecutor, ExecutionResult
from simp.organs.quantumarb.pnl_ledger import PNLLedger, PnLRecord
from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("quantumarb_phase4_simple")

class ArbType(str, Enum):
    """Types of arbitrage opportunities."""
    CROSS_VENUE = "cross_venue"
    STATISTICAL = "statistical"
    TRIANGULAR = "triangular"
    FUNDING_RATE = "funding_rate"

class ArbDecision(str, Enum):
    """Arbitrage decision outcomes."""
    EXECUTE = "execute"
    REJECT_RISK = "reject_risk"
    REJECT_SLIPPAGE = "reject_slippage"
    REJECT_SIZE = "reject_size"
    REJECT_MONITORING = "reject_monitoring"

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
    execution_plan: Optional[Dict[str, Any]] = None
    
    def to_simp_intent(self, source_agent: str = "quantumarb_phase4") -> Dict[str, Any]:
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
                "risk_score": self.risk_score,
                "execution_plan": self.execution_plan or {}
            }
        }

class QuantumArbEnginePhase4Simple:
    """Simplified arbitrage engine for Phase 4."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.spread_history: Dict[str, List[float]] = {}
        self.max_history_size = 1000
        
        # Initialize components
        self.arb_detector = ArbDetector()
        
        # Initialize exchange connectors
        self.exchange_connectors: Dict[str, ExchangeConnector] = {}
        self._init_exchange_connectors()
        
        # Initialize trade executor
        self.trade_executor = TradeExecutor(
            exchange_connectors=self.exchange_connectors,
            monitoring_system=None,  # Simplified version
            config=self.config.get("executor", {})
        )
        
        # Initialize P&L ledger
        self.pnl_ledger = PNLLedger(
            ledger_path=self.config.get("pnl_ledger_path", "data/phase4_pnl_ledger.jsonl")
        )
        
        logger.info(f"QuantumArbEnginePhase4Simple initialized with {len(self.exchange_connectors)} exchanges")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration."""
        default_config = {
            "exchanges": {
                "coinbase": {
                    "type": "sandbox",
                    "api_key": "",
                    "api_secret": "",
                    "passphrase": ""
                }
            },
            "risk": {
                "max_position_size_usd": 0.10,  # $0.10 microscopic
                "max_daily_loss_usd": 1.00,     # $1.00 daily limit
                "min_spread_pct": 0.01,         # 0.01% minimum
                "max_slippage_pct": 0.05,       # 0.05% maximum
                "risk_score_threshold": 0.7     # 70% confidence required
            },
            "executor": {
                "max_retries": 3,
                "retry_delay_seconds": 1,
                "timeout_seconds": 30,
                "validate_orders": True
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
    
    def _init_exchange_connectors(self):
        """Initialize exchange connectors from config."""
        exchange_configs = self.config.get("exchanges", {})
        
        for exchange_name, config in exchange_configs.items():
            try:
                connector = create_exchange_connector(
                    exchange_name=exchange_name,
                    **config
                )
                self.exchange_connectors[exchange_name] = connector
                logger.info(f"Initialized exchange connector: {exchange_name}")
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_name}: {e}")
    
    def _record_spread(self, series_id: str, value: float) -> List[float]:
        """Record spread value in history."""
        if series_id not in self.spread_history:
            self.spread_history[series_id] = []
        
        history = self.spread_history[series_id]
        history.append(value)
        
        # Trim history if too long
        if len(history) > self.max_history_size:
            history = history[-self.max_history_size:]
            self.spread_history[series_id] = history
        
        return history
    
    def evaluate(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """Evaluate arbitrage opportunity."""
        logger.info(f"Evaluating arbitrage signal: {signal.signal_id}")
        
        # Record spread for analysis
        spread_series_id = f"{signal.symbol_a}_{signal.symbol_b}"
        self._record_spread(spread_series_id, signal.spread_pct)
        
        # Check minimum spread threshold
        min_spread = self.config["risk"]["min_spread_pct"]
        if signal.spread_pct < min_spread:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                reason=f"Spread {signal.spread_pct:.4f}% below minimum {min_spread:.4f}%"
            )
        
        # Use arb detector for advanced analysis
        arb_opportunity = self.arb_detector.detect_opportunity(
            symbol_a=signal.symbol_a,
            symbol_b=signal.symbol_b,
            venue_a=signal.venue_a,
            venue_b=signal.venue_b,
            spread_pct=signal.spread_pct
        )
        
        if not arb_opportunity:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                reason="Arb detector rejected opportunity"
            )
        
        # Calculate position size (microscopic)
        max_position = self.config["risk"]["max_position_size_usd"]
        position_size = min(max_position, arb_opportunity.max_trade_size_usd)
        
        # Estimate slippage
        slippage = self._estimate_slippage(signal, position_size)
        max_slippage = self.config["risk"]["max_slippage_pct"]
        
        if slippage > max_slippage:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_SLIPPAGE,
                reason=f"Estimated slippage {slippage:.4f}% exceeds maximum {max_slippage:.4f}%"
            )
        
        # Calculate expected P&L (adjusted for slippage)
        expected_return = signal.expected_return_pct - slippage
        expected_pnl = position_size * expected_return / 100
        
        # Check risk score
        risk_score = self._calculate_risk_score(signal, arb_opportunity, slippage)
        risk_threshold = self.config["risk"]["risk_score_threshold"]
        
        if risk_score < risk_threshold:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                reason=f"Risk score {risk_score:.2f} below threshold {risk_threshold:.2f}"
            )
        
        # Check daily loss limit
        daily_pnl = self.pnl_ledger.get_daily_pnl()
        max_daily_loss = self.config["risk"]["max_daily_loss_usd"]
        
        if daily_pnl < -max_daily_loss:
            return self._create_rejected_opportunity(
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                reason=f"Daily P&L {daily_pnl:.2f} below limit {-max_daily_loss:.2f}"
            )
        
        # Create execution plan
        execution_plan = self._create_execution_plan(signal, position_size, slippage)
        
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
            timestamp=datetime.utcnow().isoformat(),
            execution_plan=execution_plan
        )
    
    def _estimate_slippage(self, signal: ArbitrageSignal, position_size: float) -> float:
        """Estimate slippage for the trade."""
        try:
            # Try to get actual slippage estimates from exchanges
            if signal.venue_a in self.exchange_connectors:
                connector_a = self.exchange_connectors[signal.venue_a]
                slippage_a = connector_a.estimate_slippage(
                    symbol=signal.symbol_a,
                    side=OrderSide.BUY,
                    amount_usd=position_size,
                    order_type=OrderType.MARKET
                )
            else:
                slippage_a = 0.02  # Default 0.02%
            
            if signal.venue_b in self.exchange_connectors:
                connector_b = self.exchange_connectors[signal.venue_b]
                slippage_b = connector_b.estimate_slippage(
                    symbol=signal.symbol_b,
                    side=OrderSide.SELL,
                    amount_usd=position_size,
                    order_type=OrderType.MARKET
                )
            else:
                slippage_b = 0.02  # Default 0.02%
            
            return slippage_a + slippage_b
            
        except Exception as e:
            logger.warning(f"Error estimating slippage: {e}")
            return 0.05  # Conservative default
    
    def _calculate_risk_score(self, signal: ArbitrageSignal, 
                            arb_opportunity: ArbOpportunity, 
                            slippage: float) -> float:
        """Calculate risk score for opportunity."""
        # Base score from spread
        spread_score = min(signal.spread_pct / 1.0, 1.0)  # Normalize to 1% spread
        
        # Confidence from signal
        confidence_score = signal.confidence
        
        # Liquidity score (higher liquidity = lower risk)
        liquidity_score = min(arb_opportunity.liquidity_score, 1.0)
        
        # Slippage penalty
        slippage_penalty = max(0, 1.0 - (slippage / 0.1))  # Penalize above 0.1%
        
        # Historical spread stability
        spread_series_id = f"{signal.symbol_a}_{signal.symbol_b}"
        history = self.spread_history.get(spread_series_id, [])
        if len(history) >= 10:
            # Calculate volatility (lower volatility = higher score)
            import statistics
            if len(history) > 1:
                volatility = statistics.stdev(history) if len(history) > 1 else 0
                volatility_score = max(0, 1.0 - (volatility / 0.5))  # Penalize above 0.5% volatility
            else:
                volatility_score = 0.5
        else:
            volatility_score = 0.3  # Conservative for insufficient history
        
        # Weighted average
        weights = {
            "spread": 0.3,
            "confidence": 0.2,
            "liquidity": 0.2,
            "slippage": 0.2,
            "volatility": 0.1
        }
        
        risk_score = (
            spread_score * weights["spread"] +
            confidence_score * weights["confidence"] +
            liquidity_score * weights["liquidity"] +
            slippage_penalty * weights["slippage"] +
            volatility_score * weights["volatility"]
        )
        
        return min(max(risk_score, 0.0), 1.0)
    
    def _create_execution_plan(self, signal: ArbitrageSignal, 
                             position_size: float, slippage: float) -> Dict[str, Any]:
        """Create detailed execution plan."""
        return {
            "steps": [
                {
                    "step": 1,
                    "action": "buy",
                    "symbol": signal.symbol_a,
                    "venue": signal.venue_a,
                    "amount_usd": position_size,
                    "order_type": "market",
                    "expected_slippage_pct": slippage / 2
                },
                {
                    "step": 2,
                    "action": "sell",
                    "symbol": signal.symbol_b,
                    "venue": signal.venue_b,
                    "amount_usd": position_size,
                    "order_type": "market",
                    "expected_slippage_pct": slippage / 2
                }
            ],
            "total_position_usd": position_size,
            "total_slippage_pct": slippage,
            "expected_duration_seconds": 5.0,
            "fallback_strategy": "cancel_all"
        }
    
    def _create_rejected_opportunity(self, signal: ArbitrageSignal,
                                   decision: ArbDecision,
                                   reason: str) -> ArbitrageOpportunity:
        """Create rejected opportunity."""
        return ArbitrageOpportunity(
            opportunity_id=str(uuid.uuid4()),
            signal=signal,
            decision=decision,
            decision_reason=reason,
            position_size_usd=0.0,
            expected_pnl_usd=0.0,
            max_slippage_pct=0.0,
            risk_score=0.0,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def execute_opportunity(self, opportunity: ArbitrageOpportunity) -> ExecutionResult:
        """Execute arbitrage opportunity."""
        if opportunity.decision != ArbDecision.EXECUTE:
            logger.warning(f"Cannot execute rejected opportunity: {opportunity.decision_reason}")
            return ExecutionResult(
                success=False,
                error=f"Opportunity rejected: {opportunity.decision_reason}",
                trades=[],
                total_pnl_usd=0.0,
                actual_slippage_pct=0.0
            )
        
        logger.info(f"Executing opportunity: {opportunity.opportunity_id}")
        
        try:
            # Execute using trade executor
            result = await self.trade_executor.execute_arbitrage(
                opportunity=opportunity,
                execution_plan=opportunity.execution_plan
            )
            
            # Record in P&L ledger
            if result.success and result.trades:
                # Create simplified trade record
                trade_record = PnLRecord(
                    trade_id=opportunity.opportunity_id,
                    timestamp=datetime.utcnow().isoformat(),
                    symbol=f"{opportunity.signal.symbol_a}/{opportunity.signal.symbol_b}",
                    direction="arbitrage_buy_sell",
                    leg_a=None,  # Simplified version
                    leg_b=None,  # Simplified version
                    gross_pnl=result.total_pnl_usd,
                    fees_usd=result.total_fees_usd or 0.0,
                    net_pnl=result.total_pnl_usd - (result.total_fees_usd or 0.0),
                    metadata={
                        "opportunity": asdict(opportunity),
                        "execution_result": result.to_dict()
                    }
                )
                self.pnl_ledger.record_trade(trade_record)
            
            return result
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                trades=[],
                total_pnl_usd=0.0,
                actual_slippage_pct=0.0
            )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "opportunities_evaluated": len(self.spread_history),
            "trades_executed": self.pnl_ledger.get_trade_count(),
            "total_pnl_usd": self.pnl_ledger.get_total_pnl(),
            "daily_pnl_usd": self.pnl_ledger.get_daily_pnl(),
            "win_rate": self.pnl_ledger.get_win_rate(),
            "average_trade_size_usd": self.pnl_ledger.get_average_trade_size(),
            "exchange_status": {
                name: "connected" if conn else "disconnected"
                for name, conn in self.exchange_connectors.items()
            }
        }

class QuantumArbAgentPhase4Simple:
    """Simplified Phase 4 QuantumArb agent."""
    
    def __init__(self, poll_interval: float = 2.0, config_path: Optional[str] = None):
        self.poll_interval = poll_interval
        self.config_path = config_path
        self.engine = QuantumArbEnginePhase4Simple(config_path)
        
        # Agent directories
        self.base_dir = Path("data/quantumarb_phase4_simple")
        self.inbox_dir = self.base_dir / "inbox"
        self.outbox_dir = self.base_dir / "outbox"
        self._ensure_dirs()
        
        logger.info(f"QuantumArbAgentPhase4Simple initialized with poll interval {poll_interval}s")
    
    def _ensure_dirs(self):
        """Ensure agent directories exist."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
    
    async def run(self):
        """Main agent loop."""
        logger.info("Starting QuantumArbAgentPhase4Simple...")
        
        try:
            while True:
                # Process inbox
                self._process_inbox()
                
                # Log performance metrics periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    self._log_performance()
                
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
            
            # If approved, execute asynchronously
            if opportunity.decision == ArbDecision.EXECUTE:
                asyncio.create_task(self._execute_approved_opportunity(opportunity))
            
            # Write result
            result_file = self._write_result(signal, opportunity)
            logger.info(f"Processed signal {signal.signal_id}, result: {result_file}")
            
        except Exception as e:
            logger.error(f"Error processing arbitrage signal: {e}")
    
    async def _execute_approved_opportunity(self, opportunity: ArbitrageOpportunity):
        """Execute approved opportunity asynchronously."""
        try:
            result = await self.engine.execute_opportunity(opportunity)
            
            # Log execution result
            if result.success:
                logger.info(f"Execution successful: P&L ${result.total_pnl_usd:.4f}")
            else:
                logger.error(f"Execution failed: {result.error}")
            
            # Create execution report
            report = {
                "opportunity_id": opportunity.opportunity_id,
                "execution_time": datetime.utcnow().isoformat(),
                "result": result.to_dict(),
                "performance_impact": self.engine.get_performance_metrics()
            }
            
            # Save report
            report_file = self.outbox_dir / f"execution_{opportunity.opportunity_id}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error in async execution: {e}")
    
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
                "components": {
                    "engine": "operational",
                    "exchanges": len(self.engine.exchange_connectors),
                    "pnl_ledger": "operational"
                }
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
    
    def _log_performance(self):
        """Log performance metrics periodically."""
        metrics = self.engine.get_performance_metrics()
        logger.info(f"Performance: {metrics['trades_executed']} trades, P&L: ${metrics['total_pnl_usd']:.4f}")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="QuantumArb Agent Phase 4 Simple")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--poll-interval", type=float, default=2.0,
                       help="Poll interval in seconds")
    
    args = parser.parse_args()
    
    # Create and run agent
    agent = QuantumArbAgentPhase4Simple(
        poll_interval=args.poll_interval,
        config_path=args.config
    )
    
    # Run agent
    asyncio.run(agent.run())

if __name__ == "__main__":
    main()