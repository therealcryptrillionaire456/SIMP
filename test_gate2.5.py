#!/usr/bin/env python3.10
"""Test Gate 2.5 agent."""

import sys
sys.path.insert(0, '.')

import importlib.util
import sys

# Dynamically import the module with dot in name
spec = importlib.util.spec_from_file_location(
    "quantumarb_gate2_5", 
    "simp/agents/quantumarb_gate2.5.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules["quantumarb_gate2_5"] = module
spec.loader.exec_module(module)
QuantumArbGate2_5 = module.QuantumArbGate2_5
import json
from pathlib import Path

# Create a minimal test config
test_config = {
    "mode": "gate_2.5_enhanced_sol",
    "exchange": "coinbase",
    "symbols": ["SOL-USD"],
    "position_sizing": {
        "position_type": "enhanced_dollar",
        "min_notional": 0.10,
        "max_notional": 0.50,
        "default_notional": 0.25,
        "size_tiers": {
            "tier_1": {"risk_score": 0.70, "size": 0.50},
            "tier_2": {"risk_score": 0.65, "size": 0.35},
            "tier_3": {"risk_score": 0.60, "size": 0.25},
            "tier_4": {"risk_score": 0.55, "size": 0.15},
            "tier_5": {"risk_score": 0.50, "size": 0.10}
        }
    },
    "risk_management": {
        "multi_factor_scoring": True,
        "factors": {
            "spread": {"weight": 0.35, "min": 0.02, "max": 0.30, "normalization": 0.25},
            "confidence": {"weight": 0.30, "min": 0.75},
            "liquidity": {"weight": 0.15, "score": 0.9},
            "volatility": {"weight": 0.12, "max": 0.25},
            "slippage": {"weight": 0.08, "max": 0.03}
        },
        "minimum_score": 0.55,
        "size_adjustment": True,
        "symbol_specific": {
            "SOL-USD": {
                "liquidity_score": 0.9,
                "volatility_factor": 0.8,
                "spread_normalization": 0.25
            }
        }
    },
    "execution": {
        "order_types": ["limit"],
        "default_order_type": "limit",
        "time_in_force": "IOC",
        "max_slippage_bps": 10,
        "allow_partial_fills": True,
        "min_fill_percentage": 70,
        "price_improvement_target": 0.005
    },
    "targets": {
        "total_trades": 10,  # Small for testing
        "min_for_success": 8,
        "execution_success_rate": 90,
        "max_slippage_average": 5,
        "risk_score_stability": 0.1
    }
}

# Save test config
test_config_path = Path("config/test_gate2.5.json")
test_config_path.parent.mkdir(parents=True, exist_ok=True)
with open(test_config_path, 'w') as f:
    json.dump(test_config, f, indent=2)

print("Testing Gate 2.5 Enhanced SOL Agent...")
print("="*60)

try:
    # Create agent
    agent = QuantumArbGate2_5(str(test_config_path))
    
    # Run a short test session
    print("\nRunning test session (will stop after ~10 trades)...")
    print("Press Ctrl+C to stop early")
    print("-"*60)
    
    agent.run_session()
    
    print("\n" + "="*60)
    print("Test completed successfully!")
    
    # Check results
    results_file = list(Path("data/quantumarb_gate2.5").glob("session_summary_*.json"))
    if results_file:
        with open(results_file[0], 'r') as f:
            results = json.load(f)
        
        print(f"\nSession Results:")
        print(f"  Trades executed: {results.get('trades_executed', 0)}")
        print(f"  Total P&L: ${results.get('total_pnl', 0.0):.6f}")
        print(f"  Opportunities evaluated: {results.get('opportunities_evaluated', 0)}")
        
        decisions = results.get('decisions', {})
        if decisions:
            print(f"\nDecision breakdown:")
            for decision, count in decisions.items():
                if count > 0:
                    print(f"  {decision}: {count}")
        
        # Check if minimum success criteria met
        min_for_success = test_config["targets"]["min_for_success"]
        trades_executed = results.get('trades_executed', 0)
        
        if trades_executed >= min_for_success:
            print(f"\n✅ GATE 2.5 TEST SUCCESS: {trades_executed}/{min_for_success} minimum trades executed")
        else:
            print(f"\n⚠️ GATE 2.5 TEST INCOMPLETE: {trades_executed}/{min_for_success} trades (minimum not met)")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    if test_config_path.exists():
        test_config_path.unlink()