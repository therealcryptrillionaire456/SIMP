#!/usr/bin/env python3
"""
Validate Gate 4 configuration without requiring all dependencies
"""

import json
import sys
import os
from pathlib import Path

def validate_config(config_path: str = "config/gate4_scaled_microscopic.json"):
    """Validate configuration file"""
    
    if not os.path.exists(config_path):
        print(f"✗ Configuration file not found: {config_path}")
        print("Creating default configuration...")
        return create_default_config(config_path)
    
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Basic validation
        required_fields = ['mode', 'exchange', 'symbols', 'position_sizing']
        for field in required_fields:
            if field not in config_data:
                return {
                    'valid': False,
                    'error': f"Missing required field: {field}"
                }
        
        # Position sizing validation
        ps = config_data.get('position_sizing', {})
        if 'min_notional' not in ps or 'max_notional' not in ps:
            return {
                'valid': False,
                'error': "Position sizing must include min_notional and max_notional"
            }
        
        min_notional = ps['min_notional']
        max_notional = ps['max_notional']
        
        if min_notional <= 0:
            return {
                'valid': False,
                'error': f"min_notional must be > 0, got {min_notional}"
            }
        
        if max_notional <= min_notional:
            return {
                'valid': False,
                'error': f"max_notional ({max_notional}) must be > min_notional ({min_notional})"
            }
        
        # Check position sizing range
        if min_notional < 1.0 or max_notional > 10.0:
            print(f"⚠ Warning: Position sizing ${min_notional}-${max_notional} is outside recommended $1-$10 range")
        
        return {
            'valid': True,
            'config_summary': {
                'mode': config_data['mode'],
                'exchange': config_data['exchange'],
                'symbols_count': len(config_data['symbols']),
                'symbols': config_data['symbols'][:3],  # First 3 symbols
                'position_sizing': {
                    'min_notional': min_notional,
                    'max_notional': max_notional,
                    'max_concurrent_positions': ps.get('max_concurrent_positions', 'not specified')
                }
            }
        }
        
    except json.JSONDecodeError as e:
        return {
            'valid': False,
            'error': f"Invalid JSON: {e}"
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f"Validation error: {e}"
        }

def create_default_config(config_path: str):
    """Create default configuration"""
    
    default_config = {
        "mode": "gate_4_scaled_microscopic",
        "exchange": "coinbase",
        "symbols": ["SOL-USD", "BTC-USD", "ETH-USD", "AVAX-USD", "MATIC-USD"],
        "position_sizing": {
            "min_notional": 1.00,
            "max_notional": 10.00,
            "base_allocation_per_symbol": 2.00,
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
    
    # Create directory if it doesn't exist
    config_dir = os.path.dirname(config_path)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    # Write configuration
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    print(f"✓ Default configuration created: {config_path}")
    print(f"  Mode: {default_config['mode']}")
    print(f"  Exchange: {default_config['exchange']}")
    print(f"  Symbols: {len(default_config['symbols'])} symbols")
    print(f"  Position sizing: ${default_config['position_sizing']['min_notional']}-${default_config['position_sizing']['max_notional']}")
    
    return {
        'valid': True,
        'created': True,
        'config_path': config_path
    }

def main():
    """Main validation function"""
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--create-config':
        config_path = sys.argv[2] if len(sys.argv) > 2 else "config/gate4_scaled_microscopic.json"
        result = create_default_config(config_path)
        sys.exit(0 if result.get('valid', False) else 1)
    
    # Default: validate existing config
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/gate4_scaled_microscopic.json"
    result = validate_config(config_path)
    
    if result['valid']:
        print("✓ Configuration is valid")
        summary = result['config_summary']
        print(f"  Mode: {summary['mode']}")
        print(f"  Exchange: {summary['exchange']}")
        print(f"  Symbols: {summary['symbols_count']} symbols")
        if summary['symbols_count'] > 3:
            print(f"    Sample: {', '.join(summary['symbols'])}...")
        else:
            print(f"    {', '.join(summary['symbols'])}")
        print(f"  Position sizing: ${summary['position_sizing']['min_notional']}-${summary['position_sizing']['max_notional']}")
        sys.exit(0)
    else:
        print(f"✗ Configuration is invalid: {result.get('error', 'Unknown error')}")
        print(f"\nTo create a default configuration:")
        print(f"  python3.10 {sys.argv[0]} --create-config [config_path]")
        sys.exit(1)

if __name__ == "__main__":
    main()