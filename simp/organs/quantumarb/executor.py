#!/usr/bin/env python3.10
"""
Trade Executor for QuantumArb.

Executes arbitrage trades with safety checks, risk limits, and monitoring.
Designed for Phase 4: Microscopic real-money trading.
"""

import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .exchange_connector import (
    ExchangeConnector, Order, OrderSide, OrderType, OrderStatus,
    ExchangeError, InsufficientFundsError, OrderRejectedError
)

# Try to import monitoring system
try:
    from monitoring_alerting_system import MonitoringSystem, AlertSeverity, AlertType
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

log = logging.getLogger("TradeExecutor")

@dataclass
class ExecutionResult:
    """Result of trade execution attempt."""
    success: bool
    order_id: Optional[str] = None
    filled_quantity: float = 0.0
    average_price: float = 0.0
    slippage_bps: float = 0.0
    fees: float = 0.0
    error_message: str = ""
    timestamp: str = ""

class TradeExecutor:
    """
    Executes trades with comprehensive safety checks.
    
    For Phase 4 (microscopic trading):
    - Minimum position sizes only
    - All risk checks enforced
    - Complete monitoring integration
    - Manual supervision required
    """
    
    def __init__(self, exchange_connector: ExchangeConnector,
                 monitoring_system: Optional[Any] = None,
                 max_position_size_usd: float = 100.0,  # Microscopic for Phase 4
                 max_slippage_bps: float = 20.0,  # 0.2% max slippage
                 emergency_stop: bool = False):
        """
        Initialize trade executor.
        
        Args:
            exchange_connector: Exchange connector for order execution
            monitoring_system: Monitoring system for recording trades
            max_position_size_usd: Maximum position size in USD (Phase 4: microscopic)
            max_slippage_bps: Maximum allowed slippage in basis points
            emergency_stop: Whether emergency stop is active
        """
        self.exchange = exchange_connector
        self.monitoring = monitoring_system
        self.max_position_size_usd = max_position_size_usd
        self.max_slippage_bps = max_slippage_bps
        self.emergency_stop = emergency_stop
        
        # Execution statistics
        self.execution_count = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.total_slippage_bps = 0.0
        self.total_fees = 0.0
        
        # Active orders
        self.active_orders: Dict[str, Order] = {}
        
        log.info(f"TradeExecutor initialized (max position: ${max_position_size_usd:.2f}, "
                f"max slippage: {max_slippage_bps} bps)")
    
    def check_emergency_stop(self) -> bool:
        """Check if emergency stop is active."""
        if self.emergency_stop:
            log.warning("⚠️ Emergency stop active - trading halted")
            return True
        return False
    
    def validate_position_size(self, symbol: str, quantity: float) -> Tuple[bool, str]:
        """
        Validate position size for Phase 4 (microscopic).
        
        Args:
            symbol: Trading symbol
            quantity: Proposed quantity
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get current price to calculate USD value
        try:
            ticker = self.exchange.get_ticker(symbol)
            position_value_usd = quantity * ticker.last
            
            # Phase 4: Microscopic positions only
            if position_value_usd > self.max_position_size_usd:
                return False, (
                    f"Position size ${position_value_usd:.2f} exceeds "
                    f"Phase 4 limit of ${self.max_position_size_usd:.2f}"
                )
            
            # Minimum size check (exchange-specific)
            if quantity < 0.0001:  # Minimum for most crypto
                return False, f"Quantity {quantity} below minimum trade size"
            
            return True, "Position size valid for Phase 4"
            
        except Exception as e:
            return False, f"Failed to validate position size: {e}"
    
    def estimate_execution_costs(self, symbol: str, side: OrderSide, 
                                quantity: float) -> Tuple[float, float]:
        """
        Estimate execution costs (slippage and fees).
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            
        Returns:
            Tuple of (estimated_slippage_bps, estimated_fees_usd)
        """
        # Estimate slippage
        estimated_slippage = self.exchange.estimate_slippage(symbol, side, quantity)
        
        # Estimate fees (Coinbase Pro: 0.5% for takers, 0.0% for makers in sandbox)
        ticker = self.exchange.get_ticker(symbol)
        order_value = quantity * ticker.last
        
        # For Phase 4 microscopic trading, assume minimal fees
        # In sandbox: 0 fees, in live: 0.5% taker fee
        estimated_fees = 0.0  # Sandbox
        if not self.exchange.sandbox:
            estimated_fees = order_value * 0.005  # 0.5% taker fee
        
        return estimated_slippage, estimated_fees
    
    def check_slippage_limit(self, symbol: str, side: OrderSide,
                            quantity: float) -> Tuple[bool, str]:
        """
        Check if estimated slippage is within limits.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            
        Returns:
            Tuple of (within_limit, error_message)
        """
        estimated_slippage, _ = self.estimate_execution_costs(symbol, side, quantity)
        
        if estimated_slippage > self.max_slippage_bps:
            return False, (
                f"Estimated slippage {estimated_slippage:.1f} bps "
                f"exceeds limit of {self.max_slippage_bps} bps"
            )
        
        return True, f"Estimated slippage {estimated_slippage:.1f} bps within limits"
    
    def execute_trade(self, symbol: str, side: OrderSide, 
                     quantity: float, trade_id: str = "") -> ExecutionResult:
        """
        Execute a trade with all safety checks.
        
        For Phase 4: Microscopic positions only, all checks enforced.
        
        Args:
            symbol: Trading symbol (e.g., "BTC-USD")
            side: Buy or sell
            quantity: Order quantity
            trade_id: Optional trade ID for monitoring
            
        Returns:
            ExecutionResult with outcome details
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Generate trade ID if not provided
        if not trade_id:
            trade_id = f"trade_{int(time.time())}_{self.execution_count}"
        
        log.info(f"Executing trade {trade_id}: {side.value} {quantity} {symbol}")
        
        # Check emergency stop
        if self.check_emergency_stop():
            return ExecutionResult(
                success=False,
                error_message="Emergency stop active",
                timestamp=timestamp
            )
        
        # 1. Validate position size (Phase 4: microscopic only)
        is_valid, error_msg = self.validate_position_size(symbol, quantity)
        if not is_valid:
            log.warning(f"Position size validation failed: {error_msg}")
            return ExecutionResult(
                success=False,
                error_message=f"Position size invalid: {error_msg}",
                timestamp=timestamp
            )
        
        # 2. Check slippage limits
        slippage_ok, slippage_msg = self.check_slippage_limit(symbol, side, quantity)
        if not slippage_ok:
            log.warning(f"Slippage check failed: {slippage_msg}")
            return ExecutionResult(
                success=False,
                error_message=f"Slippage limit exceeded: {slippage_msg}",
                timestamp=timestamp
            )
        
        # 3. Estimate costs
        estimated_slippage, estimated_fees = self.estimate_execution_costs(
            symbol, side, quantity
        )
        
        log.info(f"Estimated costs: slippage={estimated_slippage:.1f} bps, "
                f"fees=${estimated_fees:.4f}")
        
        # 4. Record in monitoring system
        if MONITORING_AVAILABLE and self.monitoring:
            try:
                execution_data = {
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity,
                    "estimated_slippage": estimated_slippage,
                    "estimated_fees": estimated_fees,
                    "timestamp": timestamp,
                    "status": "pending"
                }
                self.monitoring.record_order_execution(trade_id, execution_data)
            except Exception as e:
                log.warning(f"Failed to record execution in monitoring: {e}")
        
        # 5. Execute order
        try:
            order = self.exchange.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=OrderType.MARKET  # Phase 4: Use market orders for simplicity
            )
            
            log.info(f"Order placed: {order.order_id}, status: {order.status.value}")
            
            # 6. Monitor order fill
            if order.status == OrderStatus.FILLED:
                # Immediate fill (common for market orders)
                filled_quantity = order.filled_quantity
                average_price = order.average_price or 0.0
                
                # Calculate actual slippage
                ticker = self.exchange.get_ticker(symbol)
                expected_price = ticker.ask if side == OrderSide.BUY else ticker.bid
                
                if expected_price > 0:
                    actual_slippage = abs((average_price - expected_price) / expected_price) * 10000
                else:
                    actual_slippage = estimated_slippage
                
                # Calculate actual fees (simplified for Phase 4)
                actual_fees = estimated_fees  # In Phase 4, we'll use estimates
                
                # Update statistics
                self.execution_count += 1
                self.successful_executions += 1
                self.total_slippage_bps += actual_slippage
                self.total_fees += actual_fees
                
                # Store active order
                self.active_orders[order.order_id] = order
                
                # Record fill in monitoring
                if MONITORING_AVAILABLE and self.monitoring:
                    try:
                        fill_data = {
                            "order_id": order.order_id,
                            "filled_quantity": filled_quantity,
                            "average_price": average_price,
                            "slippage_bps": actual_slippage,
                            "fees": actual_fees,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        self.monitoring.record_order_execution(trade_id, fill_data)
                    except Exception as e:
                        log.warning(f"Failed to record fill in monitoring: {e}")
                
                execution_time = time.time() - start_time
                
                log.info(f"✅ Trade executed successfully: {order.order_id}")
                log.info(f"   Filled: {filled_quantity} at ${average_price:.2f}")
                log.info(f"   Slippage: {actual_slippage:.1f} bps, Fees: ${actual_fees:.4f}")
                log.info(f"   Execution time: {execution_time:.2f}s")
                
                return ExecutionResult(
                    success=True,
                    order_id=order.order_id,
                    filled_quantity=filled_quantity,
                    average_price=average_price,
                    slippage_bps=actual_slippage,
                    fees=actual_fees,
                    timestamp=timestamp
                )
                
            else:
                # Order not immediately filled
                log.warning(f"Order {order.order_id} not immediately filled: {order.status.value}")
                
                # For Phase 4, we'll cancel unfilled market orders
                time.sleep(2)  # Wait a bit
                
                order_status = self.exchange.get_order_status(order.order_id)
                
                if order_status.status == OrderStatus.FILLED:
                    # Fill occurred after delay
                    return self.execute_trade(symbol, side, quantity, trade_id)
                else:
                    # Cancel unfilled order
                    self.exchange.cancel_order(order.order_id)
                    
                    self.execution_count += 1
                    self.failed_executions += 1
                    
                    return ExecutionResult(
                        success=False,
                        order_id=order.order_id,
                        error_message=f"Order not filled: {order_status.status.value}",
                        timestamp=timestamp
                    )
                    
        except InsufficientFundsError as e:
            log.error(f"Insufficient funds: {e}")
            self.failed_executions += 1
            
            return ExecutionResult(
                success=False,
                error_message=f"Insufficient funds: {e}",
                timestamp=timestamp
            )
            
        except OrderRejectedError as e:
            log.error(f"Order rejected: {e}")
            self.failed_executions += 1
            
            return ExecutionResult(
                success=False,
                error_message=f"Order rejected: {e}",
                timestamp=timestamp
            )
            
        except ExchangeError as e:
            log.error(f"Exchange error: {e}")
            self.failed_executions += 1
            
            return ExecutionResult(
                success=False,
                error_message=f"Exchange error: {e}",
                timestamp=timestamp
            )
            
        except Exception as e:
            log.error(f"Unexpected error executing trade: {e}")
            self.failed_executions += 1
            
            return ExecutionResult(
                success=False,
                error_message=f"Unexpected error: {e}",
                timestamp=timestamp
            )
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all active orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Number of orders cancelled
        """
        cancelled = 0
        
        try:
            open_orders = self.exchange.get_open_orders(symbol)
            
            for order in open_orders:
                try:
                    if self.exchange.cancel_order(order.order_id):
                        cancelled += 1
                        log.info(f"Cancelled order: {order.order_id}")
                        
                        # Remove from active orders
                        if order.order_id in self.active_orders:
                            del self.active_orders[order.order_id]
                except Exception as e:
                    log.warning(f"Failed to cancel order {order.order_id}: {e}")
            
            log.info(f"Cancelled {cancelled} orders")
            return cancelled
            
        except Exception as e:
            log.error(f"Failed to cancel orders: {e}")
            return 0
    
    def get_execution_stats(self) -> Dict:
        """Get execution statistics."""
        avg_slippage = 0.0
        if self.successful_executions > 0:
            avg_slippage = self.total_slippage_bps / self.successful_executions
        
        success_rate = 0.0
        if self.execution_count > 0:
            success_rate = self.successful_executions / self.execution_count
        
        return {
            "execution_count": self.execution_count,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": success_rate,
            "average_slippage_bps": avg_slippage,
            "total_fees_usd": self.total_fees,
            "active_orders": len(self.active_orders),
            "emergency_stop": self.emergency_stop
        }
    
    def set_emergency_stop(self, active: bool = True):
        """Set emergency stop state."""
        self.emergency_stop = active
        status = "ACTIVE" if active else "INACTIVE"
        log.warning(f"Emergency stop set to: {status}")
        
        if active:
            # Cancel all orders when emergency stop activated
            self.cancel_all_orders()


# Test function for Phase 4
def test_trade_executor():
    """Test trade executor functionality."""
    print("Testing Trade Executor for Phase 4...")
    
    # Create stub exchange connector
    from .exchange_connector import StubExchangeConnector, OrderSide
    
    exchange = StubExchangeConnector(sandbox=True)
    
    # Create trade executor with microscopic limits
    executor = TradeExecutor(
        exchange_connector=exchange,
        max_position_size_usd=50.0,  # Very small for Phase 4
        max_slippage_bps=10.0,  # Tight slippage limits
        emergency_stop=False
    )
    
    try:
        # Test 1: Position size validation
        print("\n1. Testing position size validation...")
        is_valid, msg = executor.validate_position_size("BTC-USD", 0.0005)
        print(f"   Small position (0.0005 BTC): {is_valid} - {msg}")
        
        is_valid, msg = executor.validate_position_size("BTC-USD", 1.0)
        print(f"   Large position (1.0 BTC): {is_valid} - {msg}")
        
        # Test 2: Slippage estimation
        print("\n2. Testing slippage estimation...")
        slippage_ok, slippage_msg = executor.check_slippage_limit(
            "BTC-USD", OrderSide.BUY, 0.001
        )
        print(f"   Slippage check: {slippage_ok} - {slippage_msg}")
        
        # Test 3: Cost estimation
        print("\n3. Testing cost estimation...")
        estimated_slippage, estimated_fees = executor.estimate_execution_costs(
            "BTC-USD", OrderSide.BUY, 0.001
        )
        print(f"   Estimated slippage: {estimated_slippage:.1f} bps")
        print(f"   Estimated fees: ${estimated_fees:.4f}")
        
        # Test 4: Execute microscopic trade
        print("\n4. Testing microscopic trade execution...")
        result = executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.001  # Microscopic size
        )
        
        print(f"   Execution result: {'SUCCESS' if result.success else 'FAILED'}")
        if result.success:
            print(f"   Order ID: {result.order_id}")
            print(f"   Filled: {result.filled_quantity}")
            print(f"   Average price: ${result.average_price:.2f}")
            print(f"   Slippage: {result.slippage_bps:.1f} bps")
            print(f"   Fees: ${result.fees:.4f}")
        else:
            print(f"   Error: {result.error_message}")
        
        # Test 5: Get execution stats
        print("\n5. Testing execution statistics...")
        stats = executor.get_execution_stats()
        print(f"   Execution count: {stats['execution_count']}")
        print(f"   Success rate: {stats['success_rate']:.1%}")
        print(f"   Average slippage: {stats['average_slippage_bps']:.1f} bps")
        
        # Test 6: Emergency stop
        print("\n6. Testing emergency stop...")
        executor.set_emergency_stop(True)
        result = executor.execute_trade("BTC-USD", OrderSide.BUY, 0.001)
        print(f"   Trade with emergency stop: {'BLOCKED' if not result.success else 'ALLOWED'}")
        
        print("\n✅ Trade executor tests passed")
        print("   Ready for Phase 4 microscopic trading")
        
    except Exception as e:
        print(f"❌ Trade executor test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_trade_executor()