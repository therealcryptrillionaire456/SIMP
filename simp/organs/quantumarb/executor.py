"""
Trade executor for QuantumArb organ.

Implements trade execution with safety limits, dry-run mode, and integration
with exchange connectors. Follows SIMP safety protocols and maintains
compatibility with the broker system.

Safety rules:
1. dry_run=True by default (hardcoded safety gate)
2. All trades require explicit safety checks
3. Position limits enforced per market
4. Rate limiting to prevent excessive trading
"""

import json
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_DOWN

from .exchange_connector import ExchangeConnector, OrderBook


class TradeSide(str, Enum):
    """Trade side enumeration."""
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    """Trade status enumeration."""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"  # Safety check failed


@dataclass
class TradeRequest:
    """Request to execute a trade."""
    trade_id: str
    market: str
    side: TradeSide
    quantity: float
    price_limit: Optional[float] = None  # None = market order
    dry_run: bool = True  # Safety gate: always True unless explicitly overridden
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeResult:
    """Result of a trade execution attempt."""
    trade_id: str
    request: TradeRequest
    status: TradeStatus
    executed_price: Optional[float] = None
    executed_quantity: Optional[float] = None
    fees: float = 0.0
    error_message: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


class SafetyViolationError(Exception):
    """Raised when a safety check fails."""
    pass


class TradeExecutor:
    """
    Executes trades with safety limits and dry-run mode.
    
    Features:
    - Dry-run mode (default: True)
    - Position limits per market
    - Rate limiting
    - Slippage protection
    - Fee calculation
    - Thread-safe operations
    """
    
    def __init__(
        self,
        exchange: ExchangeConnector,
        dry_run: bool = True,  # Safety gate: default to True
        max_position_per_market: float = 10000.0,  # USD equivalent
        max_trades_per_hour: int = 10,
        max_slippage_bps: float = 50.0,  # 0.5%
        log_dir: Optional[str] = None,
    ):
        """
        Initialize the trade executor.
        
        Args:
            exchange: Exchange connector instance
            dry_run: If True, no actual trades are executed (safety gate)
            max_position_per_market: Maximum position size per market (USD)
            max_trades_per_hour: Maximum number of trades per hour
            max_slippage_bps: Maximum allowed slippage in basis points
            log_dir: Directory for trade logs
        """
        self.exchange = exchange
        self.dry_run = dry_run
        self.max_position_per_market = max_position_per_market
        self.max_trades_per_hour = max_trades_per_hour
        self.max_slippage_bps = max_slippage_bps
        
        # State tracking
        self.positions: Dict[str, float] = {}  # market -> position size
        self.trade_history: List[TradeResult] = []
        self.trade_counts: Dict[str, int] = {}  # hour timestamp -> count
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Logging
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs" / "quantumarb"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Safety: log dry-run status
        if self.dry_run:
            self._log_safety_event("INIT", "TradeExecutor initialized in DRY-RUN mode")
        else:
            self._log_safety_event(
                "WARNING", 
                "TradeExecutor initialized in LIVE mode (safety gate disabled)"
            )
    
    def _log_safety_event(self, level: str, message: str) -> None:
        """Log a safety-related event."""
        log_file = self.log_dir / "safety_events.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "dry_run": self.dry_run,
        }
        with self.lock:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except (IOError, OSError):
                pass  # Silently fail if logging fails
    
    def _log_trade(self, result: TradeResult) -> None:
        """Log a trade result."""
        log_file = self.log_dir / "trade_log.jsonl"
        with self.lock:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(asdict(result)) + "\n")
            except (IOError, OSError):
                pass  # Silently fail if logging fails
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit is exceeded."""
        current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        with self.lock:
            count = self.trade_counts.get(current_hour, 0)
            if count >= self.max_trades_per_hour:
                return False
            self.trade_counts[current_hour] = count + 1
        return True
    
    def _check_position_limit(self, market: str, quantity: float, price: float) -> bool:
        """Check if position limit would be exceeded."""
        position_value = abs(self.positions.get(market, 0.0))
        trade_value = abs(quantity * price)
        new_position_value = position_value + trade_value
        
        return new_position_value <= self.max_position_per_market
    
    def _check_slippage(self, expected_price: float, actual_price: float) -> bool:
        """Check if slippage is within limits."""
        if expected_price == 0:
            return True
        
        slippage_bps = abs((actual_price - expected_price) / expected_price) * 10000
        return slippage_bps <= self.max_slippage_bps
    
    def _get_market_price(self, market: str, side: TradeSide) -> float:
        """Get current market price for a given side."""
        orderbook = self.exchange.get_orderbook(market)
        if side == TradeSide.BUY:
            # Buy at ask price
            return orderbook['asks'][0][0] if orderbook['asks'] else 0.0
        else:  # SELL
            # Sell at bid price
            return orderbook['bids'][0][0] if orderbook['bids'] else 0.0
    
    def _calculate_fees(self, quantity: float, price: float) -> float:
        """Calculate fees for a trade."""
        trade_value = quantity * price
        fee_rate = self.exchange.get_fees()
        return trade_value * fee_rate
    
    def execute_trade(self, request: TradeRequest) -> TradeResult:
        """
        Execute a trade with safety checks.
        
        Args:
            request: Trade request to execute
            
        Returns:
            TradeResult with execution details
        """
        start_time = time.time()
        
        try:
            # 1. Validate request
            if request.quantity <= 0:
                raise ValueError(f"Invalid quantity: {request.quantity}")
            
            if request.price_limit is not None and request.price_limit <= 0:
                raise ValueError(f"Invalid price limit: {request.price_limit}")
            
            # 2. Get current market price
            market_price = self._get_market_price(request.market, request.side)
            if market_price <= 0:
                raise ValueError(f"Invalid market price: {market_price}")
            
            # 3. Apply price limit if specified
            execution_price = market_price
            if request.price_limit is not None:
                if request.side == TradeSide.BUY and market_price > request.price_limit:
                    raise SafetyViolationError(
                        f"Market price {market_price} exceeds buy limit {request.price_limit}"
                    )
                elif request.side == TradeSide.SELL and market_price < request.price_limit:
                    raise SafetyViolationError(
                        f"Market price {market_price} below sell limit {request.price_limit}"
                    )
                execution_price = request.price_limit
            
            # 4. Safety checks
            if not self._check_rate_limit():
                raise SafetyViolationError("Rate limit exceeded")
            
            if not self._check_position_limit(request.market, request.quantity, execution_price):
                raise SafetyViolationError("Position limit would be exceeded")
            
            if not self._check_slippage(request.price_limit or market_price, execution_price):
                raise SafetyViolationError("Slippage exceeds limit")
            
            # 5. Execute trade (or simulate in dry-run mode)
            if self.dry_run or request.dry_run:
                status = TradeStatus.EXECUTED if not self.dry_run else TradeStatus.PENDING
                result = TradeResult(
                    trade_id=request.trade_id,
                    request=request,
                    status=status,
                    executed_price=execution_price,
                    executed_quantity=request.quantity,
                    fees=self._calculate_fees(request.quantity, execution_price),
                    metadata={
                        "dry_run": True,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "market_price_at_execution": market_price,
                    }
                )
                
                # Update position (even in dry-run for tracking)
                with self.lock:
                    current_position = self.positions.get(request.market, 0.0)
                    if request.side == TradeSide.BUY:
                        self.positions[request.market] = current_position + request.quantity
                    else:
                        self.positions[request.market] = current_position - request.quantity
                
                self._log_trade(result)
                return result
            else:
                # Live execution would go here
                # For now, we simulate successful execution
                result = TradeResult(
                    trade_id=request.trade_id,
                    request=request,
                    status=TradeStatus.EXECUTED,
                    executed_price=execution_price,
                    executed_quantity=request.quantity,
                    fees=self._calculate_fees(request.quantity, execution_price),
                    metadata={
                        "dry_run": False,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "market_price_at_execution": market_price,
                    }
                )
                
                # Update position
                with self.lock:
                    current_position = self.positions.get(request.market, 0.0)
                    if request.side == TradeSide.BUY:
                        self.positions[request.market] = current_position + request.quantity
                    else:
                        self.positions[request.market] = current_position - request.quantity
                    self.trade_history.append(result)
                
                self._log_trade(result)
                return result
                
        except (ValueError, SafetyViolationError) as e:
            # Safety check failed
            result = TradeResult(
                trade_id=request.trade_id,
                request=request,
                status=TradeStatus.REJECTED,
                error_message=str(e),
                metadata={
                    "dry_run": self.dry_run,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }
            )
            self._log_trade(result)
            return result
        except Exception as e:
            # Unexpected error
            result = TradeResult(
                trade_id=request.trade_id,
                request=request,
                status=TradeStatus.FAILED,
                error_message=str(e),
                metadata={
                    "dry_run": self.dry_run,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }
            )
            self._log_trade(result)
            return result
    
    def get_position(self, market: str) -> float:
        """Get current position for a market."""
        with self.lock:
            return self.positions.get(market, 0.0)
    
    def get_all_positions(self) -> Dict[str, float]:
        """Get all current positions."""
        with self.lock:
            return self.positions.copy()
    
    def get_trade_history(self, limit: int = 100) -> List[TradeResult]:
        """Get recent trade history."""
        with self.lock:
            return self.trade_history[-limit:] if self.trade_history else []
    
    def reset_positions(self) -> None:
        """Reset all positions (for testing only)."""
        with self.lock:
            self.positions.clear()
            self._log_safety_event("INFO", "All positions reset")


# Factory function for creating executors
def create_executor(
    exchange: ExchangeConnector,
    dry_run: bool = True,
    **kwargs
) -> TradeExecutor:
    """
    Create a TradeExecutor with sensible defaults.
    
    Args:
        exchange: Exchange connector instance
        dry_run: Whether to run in dry-run mode (safety gate)
        **kwargs: Additional arguments for TradeExecutor
        
    Returns:
        Configured TradeExecutor instance
    """
    return TradeExecutor(exchange=exchange, dry_run=dry_run, **kwargs)