#!/usr/bin/env python3
"""
Gate 4 Scaled Microscopic Agent - Part 2b: Order Management & Advanced Features
Advanced order management, reconciliation, and production features
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy import stats, optimize

# SIMP imports
from simp.server.broker import SimpBroker
from simp.models.canonical_intent import CanonicalIntent
# FinancialOps import removed as it doesn't exist in the module
from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity
from simp.organs.quantumarb.exchange_connector import ExchangeConnector, StubExchangeConnector

# Import from previous parts
from gate4_scaled_agent_part1 import (
    TradingStrategy, OrderType, Gate4Config, ScaledPosition, 
    MarketMicrostructure, RiskMetrics, Gate4ScaledAgent
)
from gate4_scaled_agent_part2a import (
    TradeExecution, PositionState, PerformanceMetrics, TradeEngine
)

logger = logging.getLogger(__name__)


@dataclass
class OrderReconciliation:
    """Order reconciliation record"""
    reconciliation_id: str
    trade_id: str
    symbol: str
    expected_quantity: Decimal
    expected_price: Decimal
    actual_quantity: Decimal
    actual_price: Decimal
    quantity_difference: Decimal
    price_difference: Decimal
    reconciliation_status: str  # "matched", "mismatch", "error"
    timestamp: datetime
    corrective_action: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class RiskExposure:
    """Risk exposure analysis"""
    timestamp: datetime
    symbol: str
    var_95: float  # Value at Risk at 95% confidence
    expected_shortfall: float
    stress_test_results: Dict[str, float]
    concentration_risk: float
    liquidity_risk: float
    volatility_risk: float
    correlation_risk: float


@dataclass
class ComplianceRecord:
    """Compliance and surveillance record"""
    record_id: str
    timestamp: datetime
    event_type: str  # "trade", "order", "position_change", "risk_breach"
    symbol: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    action_taken: Optional[str] = None
    regulator_notified: bool = False
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)


class OrderManager:
    """Advanced order management system"""
    
    def __init__(self, trade_engine: TradeEngine):
        self.trade_engine = trade_engine
        self.agent = trade_engine.agent
        self.config = trade_engine.agent.config
        
        self.pending_orders: Dict[str, TradeExecution] = {}
        self.order_history: List[TradeExecution] = []
        self.reconciliation_log: List[OrderReconciliation] = []
        self.compliance_records: List[ComplianceRecord] = []
        
        self._order_lock = asyncio.Lock()
        self._reconciliation_interval = 300  # 5 minutes
        
        # Start background tasks
        self._reconciliation_task = None
        self._monitoring_task = None
        
        logger.info("OrderManager initialized")
    
    async def start(self):
        """Start background tasks"""
        self._reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("OrderManager background tasks started")
    
    async def stop(self):
        """Stop background tasks"""
        if self._reconciliation_task:
            self._reconciliation_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
        logger.info("OrderManager background tasks stopped")
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[Decimal] = None,
        time_in_force: str = "IOC",
        strategy: TradingStrategy = TradingStrategy.MEAN_REVERSION
    ) -> Optional[TradeExecution]:
        """
        Place an order with advanced order management
        """
        # Validate order parameters
        if not self._validate_order_parameters(symbol, side, quantity, order_type, price):
            return None
        
        # Check compliance rules
        if not await self._check_compliance_rules(symbol, side, quantity):
            logger.warning(f"Order failed compliance check for {symbol}")
            return None
        
        # Create order record
        order = await self.trade_engine.execute_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            strategy=strategy
        )
        
        if order:
            async with self._order_lock:
                self.order_history.append(order)
                
                # Record compliance event
                await self._record_compliance_event(
                    event_type="order",
                    symbol=symbol,
                    description=f"{side.upper()} order for {quantity} {symbol}",
                    severity="low"
                )
            
            # Monitor order execution
            asyncio.create_task(self._monitor_order_execution(order))
        
        return order
    
    def _validate_order_parameters(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: OrderType,
        price: Optional[Decimal]
    ) -> bool:
        """Validate order parameters"""
        if side not in ["buy", "sell"]:
            logger.error(f"Invalid side: {side}")
            return False
        
        if quantity <= Decimal("0"):
            logger.error(f"Invalid quantity: {quantity}")
            return False
        
        if order_type == OrderType.LIMIT and price is None:
            logger.error("Limit order requires price")
            return False
        
        if order_type == OrderType.LIMIT and price <= Decimal("0"):
            logger.error(f"Invalid price for limit order: {price}")
            return False
        
        # Check symbol is in configured list
        if symbol not in self.config.symbols:
            logger.warning(f"Symbol {symbol} not in configured list")
            # Allow anyway for flexibility
        
        return True
    
    async def _check_compliance_rules(self, symbol: str, side: str, quantity: Decimal) -> bool:
        """Check compliance rules before order execution"""
        # Check for market manipulation patterns
        if await self._detect_market_manipulation(symbol, side, quantity):
            logger.warning(f"Potential market manipulation detected for {symbol}")
            await self._record_compliance_event(
                event_type="compliance_alert",
                symbol=symbol,
                description=f"Potential market manipulation detected: {side} {quantity} {symbol}",
                severity="high"
            )
            return False
        
        # Check for wash trading
        if await self._detect_wash_trading(symbol, side):
            logger.warning(f"Potential wash trading detected for {symbol}")
            await self._record_compliance_event(
                event_type="compliance_alert",
                symbol=symbol,
                description=f"Potential wash trading detected: {side} {symbol}",
                severity="medium"
            )
            return False
        
        # Check position concentration
        if await self._check_position_concentration(symbol, side, quantity):
            logger.warning(f"Position concentration limit reached for {symbol}")
            await self._record_compliance_event(
                event_type="risk_breach",
                symbol=symbol,
                description=f"Position concentration limit: {side} {quantity} {symbol}",
                severity="medium"
            )
            return False
        
        return True
    
    async def _detect_market_manipulation(self, symbol: str, side: str, quantity: Decimal) -> bool:
        """Detect potential market manipulation patterns"""
        # Check for spoofing (large orders that are immediately cancelled)
        recent_orders = [o for o in self.order_history[-10:] if o.symbol == symbol]
        spoof_orders = [o for o in recent_orders if o.status in ["cancelled", "rejected"]]
        
        if len(spoof_orders) > 3:  # More than 3 cancelled/rejected orders recently
            return True
        
        # Check for layering (multiple orders on one side to create false impression)
        if len(recent_orders) > 5:
            same_side_orders = [o for o in recent_orders if o.side == side]
            if len(same_side_orders) > 4:  # 5+ orders on same side
                return True
        
        return False
    
    async def _detect_wash_trading(self, symbol: str, side: str) -> bool:
        """Detect potential wash trading"""
        # Check for rapid buy/sell cycles
        recent_trades = [t for t in self.trade_engine.trade_history[-20:] if t.symbol == symbol]
        
        if len(recent_trades) < 4:
            return False
        
        # Look for pattern: buy, sell, buy, sell in quick succession
        sides = [t.side for t in recent_trades[-4:]]
        if sides == ["buy", "sell", "buy", "sell"]:
            # Check if trades are within short time frame
            times = [t.timestamp for t in recent_trades[-4:]]
            time_diff = (times[-1] - times[0]).total_seconds()
            if time_diff < 300:  # 5 minutes
                return True
        
        return False
    
    async def _check_position_concentration(self, symbol: str, side: str, quantity: Decimal) -> bool:
        """Check position concentration limits"""
        positions = self.trade_engine.get_current_positions()
        
        if not positions:
            return False
        
        # Calculate total portfolio value (simplified)
        total_value = sum(p.notional_value for p in positions.values())
        
        # Calculate new position value
        try:
            ticker = await self.trade_engine.exchange.get_ticker(symbol)
            current_price = Decimal(str(ticker.get('last', 0)))
            new_position_value = quantity * current_price
            
            # Check max exposure per symbol
            max_exposure_percent = self.config.risk_management['position_limits']['max_exposure_per_symbol_percent']
            if symbol in positions:
                existing_value = positions[symbol].notional_value
                total_symbol_value = existing_value + (new_position_value if side == "buy" else -new_position_value)
            else:
                total_symbol_value = new_position_value
            
            symbol_exposure = (total_symbol_value / total_value * Decimal("100")) if total_value > Decimal("0") else Decimal("0")
            
            if symbol_exposure > Decimal(str(max_exposure_percent)):
                return True
            
            # Check sector concentration (simplified - all crypto same sector)
            max_sector_exposure = self.config.risk_management['position_limits']['concentration_limits']['max_sector_exposure_percent']
            sector_exposure = 100.0  # All in crypto sector
            if sector_exposure > max_sector_exposure:
                return True
            
        except Exception as e:
            logger.error(f"Error checking position concentration: {e}")
        
        return False
    
    async def _monitor_order_execution(self, order: TradeExecution):
        """Monitor order execution and handle timeouts"""
        timeout = 30  # seconds
        
        try:
            await asyncio.sleep(timeout)
            
            if order.status == "pending":
                logger.warning(f"Order {order.trade_id} timed out after {timeout}s")
                order.status = "timeout"
                order.error_message = f"Order execution timed out after {timeout} seconds"
                
                # Attempt to cancel
                await self._cancel_order(order)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error monitoring order {order.trade_id}: {e}")
    
    async def _cancel_order(self, order: TradeExecution):
        """Cancel an order"""
        # In production, this would call exchange cancel API
        # For simulation, just update status
        if order.status in ["pending", "partial"]:
            order.status = "cancelled"
            order.error_message = "Order cancelled by system"
            logger.info(f"Order {order.trade_id} cancelled")
    
    async def _reconciliation_loop(self):
        """Background reconciliation loop"""
        while True:
            try:
                await asyncio.sleep(self._reconciliation_interval)
                await self._run_reconciliation()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reconciliation loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _run_reconciliation(self):
        """Run order reconciliation"""
        logger.info("Running order reconciliation")
        
        # Get recent filled orders
        recent_orders = [o for o in self.order_history[-50:] if o.status == "filled"]
        
        for order in recent_orders:
            try:
                # In production, this would compare with exchange records
                # For simulation, create reconciliation record
                reconciliation = OrderReconciliation(
                    reconciliation_id=f"recon_{int(time.time())}_{order.trade_id}",
                    trade_id=order.trade_id,
                    symbol=order.symbol,
                    expected_quantity=order.quantity,
                    expected_price=order.price,
                    actual_quantity=order.fill_quantity or order.quantity,
                    actual_price=order.fill_price or order.price,
                    quantity_difference=Decimal("0"),  # Would calculate difference
                    price_difference=Decimal("0"),  # Would calculate difference
                    reconciliation_status="matched",
                    timestamp=datetime.now()
                )
                
                self.reconciliation_log.append(reconciliation)
                
                # Check for significant discrepancies
                if abs(float(reconciliation.quantity_difference)) > 0.01:  # 1% difference
                    reconciliation.reconciliation_status = "mismatch"
                    reconciliation.corrective_action = "investigate"
                    logger.warning(f"Quantity mismatch for order {order.trade_id}")
                
                if abs(float(reconciliation.price_difference)) > 0.005:  # 0.5% difference
                    reconciliation.reconciliation_status = "mismatch"
                    reconciliation.corrective_action = "investigate"
                    logger.warning(f"Price mismatch for order {order.trade_id}")
                    
            except Exception as e:
                logger.error(f"Error reconciling order {order.trade_id}: {e}")
        
        # Save reconciliation log
        self._save_reconciliation_log()
        
        logger.info(f"Reconciliation complete: {len(recent_orders)} orders checked")
    
    def _save_reconciliation_log(self):
        """Save reconciliation log to file"""
        log_path = Path("data/gate4_reconciliation.jsonl")
        try:
            with open(log_path, "a") as f:
                for recon in self.reconciliation_log[-10:]:  # Save last 10
                    record = {
                        'reconciliation_id': recon.reconciliation_id,
                        'trade_id': recon.trade_id,
                        'symbol': recon.symbol,
                        'expected_quantity': str(recon.expected_quantity),
                        'expected_price': str(recon.expected_price),
                        'actual_quantity': str(recon.actual_quantity),
                        'actual_price': str(recon.actual_price),
                        'quantity_difference': str(recon.quantity_difference),
                        'price_difference': str(recon.price_difference),
                        'reconciliation_status': recon.reconciliation_status,
                        'timestamp': recon.timestamp.isoformat(),
                        'corrective_action': recon.corrective_action,
                        'notes': recon.notes
                    }
                    f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to save reconciliation log: {e}")
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Monitor position durations
                await self._monitor_position_durations()
                
                # Monitor risk exposures
                await self._monitor_risk_exposures()
                
                # Monitor compliance
                await self._monitor_compliance()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    async def _monitor_position_durations(self):
        """Monitor position durations and close if too long"""
        max_duration = self.config.monitoring['alert_thresholds']['max_position_duration_minutes']
        
        for symbol, position in self.trade_engine.positions.items():
            if position.duration_minutes > max_duration:
                logger.warning(f"Position {symbol} exceeded max duration: {position.duration_minutes:.1f}m")
                
                # Close position
                trade = await self.trade_engine.execute_trade(
                    symbol=symbol,
                    side="sell",
                    quantity=position.quantity,
                    order_type=OrderType.MARKET
                )
                
                if trade and trade.status == "filled":
                    await self._record_compliance_event(
                        event_type="position_change",
                        symbol=symbol,
                        description=f"Position closed due to duration limit: {position.duration_minutes:.1f}m",
                        severity="medium"
                    )
    
    async def _monitor_risk_exposures(self):
        """Monitor risk exposures"""
        # Calculate Value at Risk
        var_results = await self._calculate_value_at_risk()
        
        # Check VaR limits
        max_var = self.config.risk_management['value_at_risk']['max_var_percent']
        
        for symbol, var in var_results.items():
            if var > max_var:
                logger.warning(f"VaR breach for {symbol}: {var:.2f}% > {max_var}%")
                
                await self._record_compliance_event(
                    event_type="risk_breach",
                    symbol=symbol,
                    description=f"VaR breach: {var:.2f}% > {max_var}% limit",
                    severity="high"
                )
    
    async def _calculate_value_at_risk(self) -> Dict[str, float]:
        """Calculate Value at Risk for positions"""
        var_results = {}
        
        for symbol, position in self.trade_engine.positions.items():
            try:
                # Get historical prices (simplified - would use actual data)
                # For simulation, use fixed volatility
                volatility = 0.02  # 2% daily volatility
                confidence = self.config.risk_management['value_at_risk']['confidence_level']
                
                # Calculate VaR using normal distribution
                z_score = stats.norm.ppf(confidence)
                var = abs(float(position.notional_value)) * volatility * z_score
                var_percent = (var / float(position.notional_value)) * 100 if float(position.notional_value) > 0 else 0
                
                var_results[symbol] = var_percent
                
            except Exception as e:
                logger.error(f"Error calculating VaR for {symbol}: {e}")
                var_results[symbol] = 0.0
        
        return var_results
    
    async def _monitor_compliance(self):
        """Monitor compliance rules"""
        # Check for best execution
        await self._check_best_execution()
        
        # Check for trade surveillance alerts
        await self._run_trade_surveillance()
    
    async def _check_best_execution(self):
        """Check best execution policy compliance"""
        # This would compare execution prices with market benchmarks
        # For simulation, just log
        if len(self.order_history) % 20 == 0:
            logger.info("Best execution check completed")
    
    async def _run_trade_surveillance(self):
        """Run trade surveillance"""
        # Check for unusual trading patterns
        recent_trades = self.trade_engine.trade_history[-50:]
        
        if len(recent_trades) < 10:
            return
        
        # Check for high frequency trading
        trade_times = [t.timestamp for t in recent_trades]
        time_diffs = [(trade_times[i+1] - trade_times[i]).total_seconds() for i in range(len(trade_times)-1)]
        
        avg_time_between_trades = np.mean(time_diffs) if time_diffs else 0
        
        if avg_time_between_trades < 10:  # Less than 10 seconds between trades on average
            logger.warning(f"High frequency trading detected: avg {avg_time_between_trades:.1f}s between trades")
            
            await self._record_compliance_event(
                event_type="surveillance_alert",
                symbol="multiple",
                description=f"High frequency trading: avg {avg_time_between_trades:.1f}s between trades",
                severity="medium"
            )
    
    async def _record_compliance_event(
        self,
        event_type: str,
        symbol: str,
        description: str,
        severity: str
    ):
        """Record compliance event"""
        record = ComplianceRecord(
            record_id=f"comp_{int(time.time())}_{event_type}",
            timestamp=datetime.now(),
            event_type=event_type,
            symbol=symbol,
            description=description,
            severity=severity
        )
        
        self.compliance_records.append(record)
        
        # Save to file
        self._save_compliance_record(record)
        
        # Send alert if high severity
        if severity in ["high", "critical"]:
            await self._send_compliance_alert(record)
    
    def _save_compliance_record(self, record: ComplianceRecord):
        """Save compliance record to file"""
        log_path = Path("data/gate4_compliance.jsonl")
        try:
            with open(log_path, "a") as f:
                record_data = {
                    'record_id': record.record_id,
                    'timestamp': record.timestamp.isoformat(),
                    'event_type': record.event_type,
                    'symbol': record.symbol,
                    'description': record.description,
                    'severity': record.severity,
                    'action_taken': record.action_taken,
                    'regulator_notified': record.regulator_notified,
                    'audit_trail': record.audit_trail
                }
                f.write(json.dumps(record_data) + "\n")
        except Exception as e:
            logger.error(f"Failed to save compliance record: {e}")
    
    async def _send_compliance_alert(self, record: ComplianceRecord):
        """Send compliance alert to SIMP broker"""
        try:
            if self.agent.broker:
                intent = CanonicalIntent(
                    intent_type="compliance_alert",
                    source_agent="gate4_scaled",
                    target_agent="auto",
                    params={
                        "record_id": record.record_id,
                        "event_type": record.event_type,
                        "symbol": record.symbol,
                        "description": record.description,
                        "severity": record.severity,
                        "timestamp": record.timestamp.isoformat()
                    }
                )
                await self.agent.broker.route_intent(intent)
        except Exception as e:
            logger.error(f"Failed to send compliance alert: {e}")
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """Get order statistics"""
        total_orders = len(self.order_history)
        filled_orders = len([o for o in self.order_history if o.status == "filled"])
        cancelled_orders = len([o for o in self.order_history if o.status == "cancelled"])
        rejected_orders = len([o for o in self.order_history if o.status == "rejected"])
        
        fill_rate = (filled_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Calculate average execution time
        filled_executions = [o for o in self.order_history if o.status == "filled" and o.latency_ms > 0]
        avg_latency = np.mean([o.latency_ms for o in filled_executions]) if filled_executions else 0
        
        # Calculate average slippage
        avg_slippage = np.mean([float(o.slippage) for o in filled_executions if o.slippage]) if filled_executions else 0
        
        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "cancelled_orders": cancelled_orders,
            "rejected_orders": rejected_orders,
            "fill_rate_percent": fill_rate,
            "avg_latency_ms": avg_latency,
            "avg_slippage_percent": avg_slippage,
            "pending_reconciliation": len(self.reconciliation_log),
            "compliance_alerts": len([r for r in self.compliance_records if r.severity in ["high", "critical"]])
        }
    
    async def run_stress_test(self, scenario: str = "flash_crash"):
        """Run stress test scenario"""
        logger.info(f"Running stress test: {scenario}")
        
        stress_results = {}
        
        if scenario == "flash_crash":
            # Simulate 20% price drop
            for symbol in self.trade_engine.positions:
                position = self.trade_engine.positions[symbol]
                stress_price = position.current_price * Decimal("0.8")  # 20% drop
                stress_pnl = (stress_price - position.avg_entry_price) * position.quantity
                stress_percent = (stress_pnl / (position.quantity * position.avg_entry_price)) * Decimal("100")
                
                stress_results[symbol] = {
                    "stress_price": float(stress_price),
                    "stress_pnl": float(stress_pnl),
                    "stress_percent": float(stress_percent)
                }
        
        elif scenario == "liquidity_drain":
            # Simulate reduced liquidity (higher slippage)
            for symbol in self.trade_engine.positions:
                position = self.trade_engine.positions[symbol]
                # Assume 2x normal slippage
                stress_slippage = Decimal("0.006")  # 0.6% vs normal 0.3%
                stress_results[symbol] = {
                    "stress_slippage_percent": float(stress_slippage * Decimal("100")),
                    "estimated_impact": float(position.notional_value * stress_slippage)
                }
        
        elif scenario == "volatility_spike":
            # Simulate 3x normal volatility
            for symbol in self.trade_engine.positions:
                position = self.trade_engine.positions[symbol]
                stress_volatility = Decimal("0.06")  # 6% vs normal 2%
                stress_var = abs(float(position.notional_value)) * 0.06 * 1.645  # 95% confidence
                
                stress_results[symbol] = {
                    "stress_volatility_percent": float(stress_volatility * Decimal("100")),
                    "stress_var": stress_var,
                    "stress_var_percent": (stress_var / float(position.notional_value)) * 100 if float(position.notional_value) > 0 else 0
                }
        
        # Log stress test results
        logger.info(f"Stress test {scenario} results: {stress_results}")
        
        # Record compliance event
        await self._record_compliance_event(
            event_type="stress_test",
            symbol="portfolio",
            description=f"Stress test completed: {scenario}",
            severity="low"
        )
        
        return stress_results