#!/usr/bin/env python3.10
"""Test Gate 2 simple agent with limited run."""

import sys
sys.path.insert(0, '.')

from simp.agents.quantumarb_gate2_simple import QuantumArbGate2Simple
import json
from pathlib import Path

# Create a test config
test_config = {
    "mode": "live_phase_2_microscopic_sol",
    "exchange": "coinbase",
    "symbols": ["SOL-USD"],
    "position_sizing": {
        "position_type": "fixed_dollar",
        "min_notional": 0.01,
        "max_notional": 0.10,
        "default_notional": 0.05
    },
    "risk_limits": {
        "max_risk_per_trade_dollar": 0.10,
        "max_session_loss_dollar": 1.00,
        "max_open_positions": 1,
        "max_concurrent_orders": 2
    },
    "risk": {
        "risk_score_threshold": 0.5,
        "min_spread_pct": 0.01,
        "max_slippage_pct": 0.10
    },
    "microscopic_trading": {
        "enabled": True,
        "gate": 2,
        "primary_market": "SOL-USD",
        "target_trades": 10,  # Small target for testing
        "min_trades_for_success": 8
    }
}

# Save test config
test_config_path = Path("config/test_gate2_simple.json")
test_config_path.parent.mkdir(parents=True, exist_ok=True)
with open(test_config_path, 'w') as f:
    json.dump(test_config, f, indent=2)

print("Testing Gate 2 Simple Agent...")
print("=" * 60)

try:
    # Create agent
    agent = QuantumArbGate2Simple(str(test_config_path))
    
    # Run a short session
    print("\nRunning test session (will stop after ~10 trades)...")
    print("Press Ctrl+C to stop early")
    print("-" * 60)
    
    agent.run_session()
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    
    # Check results
    results_file = list(Path("data/quantumarb_gate2_simple").glob("session_*.json"))
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
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    if test_config_path.exists():
        test_config_path.unlink()