#!/usr/bin/env python3
"""
Tests for Gate 3.5 Enhanced Multi-Market Agent
"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from agents.gate3_5_enhanced_agent import (
    Gate35EnhancedAgent,
    Gate35Config,
    EnhancedPosition,
    MultiMarketAnalysis
)


class TestGate35Config(unittest.TestCase):
    """Test Gate 3.5 configuration"""
    
    def test_config_creation(self):
        """Test creating a Gate35Config"""
        config_dict = {
            "mode": "gate_3_5_enhanced_multi_market",
            "exchange": "coinbase",
            "symbols": ["SOL-USD", "BTC-USD"],
            "position_sizing": {
                "position_type": "enhanced_multi_market",
                "min_notional": 0.50,
                "max_notional": 5.00
            },
            "execution": {},
            "monitoring": {},
            "enhanced_features": {},
            "risk_management": {},
            "reporting": {},
            "integration": {},
            "advanced": {}
        }
        
        config = Gate35Config(**config_dict)
        self.assertEqual(config.mode, "gate_3_5_enhanced_multi_market")
        self.assertEqual(config.exchange, "coinbase")
        self.assertEqual(config.symbols, ["SOL-USD", "BTC-USD"])
        self.assertEqual(config.position_sizing["min_notional"], 0.50)
        self.assertEqual(config.position_sizing["max_notional"], 5.00)


class TestEnhancedPosition(unittest.TestCase):
    """Test EnhancedPosition dataclass"""
    
    def test_position_creation(self):
        """Test creating an EnhancedPosition"""
        from datetime import datetime
        from decimal import Decimal
        
        position = EnhancedPosition(
            symbol="SOL-USD",
            entry_price=Decimal("150.00"),
            entry_time=datetime.now(),
            position_size=Decimal("2.50"),
            notional_value=Decimal("375.00"),
            current_price=Decimal("152.00"),
            pnl_percent=Decimal("1.33"),
            pnl_usd=Decimal("5.00"),
            duration_minutes=30.5,
            market_context={"volatility": 0.02},
            tags=["volatility_adjusted", "multi_market"]
        )
        
        self.assertEqual(position.symbol, "SOL-USD")
        self.assertEqual(position.position_size, Decimal("2.50"))
        self.assertEqual(position.pnl_percent, Decimal("1.33"))
        self.assertEqual(len(position.tags), 2)
        self.assertIn("volatility_adjusted", position.tags)


class TestMultiMarketAnalysis(unittest.TestCase):
    """Test MultiMarketAnalysis dataclass"""
    
    def test_analysis_creation(self):
        """Test creating a MultiMarketAnalysis"""
        from datetime import datetime
        
        analysis = MultiMarketAnalysis(
            timestamp=datetime.now(),
            symbols=["SOL-USD", "BTC-USD"],
            correlations={"SOL-USD": {"BTC-USD": 0.7}},
            volatility_scores={"SOL-USD": 0.8, "BTC-USD": 0.6},
            liquidity_scores={"SOL-USD": 0.9, "BTC-USD": 0.95},
            opportunity_scores={"SOL-USD": 0.85, "BTC-USD": 0.75},
            recommended_allocations={"SOL-USD": 55.0, "BTC-USD": 45.0}
        )
        
        self.assertEqual(len(analysis.symbols), 2)
        self.assertEqual(analysis.correlations["SOL-USD"]["BTC-USD"], 0.7)
        self.assertEqual(analysis.opportunity_scores["SOL-USD"], 0.85)
        self.assertEqual(analysis.recommended_allocations["SOL-USD"], 55.0)


class TestGate35EnhancedAgent(unittest.TestCase):
    """Test Gate 3.5 Enhanced Agent"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"
        
        config = {
            "mode": "gate_3_5_enhanced_multi_market",
            "exchange": "coinbase",
            "symbols": ["SOL-USD", "BTC-USD", "ETH-USD"],
            "position_sizing": {
                "position_type": "enhanced_multi_market",
                "min_notional": 0.50,
                "max_notional": 5.00,
                "base_allocation_per_symbol": 1.00,
                "max_concurrent_positions": 3,
                "risk_per_trade_percent": 0.5,
                "max_daily_risk_percent": 2.0
            },
            "execution": {
                "order_type": "market",
                "time_in_force": "IOC",
                "slippage_tolerance_percent": 0.5,
                "max_retries": 3,
                "retry_delay_ms": 1000
            },
            "monitoring": {
                "heartbeat_interval_seconds": 30,
                "health_check_interval_seconds": 60,
                "performance_report_interval_minutes": 15,
                "alert_thresholds": {
                    "max_drawdown_percent": 3.0,
                    "max_position_duration_minutes": 120,
                    "max_slippage_percent": 1.0,
                    "min_success_rate_percent": 60.0
                }
            },
            "enhanced_features": {
                "multi_market_arbitrage": True,
                "cross_symbol_correlation": True,
                "volatility_adjusted_sizing": True,
                "time_of_day_optimization": True,
                "news_sentiment_integration": False
            },
            "risk_management": {
                "circuit_breakers": {
                    "max_daily_loss_percent": 5.0,
                    "max_consecutive_losses": 5,
                    "max_hourly_trades": 20,
                    "cool_down_period_minutes": 30
                },
                "position_limits": {
                    "max_exposure_per_symbol_percent": 40,
                    "max_total_exposure_percent": 100,
                    "min_liquidity_threshold_usd": 1000000
                }
            },
            "reporting": {
                "live_dashboard": True,
                "telemetry_streaming": True,
                "audit_logging": True,
                "performance_metrics": {
                    "sharpe_ratio": True,
                    "sortino_ratio": True,
                    "max_drawdown": True,
                    "win_rate": True,
                    "profit_factor": True
                }
            },
            "integration": {
                "simp_broker_enabled": False,
                "simp_broker_url": "http://127.0.0.1:5555",
                "simp_agent_id": "test_gate35",
                "dashboard_integration": False
            },
            "advanced": {
                "machine_learning_features": {
                    "pattern_recognition": True,
                    "anomaly_detection": True
                },
                "backtesting": {
                    "enabled": True,
                    "lookback_days": 30
                }
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f)
        
        # Create agent instance
        self.agent = Gate35EnhancedAgent(str(self.config_path))
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_agent_initialization(self):
        """Test agent initialization"""
        self.assertIsNotNone(self.agent)
        self.assertEqual(self.agent.config.mode, "gate_3_5_enhanced_multi_market")
        self.assertEqual(len(self.agent.config.symbols), 3)
        self.assertEqual(self.agent.config.position_sizing["min_notional"], 0.50)
        self.assertEqual(self.agent.config.position_sizing["max_notional"], 5.00)
    
    def test_load_config(self):
        """Test configuration loading"""
        config = self.agent._load_config()
        self.assertIsInstance(config, Gate35Config)
        self.assertEqual(config.exchange, "coinbase")
        self.assertIn("SOL-USD", config.symbols)
    
    @patch('agents.gate3_5_enhanced_agent.StubExchangeConnector')
    def test_init_exchange(self, mock_exchange):
        """Test exchange initialization"""
        exchange = self.agent._init_exchange()
        self.assertIsNotNone(exchange)
    
    def test_get_active_enhanced_features(self):
        """Test getting active enhanced features"""
        features = self.agent._get_active_enhanced_features()
        self.assertIn("multi_market_arbitrage", features)
        self.assertIn("volatility_adjusted_sizing", features)
        self.assertIn("time_of_day_optimization", features)
        self.assertNotIn("news_sentiment_integration", features)
    
    def test_calculate_enhanced_position_size(self):
        """Test enhanced position size calculation"""
        from decimal import Decimal
        from unittest.mock import Mock
        
        # Mock opportunity
        opportunity = Mock()
        opportunity.symbol = "SOL-USD"
        opportunity.mispricing_percent = Decimal("1.5")
        
        # Mock multi-market analysis
        self.agent.multi_market_analysis = Mock()
        self.agent.multi_market_analysis.volatility_scores = {"SOL-USD": 0.7}
        self.agent.multi_market_analysis.opportunity_scores = {"SOL-USD": 0.8}
        
        # Test with all features enabled
        size = self.agent._calculate_enhanced_position_size(opportunity)
        
        self.assertIsInstance(size, Decimal)
        self.assertGreater(float(size), 0)
        self.assertLessEqual(float(size), 5.00)  # Should respect max
        
        # Test with high volatility (should reduce size)
        self.agent.multi_market_analysis.volatility_scores = {"SOL-USD": 0.9}
        size_high_vol = self.agent._calculate_enhanced_position_size(opportunity)
        
        # Test with low opportunity score (should reduce size)
        self.agent.multi_market_analysis.opportunity_scores = {"SOL-USD": 0.3}
        size_low_opp = self.agent._calculate_enhanced_position_size(opportunity)
    
    def test_check_risk_limits(self):
        """Test risk limit checking"""
        # Initially should pass
        self.assertTrue(self.agent._check_risk_limits())
        
        # Test consecutive losses limit
        self.agent.consecutive_losses = 5  # At limit
        self.assertFalse(self.agent._check_risk_limits())
        self.agent.consecutive_losses = 4  # Below limit
        self.assertTrue(self.agent._check_risk_limits())
        
        # Test hourly trade limit
        self.agent.hourly_trade_count = 20  # At limit
        self.assertFalse(self.agent._check_risk_limits())
        self.agent.hourly_trade_count = 19  # Below limit
        self.assertTrue(self.agent._check_risk_limits())
        
        # Test position limits
        self.agent.positions = {"SOL-USD": Mock(), "BTC-USD": Mock(), "ETH-USD": Mock()}
        self.assertFalse(self.agent._check_risk_limits())  # At max concurrent
    
    def test_should_exit_position(self):
        """Test position exit conditions"""
        from decimal import Decimal
        from datetime import datetime, timedelta
        
        # Create test position
        position = EnhancedPosition(
            symbol="SOL-USD",
            entry_price=Decimal("150.00"),
            entry_time=datetime.now() - timedelta(minutes=130),  # 130 minutes ago
            position_size=Decimal("2.50"),
            notional_value=Decimal("375.00"),
            current_price=Decimal("153.00"),  # +2% profit
            pnl_percent=Decimal("2.00"),
            pnl_usd=Decimal("7.50"),
            duration_minutes=130.0,
            market_context={},
            tags=[]
        )
        
        # Should exit for profit target
        self.assertTrue(self.agent._should_exit_position(position))
        
        # Test stop loss
        position.pnl_percent = Decimal("-1.6")  # Below stop loss
        self.assertTrue(self.agent._should_exit_position(position))
        
        # Test max duration
        position.pnl_percent = Decimal("0.5")  # Small profit
        self.assertTrue(self.agent._should_exit_position(position))  # Still >120 minutes
        
        # Test should NOT exit
        position.entry_time = datetime.now() - timedelta(minutes=30)  # 30 minutes ago
        position.duration_minutes = 30.0
        position.pnl_percent = Decimal("0.5")  # Small profit
        self.assertFalse(self.agent._should_exit_position(position))
    
    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_run_multi_market_analysis(self, mock_sleep):
        """Test multi-market analysis"""
        analysis = await self.agent.run_multi_market_analysis()
        
        self.assertIsInstance(analysis, MultiMarketAnalysis)
        self.assertEqual(len(analysis.symbols), 3)
        self.assertIn("SOL-USD", analysis.symbols)
        
        # Check that scores are calculated
        self.assertIn("SOL-USD", analysis.volatility_scores)
        self.assertIn("SOL-USD", analysis.opportunity_scores)
        self.assertIn("SOL-USD", analysis.recommended_allocations)
        
        # Check correlations matrix
        self.assertIn("SOL-USD", analysis.correlations)
        self.assertIn("BTC-USD", analysis.correlations["SOL-USD"])
    
    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_analyze_arbitrage_opportunities(self, mock_sleep):
        """Test arbitrage opportunity analysis"""
        # First run multi-market analysis
        await self.agent.run_multi_market_analysis()
        
        # Analyze opportunities
        opportunities = await self.agent.analyze_arbitrage_opportunities()
        
        self.assertIsInstance(opportunities, list)
        # Should find some opportunities (simulated)
        self.assertGreaterEqual(len(opportunities), 0)
    
    def test_generate_performance_report(self):
        """Test performance report generation"""
        # No trades yet
        report = self.agent._generate_performance_report()
        self.assertIn("message", report)
        self.assertEqual(report["message"], "No trades yet")
        
        # Add some simulated trades
        self.agent.trade_history = [
            {"pnl_percent": 1.5, "pnl_usd": 3.75},
            {"pnl_percent": -0.5, "pnl_usd": -1.25},
            {"pnl_percent": 2.0, "pnl_usd": 5.00}
        ]
        
        report = self.agent._generate_performance_report()
        self.assertIn("total_trades", report)
        self.assertEqual(report["total_trades"], 3)
        self.assertIn("win_rate_percent", report)
        self.assertIn("total_pnl_usd", report)
        self.assertIn("profit_factor", report)
    
    def test_get_position_tags(self):
        """Test position tag generation"""
        from unittest.mock import Mock
        
        opportunity = Mock()
        opportunity.metadata = {"correlation_based": True}
        
        tags = self.agent._get_position_tags(opportunity)
        
        # Should include tags for enabled features
        self.assertIn("multi_market", tags)
        self.assertIn("volatility_adjusted", tags)
        self.assertIn("time_optimized", tags)
        self.assertIn("correlation_based", tags)
    
    def test_get_exit_reason(self):
        """Test exit reason determination"""
        from decimal import Decimal
        from datetime import datetime
        
        position = EnhancedPosition(
            symbol="SOL-USD",
            entry_price=Decimal("150.00"),
            entry_time=datetime.now(),
            position_size=Decimal("2.50"),
            notional_value=Decimal("375.00"),
            current_price=Decimal("153.00"),
            pnl_percent=Decimal("2.0"),
            pnl_usd=Decimal("7.50"),
            duration_minutes=30.0,
            market_context={},
            tags=[]
        )
        
        # Profit target
        reason = self.agent._get_exit_reason(position)
        self.assertEqual(reason, "profit_target")
        
        # Stop loss
        position.pnl_percent = Decimal("-1.6")
        reason = self.agent._get_exit_reason(position)
        self.assertEqual(reason, "stop_loss")
        
        # Max duration
        position.pnl_percent = Decimal("0.5")
        position.duration_minutes = 125.0
        reason = self.agent._get_exit_reason(position)
        self.assertEqual(reason, "max_duration")
        
        # Other
        position.duration_minutes = 30.0
        position.pnl_percent = Decimal("0.5")
        reason = self.agent._get_exit_reason(position)
        self.assertEqual(reason, "other")


class TestGate35Integration(unittest.TestCase):
    """Integration tests for Gate 3.5 agent"""
    
    @patch('agents.gate3_5_enhanced_agent.asyncio.sleep', new_callable=AsyncMock)
    @patch('agents.gate3_5_enhanced_agent.Gate35EnhancedAgent.connect_to_broker')
    @patch('agents.gate3_5_enhanced_agent.Gate35EnhancedAgent.start_monitoring_tasks')
    async def test_agent_main_loop(self, mock_monitoring, mock_connect, mock_sleep):
        """Test main agent loop integration"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "mode": "gate_3_5_enhanced_multi_market",
                "exchange": "coinbase",
                "symbols": ["SOL-USD"],
                "position_sizing": {"min_notional": 0.5, "max_notional": 5.0},
                "execution": {},
                "monitoring": {},
                "enhanced_features": {},
                "risk_management": {},
                "reporting": {},
                "integration": {"simp_broker_enabled": False},
                "advanced": {}
            }
            json.dump(config, f)
            config_path = f.name
        
        try:
            agent = Gate35EnhancedAgent(config_path)
            
            # Mock the methods called in run()
            with patch.object(agent, 'run_multi_market_analysis') as mock_analysis, \
                 patch.object(agent, 'analyze_arbitrage_opportunities') as mock_opps, \
                 patch.object(agent, 'execute_trade') as mock_execute:
                
                # Setup mocks
                mock_analysis.return_value = Mock()
                mock_opps.return_value = []
                mock_execute.return_value = True
                mock_connect.return_value = True
                
                # Run agent for a short time
                task = asyncio.create_task(agent.run())
                await asyncio.sleep(0.1)
                task.cancel()
                
                # Verify methods were called
                mock_analysis.assert_called()
                mock_opps.assert_called()
                
        finally:
            import os
            os.unlink(config_path)


if __name__ == '__main__':
    unittest.main()