"""
Unit tests for quantumarb TradeExecutor.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from simp.organs.quantumarb.executor import (
    TradeExecutor,
    ExecutionResult,
)
from simp.organs.quantumarb.exchange_connector import (
    StubExchangeConnector,
    OrderSide,
    OrderType,
    OrderStatus
)


class TestTradeExecutor:
    """Test TradeExecutor functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.exchange = StubExchangeConnector(sandbox=True)
        self.executor = TradeExecutor(
            exchange_connector=self.exchange,
            max_position_size_usd=1000.0,
            max_slippage_bps=20.0,
            emergency_stop=False
        )
    
    def test_executor_initialization(self):
        """Test TradeExecutor initialization."""
        assert self.executor is not None
        assert self.executor.max_position_size_usd == 1000.0
        assert self.executor.max_slippage_bps == 20.0
        assert self.executor.emergency_stop is False
        assert self.executor.execution_count == 0
        assert self.executor.successful_executions == 0
        assert self.executor.failed_executions == 0
    
    def test_validate_position_size(self):
        """Test position size validation."""
        # Valid small position
        is_valid, msg = self.executor.validate_position_size("BTC-USD", 0.001)
        assert is_valid is True
        assert "valid" in msg.lower()
        
        # Invalid large position (exceeds max position size)
        is_valid, msg = self.executor.validate_position_size("BTC-USD", 10.0)
        assert is_valid is False
        assert "exceeds" in msg.lower() or "maximum" in msg.lower()
    
    def test_check_slippage_limit(self):
        """Test slippage limit checking."""
        # Valid slippage (small quantity)
        slippage_ok, msg = self.executor.check_slippage_limit(
            "BTC-USD", OrderSide.BUY, 0.001
        )
        assert slippage_ok is True
        
        # Large quantity might exceed slippage limit
        slippage_ok, msg = self.executor.check_slippage_limit(
            "BTC-USD", OrderSide.BUY, 1.0
        )
        # This depends on the stub exchange's simulated slippage
    
    def test_estimate_execution_costs(self):
        """Test execution cost estimation."""
        estimated_slippage, estimated_fees = self.executor.estimate_execution_costs(
            "BTC-USD", OrderSide.BUY, 0.001
        )
        assert isinstance(estimated_slippage, float)
        assert isinstance(estimated_fees, float)
        assert estimated_slippage >= 0
        assert estimated_fees >= 0
    
    def test_execute_trade_success(self):
        """Test successful trade execution."""
        result = self.executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.001
        )
        
        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.order_id is not None
        assert result.filled_quantity == 0.001
        assert result.average_price > 0
        assert result.slippage_bps >= 0
        assert result.fees >= 0
        assert result.error_message == ""
        
        # Check that execution stats are updated
        assert self.executor.execution_count == 1
        assert self.executor.successful_executions == 1
    
    def test_execute_trade_invalid_quantity(self):
        """Test trade execution with invalid quantity."""
        # Zero quantity
        result = self.executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.0
        )
        
        assert result.success is False
        assert "quantity" in result.error_message.lower() or "invalid" in result.error_message.lower()
        
        # Negative quantity
        result = self.executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=-0.001
        )
        
        assert result.success is False
        assert "quantity" in result.error_message.lower() or "invalid" in result.error_message.lower()
    
    def test_execute_trade_exceeds_position_limit(self):
        """Test trade execution that exceeds position limit."""
        # Try to execute a trade that exceeds the max position size
        # The stub exchange has BTC price around 50000, so 1 BTC = ~50000 USD
        # Our max position size is 1000 USD, so 0.1 BTC = ~5000 USD should exceed limit
        result = self.executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.1  # ~5000 USD at 50000/BTC
        )
        
        # This should fail due to position size validation
        assert result.success is False
        assert "position" in result.error_message.lower() or "size" in result.error_message.lower() or "exceeds" in result.error_message.lower()
    
    def test_cancel_all_orders(self):
        """Test canceling all orders."""
        # First execute a trade
        result = self.executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.001
        )
        assert result.success is True
        
        # Cancel all orders
        cancelled_count = self.executor.cancel_all_orders("BTC-USD")
        assert cancelled_count >= 0  # Could be 0 if order was already filled
    
    def test_get_execution_stats(self):
        """Test getting execution statistics."""
        # Execute a few trades
        for _ in range(3):
            result = self.executor.execute_trade(
                symbol="BTC-USD",
                side=OrderSide.BUY,
                quantity=0.001
            )
        
        # Get stats
        stats = self.executor.get_execution_stats()
        
        assert isinstance(stats, dict)
        assert "execution_count" in stats
        assert "success_rate" in stats
        assert "average_slippage_bps" in stats
        assert "total_fees_usd" in stats
        assert "active_orders" in stats
        assert "emergency_stop" in stats
        
        assert stats["execution_count"] == 3
        assert 0 <= stats["success_rate"] <= 1
    
    def test_emergency_stop(self):
        """Test emergency stop functionality."""
        # Enable emergency stop
        self.executor.set_emergency_stop(True)
        assert self.executor.emergency_stop is True
        
        # Try to execute a trade with emergency stop enabled
        result = self.executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.001
        )
        
        # Should fail due to emergency stop
        assert result.success is False
        assert "emergency" in result.error_message.lower() or "stop" in result.error_message.lower()
        
        # Disable emergency stop
        self.executor.set_emergency_stop(False)
        assert self.executor.emergency_stop is False
        
        # Now trade should succeed
        result = self.executor.execute_trade(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=0.001
        )
        
        assert result.success is True
    
    def test_check_emergency_stop(self):
        """Test emergency stop checking."""
        # Initially should be False
        assert self.executor.check_emergency_stop() is False
        
        # Enable emergency stop
        self.executor.set_emergency_stop(True)
        assert self.executor.check_emergency_stop() is True
        
        # Disable emergency stop
        self.executor.set_emergency_stop(False)
        assert self.executor.check_emergency_stop() is False


def test_execution_result_dataclass():
    """Test ExecutionResult dataclass."""
    # Test successful execution
    success_result = ExecutionResult(
        success=True,
        order_id="order_123",
        filled_quantity=0.001,
        average_price=50000.0,
        slippage_bps=5.0,
        fees=0.75,
        error_message="",
        timestamp="2026-04-16T00:00:00Z"
    )
    
    assert success_result.success is True
    assert success_result.order_id == "order_123"
    assert success_result.filled_quantity == 0.001
    assert success_result.average_price == 50000.0
    assert success_result.slippage_bps == 5.0
    assert success_result.fees == 0.75
    assert success_result.error_message == ""
    assert success_result.timestamp == "2026-04-16T00:00:00Z"
    
    # Test failed execution
    fail_result = ExecutionResult(
        success=False,
        order_id=None,
        filled_quantity=0.0,
        average_price=0.0,
        slippage_bps=0.0,
        fees=0.0,
        error_message="Invalid quantity",
        timestamp="2026-04-16T00:00:00Z"
    )
    
    assert fail_result.success is False
    assert fail_result.order_id is None
    assert fail_result.error_message == "Invalid quantity"