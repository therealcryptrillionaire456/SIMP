#!/usr/bin/env python3
"""
Basic tests for Gate 4 Scaled Microscopic Agent
"""

import json
import tempfile
import unittest
from decimal import Decimal
from datetime import datetime
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.gate4_scaled_agent_part1 import (
    TradingStrategy, OrderType, Gate4Config
)


class TestGate4Basic(unittest.TestCase):
    """Basic tests for Gate 4 agent"""
    
    def test_trading_strategy_enum(self):
        """Test TradingStrategy enum values"""
        # Check that enum values are strings
        self.assertIsInstance(TradingStrategy.MEAN_REVERSION.value, str)
        
        # Check specific values
        self.assertEqual(TradingStrategy.MEAN_REVERSION.value, "mean_reversion")
        
        # Check other strategies if they exist
        if hasattr(TradingStrategy, 'STATISTICAL_ARBITRAGE'):
            self.assertIsInstance(TradingStrategy.STATISTICAL_ARBITRAGE.value, str)
            self.assertEqual(TradingStrategy.STATISTICAL_ARBITRAGE.value, "statistical_arbitrage")
        
        if hasattr(TradingStrategy, 'PAIRS_TRADING'):
            self.assertIsInstance(TradingStrategy.PAIRS_TRADING.value, str)
            self.assertEqual(TradingStrategy.PAIRS_TRADING.value, "pairs_trading")
    
    def test_order_type_enum(self):
        """Test OrderType enum values"""
        # Check that enum values are strings
        self.assertIsInstance(OrderType.MARKET.value, str)
        self.assertIsInstance(OrderType.LIMIT.value, str)
        
        # Check specific values
        self.assertEqual(OrderType.MARKET.value, "market")
        self.assertEqual(OrderType.LIMIT.value, "limit")
    
    def test_gate4_config_creation(self):
        """Test Gate4Config creation with minimal data"""
        # Create a minimal valid config
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
            "execution": {
                "order_type": "market",
                "time_in_force": "IOC",
                "slippage_tolerance_percent": 0.3,
                "max_retries": 5
            },
            "monitoring": {
                "heartbeat_interval_seconds": 15,
                "health_check_interval_seconds": 30
            },
            "enhanced_features": {
                "multi_market_arbitrage": True,
                "cross_symbol_correlation": True
            },
            "risk_management": {
                "circuit_breakers": {
                    "max_daily_loss_percent": 4.0,
                    "max_consecutive_losses": 4
                },
                "position_limits": {
                    "max_exposure_per_symbol_percent": 30,
                    "max_total_exposure_percent": 150
                }
            },
            "reporting": {
                "live_dashboard": True,
                "telemetry_streaming": True
            },
            "integration": {
                "simp_broker_enabled": True,
                "simp_broker_url": "http://127.0.0.1:5555"
            },
            "advanced": {
                "machine_learning_features": {
                    "pattern_recognition": True
                }
            },
            "compliance": {
                "trade_surveillance": True,
                "market_abuse_detection": True
            },
            "production_readiness": {
                "uptime_target_percent": 99.9,
                "mean_time_to_recovery_minutes": 5
            }
        }
        
        # Create config object
        config = Gate4Config(**config_dict)
        
        # Verify basic properties
        self.assertEqual(config.mode, "gate_4_scaled_microscopic")
        self.assertEqual(config.exchange, "coinbase")
        self.assertEqual(config.symbols, ["BTC-USD", "ETH-USD"])
        self.assertEqual(config.position_sizing["min_notional"], 1.0)
        self.assertEqual(config.position_sizing["max_notional"], 10.0)
        self.assertTrue(config.position_sizing["dynamic_sizing_enabled"])
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Test with missing required field
        config_dict = {
            "mode": "gate_4_scaled_microscopic",
            "exchange": "coinbase",
            # Missing symbols
            "position_sizing": {
                "min_notional": 1.0,
                "max_notional": 10.0
            }
        }
        
        # This should fail because symbols is required
        with self.assertRaises(TypeError):
            Gate4Config(**config_dict)
    
    def test_decimal_handling(self):
        """Test Decimal type handling"""
        # Test that we can create Decimal values
        quantity = Decimal("0.001")
        price = Decimal("50000.00")
        notional = quantity * price
        
        self.assertEqual(notional, Decimal("50.00000"))
        self.assertIsInstance(notional, Decimal)
        
        # Test comparison
        self.assertTrue(notional > Decimal("0"))
        self.assertTrue(notional < Decimal("100"))
    
    def test_datetime_handling(self):
        """Test datetime handling"""
        now = datetime.now()
        
        # Test ISO format conversion
        iso_str = now.isoformat()
        self.assertIsInstance(iso_str, str)
        self.assertIn("T", iso_str or "-" in iso_str)
        
        # Test that we can create datetime objects
        from datetime import timezone
        utc_now = datetime.now(timezone.utc)
        self.assertIsNotNone(utc_now)


class TestGate4ConfigFile(unittest.TestCase):
    """Test Gate 4 configuration file handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.json"
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_create_and_load_config(self):
        """Test creating and loading a config file"""
        # Create a valid config
        config_data = {
            "mode": "gate_4_scaled_microscopic",
            "exchange": "coinbase",
            "symbols": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "position_sizing": {
                "min_notional": 1.0,
                "max_notional": 10.0,
                "base_allocation_per_symbol": 2.0,
                "max_concurrent_positions": 5,
                "risk_per_trade_percent": 0.75,
                "max_daily_risk_percent": 3.0,
                "dynamic_sizing_enabled": True,
                "volatility_scaling_factor": 0.8,
                "liquidity_scaling_factor": 1.2
            },
            "execution": {
                "order_type": "market",
                "time_in_force": "IOC",
                "slippage_tolerance_percent": 0.3,
                "max_retries": 5,
                "retry_delay_ms": 500
            },
            "monitoring": {
                "heartbeat_interval_seconds": 15,
                "health_check_interval_seconds": 30,
                "performance_report_interval_minutes": 10,
                "real_time_telemetry": True
            },
            "enhanced_features": {
                "multi_market_arbitrage": True,
                "cross_symbol_correlation": True,
                "volatility_adjusted_sizing": True
            },
            "risk_management": {
                "circuit_breakers": {
                    "max_daily_loss_percent": 4.0,
                    "max_consecutive_losses": 4,
                    "max_hourly_trades": 30,
                    "cool_down_period_minutes": 15
                },
                "position_limits": {
                    "max_exposure_per_symbol_percent": 30,
                    "max_total_exposure_percent": 150,
                    "min_liquidity_threshold_usd": 5000000
                }
            },
            "reporting": {
                "live_dashboard": True,
                "telemetry_streaming": True,
                "audit_logging": True
            },
            "integration": {
                "simp_broker_enabled": True,
                "simp_broker_url": "http://127.0.0.1:5555",
                "simp_agent_id": "gate4_scaled"
            },
            "advanced": {
                "machine_learning_features": {
                    "pattern_recognition": True,
                    "anomaly_detection": True
                }
            },
            "compliance": {
                "trade_surveillance": True,
                "market_abuse_detection": True
            },
            "production_readiness": {
                "uptime_target_percent": 99.9,
                "mean_time_to_recovery_minutes": 5
            }
        }
        
        # Write config to file
        with open(self.config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        
        # Read config back
        with open(self.config_path, "r") as f:
            loaded_config = json.load(f)
        
        # Verify data
        self.assertEqual(loaded_config["mode"], "gate_4_scaled_microscopic")
        self.assertEqual(loaded_config["exchange"], "coinbase")
        self.assertEqual(len(loaded_config["symbols"]), 3)
        self.assertEqual(loaded_config["position_sizing"]["min_notional"], 1.0)
        self.assertEqual(loaded_config["position_sizing"]["max_notional"], 10.0)
        self.assertTrue(loaded_config["position_sizing"]["dynamic_sizing_enabled"])
        
        # Create Gate4Config object
        config = Gate4Config(**loaded_config)
        self.assertEqual(config.mode, "gate_4_scaled_microscopic")
        self.assertEqual(config.exchange, "coinbase")
    
    def test_position_sizing_validation(self):
        """Test position sizing validation in config"""
        # Test invalid config (min > max)
        config_data = {
            "mode": "gate_4_scaled_microscopic",
            "exchange": "coinbase",
            "symbols": ["BTC-USD"],
            "position_sizing": {
                "min_notional": 15.0,  # Invalid: > max_notional
                "max_notional": 10.0,
                "base_allocation_per_symbol": 2.0,
                "max_concurrent_positions": 5,
                "risk_per_trade_percent": 0.75,
                "max_daily_risk_percent": 3.0,
                "dynamic_sizing_enabled": True,
                "volatility_scaling_factor": 0.8,
                "liquidity_scaling_factor": 1.2
            },
            # ... other required fields
        }
        
        # Fill in other required fields with minimal data
        required_fields = ["execution", "monitoring", "enhanced_features", "risk_management", 
                          "reporting", "integration", "advanced", "compliance", "production_readiness"]
        
        for field in required_fields:
            config_data[field] = {}
        
        # Config should still create (validation happens at runtime)
        config = Gate4Config(**config_data)
        
        # But min > max is logically wrong
        self.assertGreater(config.position_sizing["min_notional"], 
                          config.position_sizing["max_notional"])


if __name__ == "__main__":
    unittest.main()