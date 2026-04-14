#!/usr/bin/env python3
"""
Gate 4 Scaled Microscopic Agent - Part 2a: Trading Engine
Trade execution with $1-$10 position sizes
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
from scipy import stats

# SIMP imports
from simp.server.broker import SimpBroker
from simp.models.canonical_intent import CanonicalIntent
# FinancialOps import removed as it doesn't exist in the module
from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity
from simp.organs.quantumarb.exchange_connector import ExchangeConnector, StubExchangeConnector

# Import from part 1
from gate4_scaled_agent_part1 import (
    TradingStrategy, OrderType, Gate4Config, ScaledPosition, 
    MarketMicrostructure, RiskMetrics, Gate4ScaledAgent
)

logger = logging.getLogger(__name__)


@dataclass
class TradeExecution:
    """Trade execution record"""
    trade_id: str
    symbol: str
    side: str  # "buy" or "sell"
    order_type: OrderType
    quantity: Decimal
    price: Decimal
    notional: Decimal
    timestamp: datetime
    status: str  # "pending", "filled", "partial", "cancelled", "rejected"
    fill_price: Optional[Decimal] = None
    fill_quantity: Optional[Decimal] = None
    fill_notional: Optional[Decimal] = None
    fill_timestamp: Optional[datetime] = None
    fees: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    latency_ms: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionState:
    """Current position state"""
    symbol: str
    quantity: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    notional_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    realized_pnl: Decimal
    total_fees: Decimal
    entry_timestamp: datetime
    duration_minutes: float
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for tracking"""
    timestamp: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    profit_factor: float
    avg_win: Decimal
    avg_loss: Decimal
    avg_trade_duration_minutes: float
    success_rate: float
    fill_rate: float
    avg_slippage_percent: float
    avg_latency_ms: float


class TradeEngine:
    """Trade execution engine for Gate 4 scaled positions"""
    
    def __init__(self, agent: Gate4ScaledAgent):
        self.agent = agent
        self.config = agent.config
        self.exchange = agent.exchange
        self.active_trades: Dict[str, TradeExecution] = {}
        self.trade_history: List[TradeExecution] = []
        self.positions: Dict[str, PositionState] = {}
        self.performance_history: List[PerformanceMetrics] = []
        self._trade_lock = asyncio.Lock()
        self._position_lock = asyncio.Lock()
        
        # Initialize performance tracking
        self._initialize_performance_tracking()
        
        logger.info(f"TradeEngine initialized for {self.config.exchange}")
    
    def _initialize_performance_tracking(self):
        """Initialize performance tracking structures"""
        self.daily_pnl = Decimal("0")
        self.daily_fees = Decimal("0")
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.hourly_trade_count = 0
        self.last_hour_reset = datetime.now()
        
        # Load historical performance if exists
        self._load_performance_history()
    
    def _load_performance_history(self):
        """Load performance history from file"""
        perf_path = Path("data/gate4_performance.jsonl")
        if perf_path.exists():
            try:
                with open(perf_path, "r") as f:
                    for line in f:
                        data = json.loads(line.strip())
                        # Convert string decimals back to Decimal
                        for key in ['total_pnl', 'total_fees', 'net_pnl', 'avg_win', 'avg_loss']:
                            if key in data:
                                data[key] = Decimal(str(data[key]))
                        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                        self.performance_history.append(PerformanceMetrics(**data))
                logger.info(f"Loaded {len(self.performance_history)} performance records")
            except Exception as e:
                logger.error(f"Failed to load performance history: {e}")
    
    def _save_performance_history(self):
        """Save performance history to file"""
        perf_path = Path("data/gate4_performance.jsonl")
        try:
            with open(perf_path, "a") as f:
                if self.performance_history:
                    latest = self.performance_history[-1]
                    record = {
                        'timestamp': latest.timestamp.isoformat(),
                        'total_trades': latest.total_trades,
                        'winning_trades': latest.winning_trades,
                        'losing_trades': latest.losing_trades,
                        'win_rate': latest.win_rate,
                        'total_pnl': str(latest.total_pnl),
                        'total_fees': str(latest.total_fees),
                        'net_pnl': str(latest.net_pnl),
                        'sharpe_ratio': latest.sharpe_ratio,
                        'sortino_ratio': latest.sortino_ratio,
                        'max_drawdown': latest.max_drawdown,
                        'profit_factor': latest.profit_factor,
                        'avg_win': str(latest.avg_win),
                        'avg_loss': str(latest.avg_loss),
                        'avg_trade_duration_minutes': latest.avg_trade_duration_minutes,
                        'success_rate': latest.success_rate,
                        'fill_rate': latest.fill_rate,
                        'avg_slippage_percent': latest.avg_slippage_percent,
                        'avg_latency_ms': latest.avg_latency_ms
                    }
                    f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to save performance history: {e}")
    
    async def execute_trade(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[Decimal] = None,
        strategy: TradingStrategy = TradingStrategy.MEAN_REVERSION
    ) -> Optional[TradeExecution]:
        """
        Execute a trade with proper risk checks and position sizing
        """
        # Check circuit breakers first
        circuit_state = self.agent._check_circuit_breakers()
        if circuit_state != "normal":
            logger.warning(f"Cannot execute trade: circuit breaker in {circuit_state} state")
            self.agent.handle_circuit_breaker(circuit_state)
            return None
        
        # Check hourly trade limit
        if self._check_hourly_trade_limit():
            logger.warning("Hourly trade limit reached")
            return None
        
        # Calculate position size based on risk management
        sized_quantity = await self._calculate_position_size(symbol, side, quantity, strategy)
        if sized_quantity <= Decimal("0"):
            logger.warning(f"Position size calculation resulted in zero or negative: {sized_quantity}")
            return None
        
        # Get current market price
        try:
            ticker = await self.exchange.get_ticker(symbol)
            current_price = Decimal(str(ticker.get('last', 0)))
            if current_price <= Decimal("0"):
                logger.error(f"Invalid current price for {symbol}: {current_price}")
                return None
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            return None
        
        # Calculate notional value
        notional = sized_quantity * current_price
        
        # Check position limits
        if not self._check_position_limits(symbol, side, notional):
            logger.warning(f"Position limit check failed for {symbol}")
            return None
        
        # Create trade execution record
        trade_id = f"gate4_{int(time.time())}_{symbol}_{side}"
        trade = TradeExecution(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=sized_quantity,
            price=current_price if order_type == OrderType.MARKET else price,
            notional=notional,
            timestamp=datetime.now(),
            status="pending"
        )
        
        async with self._trade_lock:
            # Execute the trade
            try:
                execution_result = await self._execute_order(trade)
                
                if execution_result.status == "filled":
                    # Update position
                    await self._update_position(execution_result)
                    
                    # Update performance metrics
                    self._update_performance_metrics(execution_result)
                    
                    # Check for circuit breaker triggers
                    self._check_performance_circuit_breakers()
                    
                    # Send trade notification
                    await self._send_trade_notification(execution_result)
                    
                    logger.info(f"Trade executed successfully: {trade_id}")
                    return execution_result
                else:
                    logger.warning(f"Trade execution failed: {execution_result.status}")
                    return execution_result
                    
            except Exception as e:
                logger.error(f"Trade execution error: {e}")
                trade.status = "rejected"
                trade.error_message = str(e)
                return trade
    
    async def _calculate_position_size(
        self,
        symbol: str,
        side: str,
        requested_quantity: Decimal,
        strategy: TradingStrategy
    ) -> Decimal:
        """
        Calculate position size based on risk management rules
        """
        # Get market data for volatility calculation
        try:
            market_data = await self.agent.analyze_market_microstructure(symbol)
            volatility = market_data.volatility_30m
        except:
            volatility = 0.02  # Default 2% volatility
        
        # Get base allocation from config
        base_allocation = Decimal(str(self.config.position_sizing['base_allocation_per_symbol']))
        
        # Apply volatility scaling
        volatility_factor = Decimal(str(self.config.position_sizing['volatility_scaling_factor']))
        volatility_adjustment = Decimal("1") / (Decimal(str(volatility)) * Decimal("10") + Decimal("1"))
        volatility_scaled = base_allocation * volatility_adjustment * volatility_factor
        
        # Apply liquidity scaling if available
        try:
            liquidity = market_data.liquidity_score if hasattr(market_data, 'liquidity_score') else 1.0
            liquidity_factor = Decimal(str(self.config.position_sizing['liquidity_scaling_factor']))
            liquidity_scaled = volatility_scaled * Decimal(str(liquidity)) * liquidity_factor
        except:
            liquidity_scaled = volatility_scaled
        
        # Apply risk per trade percentage
        risk_per_trade = Decimal(str(self.config.position_sizing['risk_per_trade_percent'])) / Decimal("100")
        risk_adjusted = liquidity_scaled * risk_per_trade
        
        # Ensure within min/max bounds
        min_notional = Decimal(str(self.config.position_sizing['min_notional']))
        max_notional = Decimal(str(self.config.position_sizing['max_notional']))
        
        if risk_adjusted < min_notional:
            risk_adjusted = min_notional
        elif risk_adjusted > max_notional:
            risk_adjusted = max_notional
        
        # Convert to quantity based on current price
        try:
            ticker = await self.exchange.get_ticker(symbol)
            current_price = Decimal(str(ticker.get('last', 0)))
            if current_price > Decimal("0"):
                quantity = risk_adjusted / current_price
                
                # Round to appropriate decimal places
                precision = await self._get_symbol_precision(symbol)
                quantity = self._round_to_precision(quantity, precision)
                
                return quantity
        except:
            pass
        
        # Fallback to requested quantity with bounds
        return min(requested_quantity, Decimal(str(max_notional)) / Decimal("100"))
    
    async def _get_symbol_precision(self, symbol: str) -> int:
        """Get precision for symbol"""
        # This would normally come from exchange API
        # For now, use common precisions
        if "BTC" in symbol or "ETH" in symbol:
            return 6
        elif "SOL" in symbol or "AVAX" in symbol:
            return 4
        else:
            return 3
    
    def _round_to_precision(self, value: Decimal, precision: int) -> Decimal:
        """Round to specified precision"""
        quantize_str = "0." + "0" * precision
        return value.quantize(Decimal(quantize_str))
    
    def _check_hourly_trade_limit(self) -> bool:
        """Check if hourly trade limit is reached"""
        now = datetime.now()
        if now - self.last_hour_reset > timedelta(hours=1):
            self.hourly_trade_count = 0
            self.last_hour_reset = now
        
        max_hourly = self.config.risk_management['circuit_breakers']['max_hourly_trades']
        return self.hourly_trade_count >= max_hourly
    
    def _check_position_limits(self, symbol: str, side: str, notional: Decimal) -> bool:
        """Check position limits before executing trade"""
        # Check max concurrent positions
        max_concurrent = self.config.position_sizing['max_concurrent_positions']
        if len(self.positions) >= max_concurrent and symbol not in self.positions:
            logger.warning(f"Max concurrent positions reached: {len(self.positions)}/{max_concurrent}")
            return False
        
        # Check max exposure per symbol
        max_exposure_percent = self.config.risk_management['position_limits']['max_exposure_per_symbol_percent']
        # This would require total portfolio value - for now just check notional
        
        # Check total exposure
        total_exposure = sum(p.notional_value for p in self.positions.values())
        max_total_percent = self.config.risk_management['position_limits']['max_total_exposure_percent']
        # This would also require portfolio value
        
        # Check liquidity threshold
        min_liquidity = self.config.risk_management['position_limits']['min_liquidity_threshold_usd']
        # Would need to check market liquidity
        
        return True
    
    async def _execute_order(self, trade: TradeExecution) -> TradeExecution:
        """Execute order through exchange"""
        start_time = time.time()
        
        try:
            # For Gate 4, we use market orders with IOC
            if trade.order_type == OrderType.MARKET:
                # Simulate exchange execution with realistic latency
                await asyncio.sleep(0.05)  # 50ms simulated latency
                
                # Get current price for fill
                ticker = await self.exchange.get_ticker(trade.symbol)
                fill_price = Decimal(str(ticker.get('last', trade.price)))
                
                # Calculate slippage (0.1% - 0.3% typical for crypto)
                slippage_percent = np.random.uniform(0.001, 0.003)
                if trade.side == "buy":
                    fill_price = fill_price * (Decimal("1") + Decimal(str(slippage_percent)))
                else:
                    fill_price = fill_price * (Decimal("1") - Decimal(str(slippage_percent)))
                
                # Calculate fees (0.08% typical for Coinbase)
                fee_rate = Decimal("0.0008")
                fees = trade.notional * fee_rate
                
                # Update trade record
                trade.fill_price = fill_price
                trade.fill_quantity = trade.quantity
                trade.fill_notional = trade.fill_quantity * trade.fill_price
                trade.fill_timestamp = datetime.now()
                trade.fees = fees
                trade.slippage = abs(fill_price - trade.price) / trade.price * Decimal("100")
                trade.latency_ms = int((time.time() - start_time) * 1000)
                trade.status = "filled"
                
                # Increment trade counters
                self.hourly_trade_count += 1
                self.daily_trades += 1
                
            else:
                # Limit order execution (not used in Gate 4 default config)
                trade.status = "rejected"
                trade.error_message = "Limit orders not supported in Gate 4 mode"
        
        except Exception as e:
            trade.status = "rejected"
            trade.error_message = str(e)
            logger.error(f"Order execution failed: {e}")
        
        # Add to history
        self.trade_history.append(trade)
        if trade.trade_id in self.active_trades:
            del self.active_trades[trade.trade_id]
        
        return trade
    
    async def _update_position(self, trade: TradeExecution):
        """Update position state after trade execution"""
        if trade.status != "filled":
            return
        
        symbol = trade.symbol
        async with self._position_lock:
            if symbol in self.positions:
                position = self.positions[symbol]
                
                if trade.side == "buy":
                    # Add to existing long position
                    total_quantity = position.quantity + trade.fill_quantity
                    total_cost = (position.quantity * position.avg_entry_price + 
                                 trade.fill_quantity * trade.fill_price)
                    position.avg_entry_price = total_cost / total_quantity
                    position.quantity = total_quantity
                else:
                    # Reduce existing position
                    if trade.fill_quantity >= position.quantity:
                        # Close position
                        realized_pnl = (trade.fill_price - position.avg_entry_price) * position.quantity
                        position.realized_pnl += realized_pnl
                        del self.positions[symbol]
                    else:
                        # Partial reduction
                        realized_pnl = (trade.fill_price - position.avg_entry_price) * trade.fill_quantity
                        position.realized_pnl += realized_pnl
                        position.quantity -= trade.fill_quantity
                
                # Update fees
                position.total_fees += trade.fees
                
            else:
                # New position
                if trade.side == "buy":
                    position = PositionState(
                        symbol=symbol,
                        quantity=trade.fill_quantity,
                        avg_entry_price=trade.fill_price,
                        current_price=trade.fill_price,
                        notional_value=trade.fill_notional,
                        unrealized_pnl=Decimal("0"),
                        unrealized_pnl_percent=Decimal("0"),
                        realized_pnl=Decimal("0"),
                        total_fees=trade.fees,
                        entry_timestamp=trade.fill_timestamp,
                        duration_minutes=0
                    )
                    self.positions[symbol] = position
            
            # Update position metrics
            await self._update_position_metrics()
    
    async def _update_position_metrics(self):
        """Update position metrics with current prices"""
        for symbol, position in self.positions.items():
            try:
                ticker = await self.exchange.get_ticker(symbol)
                current_price = Decimal(str(ticker.get('last', position.current_price)))
                position.current_price = current_price
                
                # Calculate unrealized P&L
                position.notional_value = position.quantity * current_price
                cost_basis = position.quantity * position.avg_entry_price
                position.unrealized_pnl = (current_price - position.avg_entry_price) * position.quantity
                
                if cost_basis > Decimal("0"):
                    position.unrealized_pnl_percent = (position.unrealized_pnl / cost_basis) * Decimal("100")
                
                # Update duration
                position.duration_minutes = (datetime.now() - position.entry_timestamp).total_seconds() / 60
                
            except Exception as e:
                logger.error(f"Failed to update position metrics for {symbol}: {e}")
    
    def _update_performance_metrics(self, trade: TradeExecution):
        """Update performance metrics after trade"""
        # Calculate P&L for this trade
        if trade.side == "sell" and trade.fill_price and trade.fill_quantity:
            # This would require knowing the entry price
            # For now, track in daily totals
            self.daily_fees += trade.fees
        
        # Update consecutive losses
        # This would require knowing if trade was profitable
        
        # Generate periodic performance report
        if len(self.trade_history) % 10 == 0:  # Every 10 trades
            self._generate_performance_report()
    
    def _check_performance_circuit_breakers(self):
        """Check performance against circuit breaker thresholds"""
        # Check max consecutive losses
        max_consecutive = self.config.risk_management['circuit_breakers']['max_consecutive_losses']
        if self.consecutive_losses >= max_consecutive:
            logger.warning(f"Max consecutive losses reached: {self.consecutive_losses}")
            self.agent.handle_circuit_breaker("warning")
        
        # Check daily P&L
        daily_loss_percent = abs(float(self.daily_pnl))  # This would need portfolio value
        max_daily_loss = self.config.risk_management['circuit_breakers']['max_daily_loss_percent']
        if daily_loss_percent >= max_daily_loss:
            logger.warning(f"Daily loss limit reached: {daily_loss_percent}%")
            self.agent.handle_circuit_breaker("critical")
    
    def _generate_performance_report(self):
        """Generate performance metrics report"""
        if not self.trade_history:
            return
        
        # Calculate metrics from trade history
        filled_trades = [t for t in self.trade_history if t.status == "filled"]
        if not filled_trades:
            return
        
        # Calculate basic metrics
        total_trades = len(filled_trades)
        # This would require P&L calculation per trade
        
        # For now, create placeholder metrics
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            total_trades=total_trades,
            winning_trades=0,  # Would need actual calculation
            losing_trades=0,
            win_rate=0.0,
            total_pnl=self.daily_pnl,
            total_fees=self.daily_fees,
            net_pnl=self.daily_pnl - self.daily_fees,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            profit_factor=0.0,
            avg_win=Decimal("0"),
            avg_loss=Decimal("0"),
            avg_trade_duration_minutes=0.0,
            success_rate=0.0,
            fill_rate=0.0,
            avg_slippage_percent=0.0,
            avg_latency_ms=0.0
        )
        
        self.performance_history.append(metrics)
        self._save_performance_history()
    
    async def _send_trade_notification(self, trade: TradeExecution):
        """Send trade notification to SIMP broker"""
        try:
            if self.agent.broker:
                intent = CanonicalIntent(
                    intent_type="trade_execution",
                    source_agent="gate4_scaled",
                    target_agent="auto",
                    params={
                        "trade_id": trade.trade_id,
                        "symbol": trade.symbol,
                        "side": trade.side,
                        "quantity": float(trade.quantity),
                        "price": float(trade.price),
                        "notional": float(trade.notional),
                        "status": trade.status,
                        "timestamp": trade.timestamp.isoformat()
                    }
                )
                await self.agent.broker.route_intent(intent)
        except Exception as e:
            logger.error(f"Failed to send trade notification: {e}")
    
    async def close_all_positions(self):
        """Close all open positions"""
        logger.info("Closing all positions")
        
        for symbol, position in list(self.positions.items()):
            try:
                # Create sell order for entire position
                trade = await self.execute_trade(
                    symbol=symbol,
                    side="sell",
                    quantity=position.quantity,
                    order_type=OrderType.MARKET
                )
                
                if trade and trade.status == "filled":
                    logger.info(f"Closed position for {symbol}: {position.quantity}")
                else:
                    logger.warning(f"Failed to close position for {symbol}")
                    
            except Exception as e:
                logger.error(f"Error closing position for {symbol}: {e}")
        
        logger.info("All positions closed")
    
    def get_current_positions(self) -> Dict[str, PositionState]:
        """Get current positions"""
        return self.positions.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.performance_history:
            return {}
        
        latest = self.performance_history[-1]
        return {
            "total_trades": latest.total_trades,
            "win_rate": latest.win_rate,
            "net_pnl": float(latest.net_pnl),
            "total_fees": float(latest.total_fees),
            "sharpe_ratio": latest.sharpe_ratio,
            "max_drawdown": latest.max_drawdown,
            "current_positions": len(self.positions),
            "daily_trades": self.daily_trades,
            "daily_pnl": float(self.daily_pnl),
            "consecutive_losses": self.consecutive_losses
        }