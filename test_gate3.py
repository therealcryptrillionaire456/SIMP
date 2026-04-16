#!/usr/bin/env python3.10
"""Test Gate 3 multi-market agent."""

import sys
sys.path.insert(0, '.')

import importlib.util
import json
from pathlib import Path

# Dynamically import the module
spec = importlib.util.spec_from_file_location(
    "quantumarb_gate3", 
    "simp/agents/quantumarb_gate3.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules["quantumarb_gate3"] = module
spec.loader.exec_module(module)
QuantumArbGate3 = module.QuantumArbGate3

# Create a minimal test config
test_config = {
    "mode": "gate_3_multi_market",
    "exchange": "coinbase",
    "symbols": ["SOL-USD", "BTC-USD", "ETH-USD"],
    "position_sizing": {
        "position_type": "symbol_scaled",
        "min_notional": 0.10,
        "max_notional": 1.00,
        "default_notional": 0.50,
        "size_by_symbol": {
            "SOL-USD": 0.50,
            "BTC-USD": 0.30,
            "ETH-USD": 0.20
        },
        "size_tiers": {
            "tier_1": {"risk_score": 0.75, "size_multiplier": 1.0},
            "tier_2": {"risk_score": 0.70, "size_multiplier": 0.8},
            "tier_3": {"risk_score": 0.65, "size_multiplier": 0.6},
            "tier_4": {"risk_score": 0.60, "size_multiplier": 0.4},
            "tier_5": {"risk_score": 0.55, "size_multiplier": 0.2}
        }
    },
    "risk_management": {
        "multi_factor_scoring": True,
        "factors": {
            "spread": {
                "weight": 0.30,
                "min_by_symbol": {
                    "SOL-USD": 0.02,
                    "BTC-USD": 0.01,
                    "ETH-USD": 0.015
                },
                "max_by_symbol": {
                    "SOL-USD": 0.30,
                    "BTC-USD": 0.20,
                    "ETH-USD": 0.25
                },
                "normalization_by_symbol": {
                    "SOL-USD": 0.25,
                    "BTC-USD": 0.15,
                    "ETH-USD": 0.20
                }
            },
            "confidence": {
                "weight": 0.25,
                "min": 0.75
            },
            "liquidity": {
                "weight": 0.20,
                "scores_by_symbol": {
                    "SOL-USD": 0.9,
                    "BTC-USD": 0.95,
                    "ETH-USD": 0.85
                }
            },
            "volatility": {
                "weight": 0.15,
                "max_by_symbol": {
                    "SOL-USD": 0.25,
                    "BTC-USD": 0.20,
                    "ETH-USD": 0.22
                }
            },
            "slippage": {
                "weight": 0.10,
                "max_by_symbol": {
                    "SOL-USD": 0.03,
                    "BTC-USD": 0.02,
                    "ETH-USD": 0.025
                }
            }
        },
        "minimum_score_by_symbol": {
            "SOL-USD": 0.60,
            "BTC-USD": 0.65,
            "ETH-USD": 0.62
        },
        "size_adjustment": True
    },
    "targets": {
        "total_trades": 30,  # Small for testing
        "min_for_success": 24,
        "trades_by_symbol": {
            "SOL-USD": 12,
            "BTC-USD": 9,
            "ETH-USD": 9
        },
        "min_trades_per_symbol": {
            "SOL-USD": 10,
            "BTC-USD": 7,
            "ETH-USD": 7
        },
        "execution_success_rate": 90,
        "max_slippage_average": 8
    }
}

# Save test config
test_config_path = Path("config/test_gate3.json")
test_config_path.parent.mkdir(parents=True, exist_ok=True)
with open(test_config_path, 'w') as f:
    json.dump(test_config, f, indent=2)

print("Testing Gate 3 Multi-Market Agent...")
print("="*70)

try:
    # Create agent
    agent = QuantumArbGate3(str(test_config_path))
    
    # Run a short test session
    print("\nRunning test session (will stop after ~30 trades)...")
    print("Press Ctrl+C to stop early")
    print("-"*70)
    
    agent.run_session()
    
    print("\n" + "="*70)
    print("Test completed successfully!")
    
    # Check results
    results_file = list(Path("data/quantumarb_gate3").glob("session_summary_*.json"))
    if results_file:
        with open(results_file[0], 'r') as f:
            results = json.load(f)
        
        print(f"\nSession Results:")
        print(f"  Trades executed: {results.get('trades_executed', 0)}")
        print(f"  Total P&L: ${results.get('total_pnl', 0.0):.6f}")
        print(f"  Opportunities evaluated: {results.get('opportunities_evaluated', 0)}")
        
        # Check symbol performances
        performances = results.get('symbol_performances', [])
        if performances:
            print(f"\nSymbol Performance:")
            for perf in performances:
                print(f"  {perf['symbol']}: {perf['trades_executed']} trades, P&L: ${perf['total_pnl']:.6f}")
        
        # Check if minimum success criteria met
        min_for_success = test_config["targets"]["min_for_success"]
        trades_executed = results.get('trades_executed', 0)
        
        if trades_executed >= min_for_success:
            print(f"\n✅ GATE 3 TEST SUCCESS: {trades_executed}/{min_for_success} minimum trades executed")
        else:
            print(f"\n⚠️ GATE 3 TEST INCOMPLETE: {trades_executed}/{min_for_success} trades (minimum not met)")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    if test_config_path.exists():
        test_config_path.unlink()