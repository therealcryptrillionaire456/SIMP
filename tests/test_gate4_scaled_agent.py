#!/usr/bin/env python3
"""
Tests for Gate 4 Scaled Microscopic Agent
"""

import asyncio
import json
import tempfile
import unittest
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.gate4_scaled_agent_part1 import (
    TradingStrategy, OrderType, Gate4Config, ScaledPosition,
    MarketMicrostructure, RiskMetrics, Gate4ScaledAgent
)
from agents.gate4_scaled_agent_part2a import (
    TradeExecution, PositionState, PerformanceMetrics, TradeEngine
)
from agents.gate4_scaled_agent_part2b import (
    OrderReconciliation, RiskExposure, ComplianceRecord, OrderManager
)


class TestGate4Dataclasses(unittest.TestCase):
    """Test Gate 4 dataclasses"""
    
    def test_trading_strategy_enum(self):
        """Test TradingStrategy enum"""
        self.assertEqual(TradingStrategy.MEAN_REVERSION.value, "mean_reversion")
        self.assertEqual(TradingStrategy.MOMENTUM.value, "momentum")
        self.assertEqual(TradingStrategy.STATISTICAL_ARB.value, "statistical_arb")
        self.assertEqual(TradingStrategy.PAIRS_TRADING.value, "pairs_trading")
    
    def test_order_type_enum(self):
        """Test OrderType enum"""
        self.assertEqual(OrderType.MARKET.value, "market")
        self.assertEqual(OrderType.LIMIT.value, "limit")
        self.assertEqual(OrderType.STOP.value, "stop")
        self.assertEqual(OrderType.STOP_LIMIT.value, "stop_limit")
    
    def test_gate4_config(self):
        """Test Gate4Config dataclass"""
        # Note: Gate4Config requires all fields from the JSON config
        # For testing, we'll create a minimal valid config
        config_dict = {
            "mode": "gate_4_scaled_microscopic",
            "exchange": "coinbase",
            "symbols": ["BTC-USD", "ETH-USD"],
            "position_sizing": {
                "min_notional": 1.0,
                "max_notional": 10.0,
                "base_allocation_per_symbol": 2.0,
                "max_concurrent_positions": 3,
                "risk_per_trade_percent": 0.75,
                "max_daily_risk_percent": 3.0,
                "dynamic_sizing_enabled": True,
                "volatility_scaling_factor": 0.8,
                "liquidity_scaling_factor": 1.2
            },
            "execution": {},
            "monitoring": {},
            "enhanced_features": {},
            "risk_management": {},
            "reporting": {},
            "integration": {},
            "advanced": {},
            "compliance": {},
            "production_readiness": {}
        }
        
        config = Gate4Config(**config_dict)
        
        self.assertEqual(config.mode, "gate_4_scaled_microscopic")
        self.assertEqual(config.exchange, "coinbase")
        self.assertEqual(config.symbols, ["BTC-USD", "ETH-USD"])
        self.assertEqual(config.position_sizing["min_notional"], 1.0)
        self.assertEqual(config.position_sizing["max_notional"], 10.0)
    
    def test_scaled_position(self):
        """Test ScaledPosition dataclass"""
        position = ScaledPosition(
            symbol="BTC-USD",
            quantity=Decimal("0.001"),
            entry_price=Decimal("50000.00"),
            current_price=Decimal("51000.00"),
            notional_value=Decimal("51.00"),
            unrealized_pnl=Decimal("1.00"),
            unrealized_pnl_percent=Decimal("2.00"),
            entry_time=datetime.now(),
            strategy=TradingStrategy.MEAN_REVERSION
        )
        
        self.assertEqual(position.symbol, "BTC-USD")
        self.assertEqual(position.quantity, Decimal("0.001"))
        self.assertEqual(position.unrealized_pnl, Decimal("1.00"))
        self.assertEqual(position.strategy, TradingStrategy.MEAN_REVERSION)
    
    def test_market_microstructure(self):
        """Test MarketMicrostructure dataclass"""
        microstructure = MarketMicrostructure(
            symbol="BTC-USD",
            timestamp=datetime.now(),
            bid_price=Decimal("49900.00"),
            ask_price=Decimal("50100.00"),
            mid_price=Decimal("50000.00"),
            spread_percent=Decimal("0.004"),
            volume_24h=Decimal("1000000.00"),
            volatility_30m=Decimal("0.02"),
            momentum_5m=Decimal("0.01"),
            liquidity_score=Decimal("0.85"),
            order_book_imbalance=Decimal("0.15"),
            price_deviation=Decimal("-0.01")
        )
        
        self.assertEqual(microstructure.symbol, "BTC-USD")
        self.assertEqual(microstructure.spread_percent, Decimal("0.004"))
        self.assertEqual(microstructure.volatility_30m, Decimal("0.02"))
    
    def test_risk_metrics(self):
        """Test RiskMetrics dataclass"""
        risk_metrics = RiskMetrics(
            timestamp=datetime.now(),
            total_exposure=Decimal("100.00"),
            var_95=Decimal("5.00"),
            expected_shortfall=Decimal("7.50"),
            max_drawdown=Decimal("3.00"),
            sharpe_ratio=Decimal("1.50"),
            sortino_ratio=Decimal("2.00"),
            win_rate=Decimal("65.00"),
            profit_factor=Decimal("1.80")
        )
        
        self.assertEqual(risk_metrics.total_exposure, Decimal("100.00"))
        self.assertEqual(risk_metrics.var_95, Decimal("5.00"))
        self.assertEqual(risk_metrics.win_rate, Decimal("65.00"))


class TestTradeExecutionDataclasses(unittest.TestCase):
    """Test trade execution dataclasses"""
    
    def test_trade_execution(self):
        """Test TradeExecution dataclass"""
        trade = TradeExecution(
            trade_id="test_123",
            symbol="BTC-USD",
            side="buy",
            order_type=OrderType.MARKET,
            quantity=Decimal("0.001"),
            price=Decimal("50000.00"),
            notional=Decimal("50.00"),
            timestamp=datetime.now(),
            status="filled",
            fill_price=Decimal("50050.00"),
            fill_quantity=Decimal("0.001"),
            fill_notional=Decimal("50.05"),
            fill_timestamp=datetime.now(),
            fees=Decimal("0.04"),
            slippage=Decimal("0.001"),
            latency_ms=50
        )
        
        self.assertEqual(trade.trade_id, "test_123")
        self.assertEqual(trade.side, "buy")
        self.assertEqual(trade.order_type, OrderType.MARKET)
        self.assertEqual(trade.notional, Decimal("50.00"))
        self.assertEqual(trade.fees, Decimal("0.04"))
    
    def test_position_state(self):
        """Test PositionState dataclass"""
        position = PositionState(
            symbol="BTC-USD",
            quantity=Decimal("0.002"),
            avg_entry_price=Decimal("50000.00"),
            current_price=Decimal("51000.00"),
            notional_value=Decimal("102.00"),
            unrealized_pnl=Decimal("2.00"),
            unrealized_pnl_percent=Decimal("2.00"),
            realized_pnl=Decimal("1.50"),
            total_fees=Decimal("0.08"),
            entry_timestamp=datetime.now(),
            duration_minutes=30.5
        )
        
        self.assertEqual(position.symbol, "BTC-USD")
        self.assertEqual(position.quantity, Decimal("0.002"))
        self.assertEqual(position.unrealized_pnl, Decimal("2.00"))
        self.assertEqual(position.duration_minutes, 30.5)
    
    def test_performance_metrics(self):
        """Test PerformanceMetrics dataclass"""
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            total_trades=100,
            winning_trades=65,
            losing_trades=35,
            win_rate=65.0,
            total_pnl=Decimal("150.00"),
            total_fees=Decimal("8.00"),
            net_pnl=Decimal("142.00"),
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=3.0,
            profit_factor=1.8,
            avg_win=Decimal("2.50"),
            avg_loss=Decimal("-1.50"),
            avg_trade_duration_minutes=15.5,
            success_rate=95.0,
            fill_rate=98.5,
            avg_slippage_percent=0.15,
            avg_latency_ms=45.0
        )
        
        self.assertEqual(metrics.total_trades, 100)
        self.assertEqual(metrics.win_rate, 65.0)
        self.assertEqual(metrics.net_pnl, Decimal("142.00"))
        self.assertEqual(metrics.avg_trade_duration_minutes, 15.5)


class TestGate4ScaledAgent(unittest.TestCase):
    """Test Gate4ScaledAgent"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"
        
        config = {
            "mode": "gate_4_scaled_microscopic",
            "exchange": "coinbase",
            "symbols": ["BTC-USD", "ETH-USD"],
            "position_sizing": {
                "min_notional": 1.0,
                "max_notional": 10.0,
                "base_allocation_per_symbol": 2.0,
                "max_concurrent_positions": 3,
                "risk_per_trade_percent": 0.75
            }
        }
        
        with open(self.config_path, "w") as f:
            json.dump(config, f)
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('agents.gate4_scaled_agent_part1.ExchangeConnector')
    def test_agent_initialization(self, mock_exchange):
        """Test agent initialization"""
        mock_exchange.return_value = AsyncMock()
        
        agent = Gate4ScaledAgent(str(self.config_path))
        
        self.assertEqual(agent.config.mode, "gate_4_scaled_microscopic")
        self.assertEqual(agent.config.exchange, "coinbase")
        self.assertEqual(agent.config.symbols, ["BTC-USD", "ETH-USD"])
        self.assertIsNotNone(agent.exchange)
    
    @patch('agents.gate4_scaled_agent_part1.ExchangeConnector')
    def test_load_config(self, mock_exchange):
        """Test config loading"""
        mock_exchange.return_value = AsyncMock()
        
        agent = Gate4ScaledAgent(str(self.config_path))
        config = agent._load_config()
        
        self.assertEqual(config.mode, "gate_4_scaled_microscopic")
        self.assertEqual(config.position_sizing["min_notional"], 1.0)
        self.assertEqual(config.position_sizing["max_notional"], 10.0)
    
    @patch('agents.gate4_scaled_agent_part1.SimpBroker')
    @patch('agents.gate4_scaled_agent_part1.ExchangeConnector')
    async def test_connect_to_broker(self, mock_exchange, mock_broker):
        """Test broker connection"""
        mock_exchange.return_value = AsyncMock()
        mock_broker.return_value = AsyncMock()
        
        agent = Gate4ScaledAgent(str(self.config_path))
        await agent.connect_to_broker()
        
        self.assertIsNotNone(agent.broker)


class TestTradeEngine(unittest.IsolatedAsyncioTestCase):
    """Test TradeEngine"""
    
    async def asyncSetUp(self):
        """Set up async test fixtures"""
        # Create mock agent
        self.mock_agent = Mock(spec=Gate4ScaledAgent)
        self.mock_agent.config = Mock()
        self.mock_agent.config.position_sizing = {
            "min_notional": 1.0,
            "max_notional": 10.0,
            "base_allocation_per_symbol": 2.0,
            "max_concurrent_positions": 3,
            "risk_per_trade_percent": 0.75,
            "dynamic_sizing_enabled": True,
            "volatility_scaling_factor": 0.8,
            "liquidity_scaling_factor": 1.2
        }
        self.mock_agent.config.risk_management = {
            "circuit_breakers": {
                "max_hourly_trades": 30
            },
            "position_limits": {
                "max_exposure_per_symbol_percent": 30,
                "min_liquidity_threshold_usd": 5000000
            }
        }
        
        # Create mock exchange
        self.mock_exchange = AsyncMock()
        self.mock_exchange.get_ticker.return_value = {"last": 50000.0}
        self.mock_agent.exchange = self.mock_exchange
        
        # Create trade engine
        self.trade_engine = TradeEngine(self.mock_agent)
    
    async def test_calculate_position_size(self):
        """Test position size calculation"""
        # Mock market data
        self.mock_agent.analyze_market_microstructure = AsyncMock()
        self.mock_agent.analyze_market_microstructure.return_value = Mock(
            volatility_30m=0.02,
            liquidity_score=0.8
        )
        
        # Test position size calculation
        size = await self.trade_engine._calculate_position_size(
            symbol="BTC-USD",
            side="buy",
            requested_quantity=Decimal("0.001"),
            strategy=TradingStrategy.MEAN_REVERSION
        )
        
        # Should return a Decimal
        self.assertIsInstance(size, Decimal)
        self.assertGreater(size, Decimal("0"))
    
    async def test_check_hourly_trade_limit(self):
        """Test hourly trade limit check"""
        # Initially should be False
        self.assertFalse(self.trade_engine._check_hourly_trade_limit())
        
        # Set hourly count to limit
        self.trade_engine.hourly_trade_count = 30
        
        # Should be True (at limit)
        self.assertTrue(self.trade_engine._check_hourly_trade_limit())
    
    async def test_check_position_limits(self):
        """Test position limit checks"""
        # Test with no positions (should pass)
        result = self.trade_engine._check_position_limits(
            symbol="BTC-USD",
            side="buy",
            notional=Decimal("5.00")
        )
        self.assertTrue(result)
        
        # Test with max concurrent positions
        self.trade_engine.positions = {
            "ETH-USD": Mock(),
            "SOL-USD": Mock(),
            "AVAX-USD": Mock()
        }
        
        # Should fail for new symbol
        result = self.trade_engine._check_position_limits(
            symbol="BTC-USD",
            side="buy",
            notional=Decimal("5.00")
        )
        self.assertFalse(result)
    
    async def test_update_position(self):
        """Test position update"""
        # Create a filled trade
        trade = TradeExecution(
            trade_id="test_123",
            symbol="BTC-USD",
            side="buy",
            order_type=OrderType.MARKET,
            quantity=Decimal("0.001"),
            price=Decimal("50000.00"),
            notional=Decimal("50.00"),
            timestamp=datetime.now(),
            status="filled",
            fill_price=Decimal("50050.00"),
            fill_quantity=Decimal("0.001"),
            fill_notional=Decimal("50.05"),
            fill_timestamp=datetime.now(),
            fees=Decimal("0.04")
        )
        
        # Update position
        await self.trade_engine._update_position(trade)
        
        # Should have position
        self.assertIn("BTC-USD", self.trade_engine.positions)
        position = self.trade_engine.positions["BTC-USD"]
        self.assertEqual(position.quantity, Decimal("0.001"))
        self.assertEqual(position.avg_entry_price, Decimal("50050.00"))
    
    async def test_close_all_positions(self):
        """Test closing all positions"""
        # Add some positions
        self.trade_engine.positions = {
            "BTC-USD": Mock(quantity=Decimal("0.001")),
            "ETH-USD": Mock(quantity=Decimal("0.01"))
        }
        
        # Mock execute_trade to simulate closing
        self.trade_engine.execute_trade = AsyncMock()
        self.trade_engine.execute_trade.return_value = Mock(status="filled")
        
        # Close all positions
        await self.trade_engine.close_all_positions()
        
        # Should have called execute_trade for each position
        self.assertEqual(self.trade_engine.execute_trade.call_count, 2)


class TestOrderManager(unittest.IsolatedAsyncioTestCase):
    """Test OrderManager"""
    
    async def asyncSetUp(self):
        """Set up async test fixtures"""
        # Create mock trade engine
        self.mock_trade_engine = Mock(spec=TradeEngine)
        self.mock_trade_engine.agent = Mock()
        self.mock_trade_engine.agent.config = Mock()
        self.mock_trade_engine.agent.config.symbols = ["BTC-USD", "ETH-USD"]
        self.mock_trade_engine.agent.config.risk_management = {
            "position_limits": {
                "concentration_limits": {
                    "max_sector_exposure_percent": 50
                }
            }
        }
        
        # Create order manager
        self.order_manager = OrderManager(self.mock_trade_engine)
    
    async def test_validate_order_parameters(self):
        """Test order parameter validation"""
        # Valid parameters
        result = self.order_manager._validate_order_parameters(
            symbol="BTC-USD",
            side="buy",
            quantity=Decimal("0.001"),
            order_type=OrderType.MARKET,
            price=None
        )
        self.assertTrue(result)
        
        # Invalid side
        result = self.order_manager._validate_order_parameters(
            symbol="BTC-USD",
            side="invalid",
            quantity=Decimal("0.001"),
            order_type=OrderType.MARKET,
            price=None
        )
        self.assertFalse(result)
        
        # Invalid quantity
        result = self.order_manager._validate_order_parameters(
            symbol="BTC-USD",
            side="buy",
            quantity=Decimal("0"),
            order_type=OrderType.MARKET,
            price=None
        )
        self.assertFalse(result)
        
        # Limit order without price
        result = self.order_manager._validate_order_parameters(
            symbol="BTC-USD",
            side="buy",
            quantity=Decimal("0.001"),
            order_type=OrderType.LIMIT,
            price=None
        )
        self.assertFalse(result)
    
    async def test_detect_market_manipulation(self):
        """Test market manipulation detection"""
        # Test with no recent orders (should return False)
        result = await self.order_manager._detect_market_manipulation(
            symbol="BTC-USD",
            side="buy",
            quantity=Decimal("0.001")
        )
        self.assertFalse(result)
        
        # Add some cancelled orders to simulate spoofing
        self.order_manager.order_history = [
            Mock(symbol="BTC-USD", status="cancelled"),
            Mock(symbol="BTC-USD", status="cancelled"),
            Mock(symbol="BTC-USD", status="cancelled"),
            Mock(symbol="BTC-USD", status="cancelled")  # 4 cancelled orders
        ]
        
        result = await self.order_manager._detect_market_manipulation(
            symbol="BTC-USD",
            side="buy",
            quantity=Decimal("0.001")
        )
        self.assertTrue(result)
    
    async def test_get_order_statistics(self):
        """Test order statistics calculation"""
        # Add some orders to history
        self.order_manager.order_history = [
            Mock(status="filled", latency_ms=50, slippage=Decimal("0.001")),
            Mock(status="filled", latency_ms=60, slippage=Decimal("0.002")),
            Mock(status="cancelled"),
            Mock(status="rejected")
        ]
        
        stats = self.order_manager.get_order_statistics()
        
        self.assertEqual(stats["total_orders"], 4)
        self.assertEqual(stats["filled_orders"], 2)
        self.assertEqual(stats["cancelled_orders"], 1)
        self.assertEqual(stats["rejected_orders"], 1)
        self.assertEqual(stats["fill_rate_percent"], 50.0)
        self.assertEqual(stats["avg_latency_ms"], 55.0)
        self.assertEqual(stats["avg_slippage_percent"], 0.15)


if __name__ == "__main__":
    unittest.main()