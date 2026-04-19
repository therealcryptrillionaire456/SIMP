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
    TradeRequest,
    TradeSide,
    TradeStatus,
    SafetyViolationError,
    create_executor,
)
from simp.organs.quantumarb.exchange_connector import StubExchangeConnector


class TestTradeExecutor:
    """Test TradeExecutor functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.exchange = StubExchangeConnector(
            name="test_exchange",
            prices={"BTC-USD": 50000.0},
            fee_rate=0.001,
            balances={"USD": 100000.0, "BTC": 10.0},
        )
        
    def test_create_executor(self):
        """Test executor creation."""
        executor = create_executor(
            exchange=self.exchange,
            dry_run=True,
            max_position_per_market=10000.0,
            max_trades_per_hour=10,
            max_slippage_bps=50.0,
            log_dir=self.temp_dir,
        )
        
        assert executor is not None
        assert executor.dry_run is True
        assert executor.max_position_per_market == 10000.0
        assert executor.max_trades_per_hour == 10
        assert executor.max_slippage_bps == 50.0
        
    def test_executor_initialization(self):
        """Test executor initialization."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            max_position_per_market=10000.0,
            max_trades_per_hour=10,
            max_slippage_bps=50.0,
            log_dir=self.temp_dir,
        )
        
        assert executor.exchange == self.exchange
        assert executor.dry_run is True
        assert executor.positions == {}
        assert len(executor.trade_history) == 0
        assert executor.trade_counts["total"] == 0
        assert executor.trade_counts["successful"] == 0
        assert executor.trade_counts["failed"] == 0
        
    def test_create_trade_request(self):
        """Test trade request creation."""
        # TradeRequest is a dataclass
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=50000.0,  # Limit order
            dry_run=True,
            metadata={"test": "data"},
        )
        
        assert request.market == "BTC-USD"
        assert request.side == TradeSide.BUY
        assert request.quantity == 1.0
        assert request.price_limit == 50000.0
        assert request.dry_run is True
        assert request.metadata["test"] == "data"
        assert request.trade_id == "test-trade-123"
        
    def test_execute_trade_dry_run_success(self):
        """Test successful trade execution in dry-run mode."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,  # Dry-run mode
            log_dir=self.temp_dir,
        )
        
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=50000.0,
        )
        
        result = executor.execute_trade(request)
        
        # Check result
        assert result.trade_id == request.trade_id
        assert result.request == request
        assert result.status in [TradeStatus.PENDING, TradeStatus.EXECUTED]
        assert result.executed_price is not None
        assert result.executed_quantity == request.quantity
        assert result.fees > 0
        assert result.error_message is None
        
        # Check position was updated (even in dry-run for tracking)
        assert executor.get_position("BTC-USD") == 1.0
        
        # Check trade counts
        assert executor.trade_counts["total"] == 1
        assert executor.trade_counts["successful"] == 1
        
    def test_execute_trade_invalid_quantity(self):
        """Test trade execution with invalid quantity."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=0.0,  # Invalid quantity
            price_limit=50000.0,
        )
        
        result = executor.execute_trade(request)
        
        assert result.status == TradeStatus.REJECTED
        assert result.error_message is not None
        assert "quantity" in result.error_message.lower()
        
    def test_execute_trade_invalid_price_limit(self):
        """Test trade execution with invalid price limit."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=0.0,  # Invalid price
        )
        
        result = executor.execute_trade(request)
        
        assert result.status == TradeStatus.REJECTED
        assert result.error_message is not None
        assert "price" in result.error_message.lower()
        
    def test_execute_trade_exceeds_position_limit(self):
        """Test trade execution that exceeds position limit."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            max_position_per_market=1000.0,  # Low limit (1000 USD)
            log_dir=self.temp_dir,
        )
        
        # This trade would exceed the position limit
        # 1 BTC * 50000 = 50,000 USD > 1,000 USD limit
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=50000.0,
        )
        
        result = executor.execute_trade(request)
        
        assert result.status == TradeStatus.REJECTED
        assert result.error_message is not None
        assert "position" in result.error_message.lower()
        
    def test_execute_trade_rate_limited(self):
        """Test trade execution rate limiting."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            max_trades_per_hour=1,  # Very low limit
            log_dir=self.temp_dir,
        )
        
        # First trade
        request1 = TradeRequest(
            trade_id="test-trade-1",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=0.1,  # Small quantity to pass position check
            price_limit=50000.0,
        )
        
        result1 = executor.execute_trade(request1)
        assert result1.status in [TradeStatus.PENDING, TradeStatus.EXECUTED]
        
        # Second trade should be rate limited
        request2 = TradeRequest(
            trade_id="test-trade-2",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=0.1,
            price_limit=50000.0,
        )
        
        result2 = executor.execute_trade(request2)
        assert result2.status == TradeStatus.REJECTED
        assert "rate" in result2.error_message.lower()
        
    def test_execute_trade_market_order(self):
        """Test market order execution."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        # Market order (price_limit=None)
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=None,  # Market order
        )
        
        result = executor.execute_trade(request)
        
        assert result.status in [TradeStatus.PENDING, TradeStatus.EXECUTED]
        assert result.executed_price is not None
        assert result.executed_quantity == request.quantity
        
    def test_execute_trade_limit_order_price_check(self):
        """Test limit order price validation."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        # Buy limit order with price below market (should fail)
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=40000.0,  # Below market price of 50000
        )
        
        result = executor.execute_trade(request)
        
        # Should fail because market price > buy limit
        assert result.status == TradeStatus.REJECTED
        assert "exceeds" in result.error_message.lower()
        
    def test_get_position(self):
        """Test position retrieval."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        # Set up positions
        executor.positions["BTC-USD"] = 1.5
        executor.positions["ETH-USD"] = 10.0
        
        # Get existing position
        btc_position = executor.get_position("BTC-USD")
        assert btc_position == 1.5
        
        # Get non-existent position
        ltc_position = executor.get_position("LTC-USD")
        assert ltc_position == 0.0
        
        # Get all positions
        all_positions = executor.get_all_positions()
        assert all_positions == {"BTC-USD": 1.5, "ETH-USD": 10.0}
        
    def test_get_trade_history(self):
        """Test trade history retrieval."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        # Execute some trades
        request1 = TradeRequest(
            trade_id="test-trade-1",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=50000.0,
        )
        
        request2 = TradeRequest(
            trade_id="test-trade-2",
            market="ETH-USD",
            side=TradeSide.SELL,
            quantity=2.0,
            price_limit=None,  # Market order
        )
        
        result1 = executor.execute_trade(request1)
        result2 = executor.execute_trade(request2)
        
        # Get trade history
        history = executor.get_trade_history()
        
        assert len(history) == 2
        assert history[0].trade_id == result1.trade_id
        assert history[1].trade_id == result2.trade_id
        
        # Test limit
        limited_history = executor.get_trade_history(limit=1)
        assert len(limited_history) == 1
        
    def test_reset_positions(self):
        """Test position reset."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        # Set up positions
        executor.positions["BTC-USD"] = 1.5
        executor.positions["ETH-USD"] = 10.0
        
        # Reset positions
        executor.reset_positions()
        
        assert executor.positions == {}
        assert executor.get_position("BTC-USD") == 0.0
        assert executor.get_position("ETH-USD") == 0.0
        
    def test_logging(self):
        """Test trade logging."""
        executor = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            log_dir=self.temp_dir,
        )
        
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=50000.0,
            metadata={"test": "logging"},
        )
        
        result = executor.execute_trade(request)
        
        # Check that log file was created
        log_files = list(Path(self.temp_dir).glob("trade_executions*.jsonl"))
        assert len(log_files) > 0
        
        # Check log content
        with open(log_files[0], "r") as f:
            log_lines = [json.loads(line) for line in f.readlines()]
            
        assert len(log_lines) > 0
        latest_log = log_lines[-1]
        assert latest_log["trade_id"] == request.trade_id
        assert latest_log["market"] == "BTC-USD"
        assert latest_log["dry_run"] is True
        
    def test_safety_gates(self):
        """Test that safety gates are enforced."""
        # Test 1: dry_run=True by default
        executor1 = create_executor(exchange=self.exchange)
        assert executor1.dry_run is True
        
        # Test 2: SafetyViolationError is raised for safety violations
        executor2 = TradeExecutor(
            exchange=self.exchange,
            dry_run=True,
            max_position_per_market=1000.0,  # Low limit
            log_dir=self.temp_dir,
        )
        
        # This should trigger a safety violation
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,  # 1 BTC * 50000 = 50,000 USD > 1,000 USD limit
            price_limit=50000.0,
        )
        
        result = executor2.execute_trade(request)
        assert result.status == TradeStatus.REJECTED
        assert isinstance(result.error_message, str)
        assert "position" in result.error_message.lower()


class TestTradeRequest:
    """Test TradeRequest dataclass."""
    
    def test_trade_request_creation(self):
        """Test TradeRequest creation."""
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=50000.0,
            metadata={"test": "data"},
        )
        
        assert request.market == "BTC-USD"
        assert request.side == TradeSide.BUY
        assert request.quantity == 1.0
        assert request.price_limit == 50000.0
        assert request.metadata["test"] == "data"
        assert request.trade_id == "test-trade-123"
        
    def test_trade_request_defaults(self):
        """Test TradeRequest defaults."""
        request = TradeRequest(
            trade_id="test-trade-123",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            # price_limit=None for market order
        )
        
        assert request.price_limit is None  # market order
        assert request.dry_run is True  # default safety gate
        assert request.metadata == {}
        assert request.trade_id == "test-trade-123"
        
    def test_trade_request_is_market_order(self):
        """Test market order detection."""
        # Market order
        market_request = TradeRequest(
            trade_id="test-1",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=None,
        )
        
        # Limit order
        limit_request = TradeRequest(
            trade_id="test-2",
            market="BTC-USD",
            side=TradeSide.BUY,
            quantity=1.0,
            price_limit=50000.0,
        )
        
        # Check market order
        assert market_request.price_limit is None
        
        # Check limit order
        assert limit_request.price_limit == 50000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])