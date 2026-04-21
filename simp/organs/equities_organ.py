"""
Equities Trading Organ - Stock/ETF execution via Alpaca API
============================================================
Executes stock and ETF trades based on BullBear signals.

This organ:
1. Receives equity trading signals from BullBear
2. Executes trades via Alpaca API (simulated in dry-run mode)
3. Manages position sizing and risk
4. Trades stocks, ETFs, and other equity instruments

For production use, replace mock execution with real Alpaca API calls.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
import random

from simp.integrations.trading_organ import (
    TradingOrgan,
    OrganType,
    TradeExecution,
    OrganExecutionResult,
    ExecutionStatus
)


class EquitiesOrgan(TradingOrgan):
    """
    Equities trading organ for stocks and ETFs.
    
    Executes trades via Alpaca API (simulated in dry-run mode).
    Handles market, limit, and stop orders for US equities.
    """

    def __init__(
        self,
        organ_id: str = "equities:001",
        initial_balance: float = 50000.0,
        dry_run: bool = True
    ):
        """
        Initialize equities trading organ.
        
        Args:
            organ_id: Unique identifier
            initial_balance: Starting USD balance
            dry_run: If True, simulate execution without real trades
        """
        super().__init__(organ_id, OrganType.EQUITIES_TRADING)
        self.balance = initial_balance
        self.dry_run = dry_run
        self.positions: Dict[str, float] = {}  # symbol -> quantity
        self.is_operational = True
        self.last_execution_time: Optional[str] = None
        self.total_trades = 0
        self.total_volume = 0.0
        
        # Supported exchanges
        self.supported_exchanges = ["NASDAQ", "NYSE", "AMEX"]
        
        # Market hours (EST)
        self.market_hours = {
            "regular": {"start": "09:30", "end": "16:00"},
            "extended": {"premarket": "04:00-09:30", "afterhours": "16:00-20:00"}
        }
        
        # Risk limits
        self.max_position_size = 10000.0  # Max $ per position
        self.max_daily_trades = 20
        self.daily_trade_count = 0
        
        print(f"[EquitiesOrgan] Initialized with balance=${initial_balance:,.2f}, dry_run={dry_run}")

    async def execute(
        self,
        params: Dict[str, Any],
        intent_id: str
    ) -> OrganExecutionResult:
        """
        Execute an equity trade.
        
        Parameters expected in params:
        - symbol: Stock symbol (e.g., "AAPL", "TSLA")
        - side: "BUY" or "SELL"
        - quantity: Number of shares
        - order_type: "MARKET", "LIMIT", "STOP"
        - limit_price: Required for LIMIT orders
        - stop_price: Required for STOP orders
        - time_in_force: "DAY", "GTC", "IOC", "FOK"
        - extended_hours: True/False for extended hours trading
        """
        try:
            # Validate parameters
            valid = await self.validate_params(params)
            if not valid:
                return OrganExecutionResult(
                    organ_id=self.organ_id,
                    organ_type=self.organ_type,
                    intent_id=intent_id,
                    status=ExecutionStatus.FAILED,
                    executions=[],
                    total_pnl=0,
                    timestamp=datetime.utcnow().isoformat(),
                    error_message="Invalid parameters"
                )
            
            # Check risk limits
            if not await self._check_risk_limits(params):
                return OrganExecutionResult(
                    organ_id=self.organ_id,
                    organ_type=self.organ_type,
                    intent_id=intent_id,
                    status=ExecutionStatus.FAILED,
                    executions=[],
                    total_pnl=0,
                    timestamp=datetime.utcnow().isoformat(),
                    error_message="Risk limit exceeded"
                )
            
            # Extract parameters
            symbol = params.get("symbol", "").upper()
            side = params.get("side", "BUY").upper()
            quantity = float(params.get("quantity", 0))
            order_type = params.get("order_type", "MARKET").upper()
            limit_price = params.get("limit_price")
            stop_price = params.get("stop_price")
            time_in_force = params.get("time_in_force", "DAY")
            extended_hours = params.get("extended_hours", False)
            
            # Get current market price (simulated)
            current_price = await self._get_market_price(symbol)
            
            # Calculate execution price based on order type
            execution_price = await self._calculate_execution_price(
                symbol, side, order_type, current_price, limit_price, stop_price
            )
            
            # Calculate total cost/proceeds
            if side == "BUY":
                total_cost = quantity * execution_price
                fee = total_cost * 0.0005  # 0.05% fee (typical for retail)
                
                # Check balance
                if self.balance < total_cost + fee:
                    return OrganExecutionResult(
                        organ_id=self.organ_id,
                        organ_type=self.organ_type,
                        intent_id=intent_id,
                        status=ExecutionStatus.FAILED,
                        executions=[],
                        total_pnl=0,
                        timestamp=datetime.utcnow().isoformat(),
                        error_message=f"Insufficient balance: ${self.balance:,.2f} < ${total_cost + fee:,.2f}"
                    )
                
                # Update balance and position
                self.balance -= (total_cost + fee)
                self.positions[symbol] = self.positions.get(symbol, 0) + quantity
                
            else:  # SELL
                # Check position
                current_position = self.positions.get(symbol, 0)
                if current_position < quantity:
                    return OrganExecutionResult(
                        organ_id=self.organ_id,
                        organ_type=self.organ_type,
                        intent_id=intent_id,
                        status=ExecutionStatus.FAILED,
                        executions=[],
                        total_pnl=0,
                        timestamp=datetime.utcnow().isoformat(),
                        error_message=f"Insufficient position: {current_position} < {quantity}"
                    )
                
                total_proceeds = quantity * execution_price
                fee = total_proceeds * 0.0005  # 0.05% fee
                
                # Update balance and position
                self.balance += (total_proceeds - fee)
                self.positions[symbol] = current_position - quantity
                if self.positions[symbol] <= 0.0001:  # Near zero
                    del self.positions[symbol]
            
            # Simulate API call delay
            if not self.dry_run:
                await asyncio.sleep(0.2)  # Real API call
            else:
                await asyncio.sleep(0.05)  # Simulated
            
            # Generate execution ID
            execution_id = f"EQ_{uuid.uuid4().hex[:8]}"
            
            # Create execution record
            execution = TradeExecution(
                execution_id=execution_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=execution_price,
                fee=fee,
                timestamp=datetime.utcnow().isoformat(),
                metadata={
                    "order_type": order_type,
                    "time_in_force": time_in_force,
                    "extended_hours": extended_hours,
                    "dry_run": self.dry_run,
                    "intent_id": intent_id,
                }
            )
            
            # Update stats
            self.total_trades += 1
            self.daily_trade_count += 1
            self.total_volume += quantity * execution_price
            self.last_execution_time = datetime.utcnow().isoformat()
            
            # Log execution
            action = "SIMULATED" if self.dry_run else "EXECUTED"
            print(f"[EquitiesOrgan] {action} {side} {quantity} {symbol} @ ${execution_price:.2f}")
            
            return OrganExecutionResult(
                organ_id=self.organ_id,
                organ_type=self.organ_type,
                intent_id=intent_id,
                status=ExecutionStatus.COMPLETED,
                executions=[execution],
                total_pnl=0,  # P&L calculated separately
                timestamp=datetime.utcnow().isoformat(),
                metadata={
                    "dry_run": self.dry_run,
                    "execution_id": execution_id,
                    "remaining_balance": self.balance,
                    "positions": self.positions,
                }
            )
            
        except Exception as e:
            print(f"[EquitiesOrgan] Execution error: {e}")
            return OrganExecutionResult(
                organ_id=self.organ_id,
                organ_type=self.organ_type,
                intent_id=intent_id,
                status=ExecutionStatus.FAILED,
                executions=[],
                total_pnl=0,
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate equity trading parameters."""
        try:
            # Required fields
            symbol = params.get("symbol", "")
            side = params.get("side", "")
            quantity = params.get("quantity", 0)
            
            if not symbol or not isinstance(symbol, str):
                return False
            
            if side not in ["BUY", "SELL"]:
                return False
            
            if not isinstance(quantity, (int, float)) or quantity <= 0:
                return False
            
            # Check order type
            order_type = params.get("order_type", "MARKET").upper()
            if order_type not in ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]:
                return False
            
            # Check limit/stop prices for appropriate order types
            if order_type in ["LIMIT", "STOP_LIMIT"]:
                if "limit_price" not in params or params["limit_price"] <= 0:
                    return False
            
            if order_type in ["STOP", "STOP_LIMIT"]:
                if "stop_price" not in params or params["stop_price"] <= 0:
                    return False
            
            # Check time in force
            time_in_force = params.get("time_in_force", "DAY")
            if time_in_force not in ["DAY", "GTC", "IOC", "FOK"]:
                return False
            
            return True
            
        except Exception as e:
            print(f"[EquitiesOrgan] Validation error: {e}")
            return False

    async def _check_risk_limits(self, params: Dict[str, Any]) -> bool:
        """Check risk management limits."""
        try:
            symbol = params.get("symbol", "").upper()
            side = params.get("side", "BUY").upper()
            quantity = float(params.get("quantity", 0))
            
            # Get estimated price for position sizing
            estimated_price = await self._get_market_price(symbol)
            position_value = quantity * estimated_price
            
            # Check max position size
            if position_value > self.max_position_size:
                print(f"[EquitiesOrgan] Position size ${position_value:,.2f} > max ${self.max_position_size:,.2f}")
                return False
            
            # Check daily trade limit
            if self.daily_trade_count >= self.max_daily_trades:
                print(f"[EquitiesOrgan] Daily trade limit {self.max_daily_trades} reached")
                return False
            
            # For buys, check if we already have too much of this symbol
            if side == "BUY":
                current_position = self.positions.get(symbol, 0)
                current_value = current_position * estimated_price
                if current_value + position_value > self.max_position_size * 1.5:
                    print(f"[EquitiesOrgan] Would exceed concentration limit for {symbol}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"[EquitiesOrgan] Risk check error: {e}")
            return False

    async def _get_market_price(self, symbol: str) -> float:
        """Get current market price for a symbol (simulated)."""
        # In production, this would call Alpaca API
        # For simulation, return realistic prices for common symbols
        
        price_map = {
            "AAPL": 175.0,
            "MSFT": 420.0,
            "GOOGL": 155.0,
            "AMZN": 180.0,
            "TSLA": 175.0,
            "NVDA": 950.0,
            "META": 500.0,
            "JPM": 195.0,
            "JNJ": 150.0,
            "SPY": 520.0,
            "QQQ": 440.0,
            "DIA": 400.0,
            "IWM": 200.0,
            "VTI": 250.0,
        }
        
        # Return mapped price or random realistic price
        if symbol in price_map:
            price = price_map[symbol]
        else:
            # Generate random but realistic price
            price = random.uniform(10, 500)
        
        # Add small random fluctuation
        fluctuation = random.uniform(-0.01, 0.01)  # ±1%
        return price * (1 + fluctuation)

    async def _calculate_execution_price(
        self,
        symbol: str,
        side: str,
        order_type: str,
        current_price: float,
        limit_price: Optional[float],
        stop_price: Optional[float]
    ) -> float:
        """Calculate execution price based on order type."""
        if order_type == "MARKET":
            # Market orders get current price with small slippage
            slippage = random.uniform(-0.001, 0.001)  # ±0.1%
            return current_price * (1 + slippage)
        
        elif order_type == "LIMIT":
            # Limit orders execute at limit price if marketable
            if limit_price is None:
                return current_price
            
            # Check if limit order is marketable
            if (side == "BUY" and limit_price >= current_price) or \
               (side == "SELL" and limit_price <= current_price):
                # Execute at limit price
                return limit_price
            else:
                # Order would not execute immediately
                # For simulation, assume it executes at current price
                return current_price
        
        elif order_type == "STOP":
            # Stop orders become market orders when stop price is hit
            if stop_price is None:
                return current_price
            
            # Check if stop is triggered
            if (side == "BUY" and current_price >= stop_price) or \
               (side == "SELL" and current_price <= stop_price):
                # Stop triggered, execute at market
                slippage = random.uniform(-0.002, 0.002)  # ±0.2% for stop orders
                return current_price * (1 + slippage)
            else:
                # Stop not triggered
                return current_price
        
        elif order_type == "STOP_LIMIT":
            # Stop-limit orders become limit orders when stop price is hit
            if stop_price is None or limit_price is None:
                return current_price
            
            # Check if stop is triggered
            if (side == "BUY" and current_price >= stop_price) or \
               (side == "SELL" and current_price <= stop_price):
                # Stop triggered, execute at limit price if marketable
                if (side == "BUY" and limit_price >= current_price) or \
                   (side == "SELL" and limit_price <= current_price):
                    return limit_price
                else:
                    return current_price
            else:
                return current_price
        
        return current_price

    async def get_status(self) -> Dict[str, Any]:
        """Get organ status."""
        return {
            "organ_id": self.organ_id,
            "organ_type": self.organ_type.value,
            "balance": self.balance,
            "positions": self.positions,
            "total_trades": self.total_trades,
            "total_volume": self.total_volume,
            "daily_trade_count": self.daily_trade_count,
            "last_execution_time": self.last_execution_time,
            "is_operational": self.is_operational,
            "dry_run": self.dry_run,
            "max_position_size": self.max_position_size,
            "max_daily_trades": self.max_daily_trades,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def reset_daily_counts(self):
        """Reset daily counters (call at market close)."""
        self.daily_trade_count = 0
        print(f"[EquitiesOrgan] Daily counters reset")


# Factory function for creating equities organ
def create_equities_organ(
    organ_id: str = "equities:001",
    initial_balance: float = 50000.0,
    dry_run: bool = True
) -> EquitiesOrgan:
    """Create and initialize an equities trading organ."""
    organ = EquitiesOrgan(
        organ_id=organ_id,
        initial_balance=initial_balance,
        dry_run=dry_run
    )
    return organ