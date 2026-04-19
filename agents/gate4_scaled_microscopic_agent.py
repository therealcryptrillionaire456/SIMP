#!/usr/bin/env python3
"""
Gate 4 Scaled Microscopic Agent
Full production-ready agent with $1-$10 position sizes

This is the unified main agent file that imports all components.
"""

import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Try to import SIMP modules, but don't fail if they're not available
try:
    import numpy as np
    import pandas as pd
    # SIMP imports
    from simp.server.broker import SimpBroker
    from simp.models.canonical_intent import CanonicalIntent
    # FinancialOps import removed as it doesn't exist in the module
    from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity
    from simp.organs.quantumarb.exchange_connector import ExchangeConnector, StubExchangeConnector
    SIMP_AVAILABLE = True
except ImportError as e:
    print(f"Note: Some SIMP dependencies not available: {e}")
    print("Running in validation mode only.")
    SIMP_AVAILABLE = False
    # Create dummy classes for validation
    class SimpBroker:
        pass
    class CanonicalIntent:
        pass
    class ArbDetector:
        pass
    class ArbOpportunity:
        pass
    class ExchangeConnector:
        pass
    class StubExchangeConnector:
        pass

# Import all components
from gate4_scaled_agent_part1 import (
    TradingStrategy, OrderType, Gate4Config, ScaledPosition, 
    MarketMicrostructure, RiskMetrics, Gate4ScaledAgent
)
from gate4_scaled_agent_part2a import (
    TradeExecution, PositionState, PerformanceMetrics, TradeEngine
)
from gate4_scaled_agent_part2b import (
    OrderReconciliation, RiskExposure, ComplianceRecord, OrderManager
)
from gate4_scaled_agent_part3 import (
    TelemetryData, Alert, Gate4ScaledMicroscopicAgent
)

logger = logging.getLogger(__name__)


def run_agent(config_path: str = "config/gate4_scaled_microscopic.json"):
    """
    Run the Gate 4 Scaled Microscopic Agent
    
    Args:
        config_path: Path to configuration file
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/gate4_agent.log'),
            logging.StreamHandler()
        ]
    )
    
    logger.info("=" * 60)
    logger.info("Gate 4 Scaled Microscopic Agent Starting")
    logger.info(f"Config: {config_path}")
    logger.info("=" * 60)
    
    async def _run():
        # Create agent
        agent = Gate4ScaledMicroscopicAgent(config_path)
        
        try:
            # Start agent
            await agent.start()
            
            # Keep running until stopped
            while agent.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Agent error: {e}")
        finally:
            # Stop agent gracefully
            await agent.stop()
        
        logger.info("=" * 60)
        logger.info("Gate 4 Scaled Microscopic Agent Stopped")
        logger.info("=" * 60)
    
    # Run the agent
    asyncio.run(_run())


def get_agent_status() -> Dict[str, Any]:
    """
    Get current agent status without starting it
    
    Returns:
        Dictionary with agent status information
    """
    try:
        # Check if agent is running by looking for log file
        log_path = Path("logs/gate4_agent.log")
        if log_path.exists():
            with open(log_path, "r") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    return {
                        "status": "running",
                        "last_log": last_line,
                        "log_size_kb": log_path.stat().st_size / 1024
                    }
        
        return {"status": "stopped"}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


def validate_config(config_path: str = "config/gate4_scaled_microscopic.json") -> Dict[str, Any]:
    """
    Validate Gate 4 configuration
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dictionary with validation results
    """
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # Required fields
        required_fields = ["mode", "exchange", "symbols", "position_sizing"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            return {
                "valid": False,
                "error": f"Missing required fields: {missing_fields}"
            }
        
        # Validate position sizing
        ps = config.get("position_sizing", {})
        if ps.get("min_notional", 0) < 1.0:
            return {
                "valid": False,
                "error": "min_notional must be >= 1.0"
            }
        
        if ps.get("max_notional", 0) > 10.0:
            return {
                "valid": False,
                "error": "max_notional must be <= 10.0 for Gate 4"
            }
        
        if ps.get("min_notional", 0) > ps.get("max_notional", 0):
            return {
                "valid": False,
                "error": "min_notional cannot be greater than max_notional"
            }
        
        # Validate symbols
        symbols = config.get("symbols", [])
        if not symbols:
            return {
                "valid": False,
                "error": "No symbols configured"
            }
        
        # Validate risk management
        rm = config.get("risk_management", {})
        cb = rm.get("circuit_breakers", {})
        if cb.get("max_daily_loss_percent", 100) > 10:
            return {
                "valid": False,
                "warning": "max_daily_loss_percent is high for Gate 4"
            }
        
        return {
            "valid": True,
            "config_summary": {
                "mode": config.get("mode"),
                "exchange": config.get("exchange"),
                "symbols_count": len(symbols),
                "position_sizing": {
                    "min_notional": ps.get("min_notional"),
                    "max_notional": ps.get("max_notional"),
                    "max_concurrent_positions": ps.get("max_concurrent_positions")
                }
            }
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Configuration error: {str(e)}"
        }


def create_default_config(output_path: str = "config/gate4_scaled_microscopic.json"):
    """
    Create default Gate 4 configuration
    
    Args:
        output_path: Path to save configuration file
    """
    config = {
        "mode": "gate_4_scaled_microscopic",
        "exchange": "coinbase",
        "symbols": ["SOL-USD", "BTC-USD", "ETH-USD", "AVAX-USD", "MATIC-USD"],
        "position_sizing": {
            "position_type": "scaled_production",
            "min_notional": 1.00,
            "max_notional": 10.00,
            "base_allocation_per_symbol": 2.00,
            "max_concurrent_positions": 5,
            "risk_per_trade_percent": 0.75,
            "max_daily_risk_percent": 3.0,
            "dynamic_sizing_enabled": true,
            "volatility_scaling_factor": 0.8,
            "liquidity_scaling_factor": 1.2
        },
        "execution": {
            "order_type": "market",
            "time_in_force": "IOC",
            "slippage_tolerance_percent": 0.3,
            "max_retries": 5,
            "retry_delay_ms": 500,
            "partial_fill_handling": "complete_or_cancel",
            "smart_order_routing": true,
            "iceberg_orders": false,
            "twap_vwap_enabled": false
        },
        "monitoring": {
            "heartbeat_interval_seconds": 15,
            "health_check_interval_seconds": 30,
            "performance_report_interval_minutes": 10,
            "real_time_telemetry": true,
            "alert_thresholds": {
                "max_drawdown_percent": 2.5,
                "max_position_duration_minutes": 90,
                "max_slippage_percent": 0.8,
                "min_success_rate_percent": 65.0,
                "max_order_latency_ms": 500,
                "min_fill_rate_percent": 95.0
            },
            "circuit_breaker_levels": {
                "warning": 75,
                "critical": 90,
                "shutdown": 100
            }
        },
        "enhanced_features": {
            "multi_market_arbitrage": true,
            "cross_symbol_correlation": true,
            "volatility_adjusted_sizing": true,
            "time_of_day_optimization": true,
            "news_sentiment_integration": false,
            "market_maker_mode": false,
            "statistical_arbitrage": true,
            "pairs_trading": true,
            "momentum_scalping": true,
            "mean_reversion": true
        },
        "risk_management": {
            "circuit_breakers": {
                "max_daily_loss_percent": 4.0,
                "max_consecutive_losses": 4,
                "max_hourly_trades": 30,
                "cool_down_period_minutes": 15,
                "auto_recovery_enabled": true,
                "recovery_wait_minutes": 5
            },
            "position_limits": {
                "max_exposure_per_symbol_percent": 30,
                "max_total_exposure_percent": 150,
                "min_liquidity_threshold_usd": 5000000,
                "max_leverage": 1.0,
                "concentration_limits": {
                    "max_sector_exposure_percent": 50,
                    "max_correlation_exposure_percent": 70
                }
            },
            "value_at_risk": {
                "enabled": true,
                "confidence_level": 0.95,
                "lookback_days": 30,
                "max_var_percent": 2.0
            },
            "stress_testing": {
                "enabled": true,
                "scenarios": ["flash_crash", "liquidity_drain", "volatility_spike"],
                "frequency_hours": 24
            }
        },
        "reporting": {
            "live_dashboard": true,
            "telemetry_streaming": true,
            "audit_logging": true,
            "regulatory_reporting": false,
            "performance_metrics": {
                "sharpe_ratio": true,
                "sortino_ratio": true,
                "max_drawdown": true,
                "win_rate": true,
                "profit_factor": true,
                "calmar_ratio": true,
                "omega_ratio": true,
                "value_at_risk": true,
                "expected_shortfall": true
            },
            "real_time_analytics": {
                "trade_flow_analysis": true,
                "market_impact_measurement": true,
                "execution_quality_score": true,
                "alpha_decay_tracking": true
            }
        },
        "integration": {
            "simp_broker_enabled": true,
            "simp_broker_url": "http://127.0.0.1:5555",
            "simp_agent_id": "gate4_scaled",
            "dashboard_integration": true,
            "webhook_notifications": true,
            "api_rate_limits": {
                "requests_per_second": 10,
                "burst_capacity": 50
            },
            "external_data_sources": {
                "news_api": false,
                "social_sentiment": false,
                "on_chain_metrics": false,
                "options_flow": false
            }
        },
        "advanced": {
            "machine_learning_features": {
                "pattern_recognition": true,
                "anomaly_detection": true,
                "predictive_sizing": true,
                "reinforcement_learning": false,
                "neural_networks": false,
                "feature_engineering": {
                    "technical_indicators": true,
                    "market_microstructure": true,
                    "order_book_imbalance": true,
                    "volume_profile": true
                }
            },
            "backtesting": {
                "enabled": true,
                "lookback_days": 90,
                "resolution_minutes": 1,
                "commission_rate_percent": 0.08,
                "slippage_model": "proportional",
                "walk_forward_analysis": true,
                "monte_carlo_simulation": true
            },
            "optimization": {
                "genetic_algorithm_tuning": true,
                "grid_search_parameters": true,
                "real_time_adaptation": true,
                "hyperparameter_tuning": {
                    "enabled": true,
                    "frequency_days": 7,
                    "method": "bayesian"
                }
            },
            "scalability": {
                "horizontal_scaling": true,
                "max_parallel_symbols": 20,
                "load_balancing": true,
                "fault_tolerance": {
                    "redundant_instances": 2,
                    "auto_failover": true,
                    "state_recovery": true
                }
            }
        },
        "compliance": {
            "trade_surveillance": true,
            "market_abuse_detection": true,
            "best_execution_policy": true,
            "record_keeping": {
                "trade_records_years": 7,
                "communication_records_years": 5,
                "audit_trail_comprehensive": true
            },
            "regulatory_frameworks": {
                "mifid_ii": false,
                "sec_rule_15c3_5": false,
                "fatf_travel_rule": false
            }
        },
        "production_readiness": {
            "uptime_target_percent": 99.9,
            "mean_time_to_recovery_minutes": 5,
            "disaster_recovery": {
                "enabled": true,
                "recovery_point_objective_minutes": 15,
                "recovery_time_objective_minutes": 30
            },
            "monitoring_stack": {
                "prometheus_metrics": true,
                "grafana_dashboards": true,
                "alertmanager_integration": true,
                "log_aggregation": true
            },
            "ci_cd_pipeline": {
                "automated_testing": true,
                "canary_deployments": true,
                "blue_green_deployment": false,
                "rollback_automation": true
            }
        }
    }
    
    # Create directory if it doesn't exist
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write configuration
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"Default configuration created: {output_path}")
    return config


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Gate 4 Scaled Microscopic Agent")
    parser.add_argument("--config", default="config/gate4_scaled_microscopic.json",
                       help="Path to configuration file")
    parser.add_argument("--validate", action="store_true",
                       help="Validate configuration without running")
    parser.add_argument("--create-config", action="store_true",
                       help="Create default configuration")
    parser.add_argument("--status", action="store_true",
                       help="Check agent status")
    
    args = parser.parse_args()
    
    if args.create_config:
        create_default_config(args.config)
        print(f"Default configuration created: {args.config}")
        sys.exit(0)
    
    if args.validate:
        result = validate_config(args.config)
        if result["valid"]:
            print("✓ Configuration is valid")
            print(f"  Mode: {result['config_summary']['mode']}")
            print(f"  Exchange: {result['config_summary']['exchange']}")
            print(f"  Symbols: {result['config_summary']['symbols_count']}")
            print(f"  Position sizing: ${result['config_summary']['position_sizing']['min_notional']}-${result['config_summary']['position_sizing']['max_notional']}")
        else:
            print("✗ Configuration is invalid")
            print(f"  Error: {result.get('error', 'Unknown error')}")
        sys.exit(0)
    
    if args.status:
        status = get_agent_status()
        print(f"Agent status: {status['status']}")
        if status['status'] == 'running':
            print(f"  Last log: {status.get('last_log', 'N/A')}")
            print(f"  Log size: {status.get('log_size_kb', 0):.1f} KB")
        sys.exit(0)
    
    # Run the agent
    run_agent(args.config)