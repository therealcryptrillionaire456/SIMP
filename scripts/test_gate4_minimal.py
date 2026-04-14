#!/usr/bin/env python3
"""
Minimal test for Gate 4 agent without SIMP dependencies
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test basic imports without SIMP
print("Testing basic imports...")

try:
    from agents.gate4_scaled_agent_part1 import (
        TradingStrategy, OrderType, Gate4Config
    )
    print("✓ Successfully imported from gate4_scaled_agent_part1")
    
    # Test creating a config
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
    print(f"✓ Created Gate4Config: mode={config.mode}, exchange={config.exchange}")
    print(f"  Position sizing: ${config.position_sizing['min_notional']}-${config.position_sizing['max_notional']}")
    
except Exception as e:
    print(f"✗ Error importing from part1: {e}")
    sys.exit(1)

try:
    from agents.gate4_scaled_agent_part2a import (
        TradeExecution, PositionState, PerformanceMetrics
    )
    print("✓ Successfully imported from gate4_scaled_agent_part2a")
except Exception as e:
    print(f"✗ Error importing from part2a: {e}")
    sys.exit(1)

try:
    from agents.gate4_scaled_agent_part2b import (
        OrderReconciliation, RiskExposure, ComplianceRecord
    )
    print("✓ Successfully imported from gate4_scaled_agent_part2b")
except Exception as e:
    print(f"✗ Error importing from part2b: {e}")
    sys.exit(1)

try:
    from agents.gate4_scaled_agent_part3 import (
        TelemetryData, Alert
    )
    print("✓ Successfully imported from gate4_scaled_agent_part3")
except Exception as e:
    print(f"✗ Error importing from part3: {e}")
    sys.exit(1)

print("\nAll basic imports successful!")
print("\nTesting enum values...")

# Test enum values
print(f"TradingStrategy.MEAN_REVERSION = {TradingStrategy.MEAN_REVERSION}")
print(f"OrderType.MARKET = {OrderType.MARKET}")

print("\n✓ Gate 4 agent components are ready for testing!")