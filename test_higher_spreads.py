#!/usr/bin/env python3.10
"""
Test with higher spreads to understand risk scoring.
"""

import json
import time
import random
from datetime import datetime
from pathlib import Path

def test_spread_impact():
    """Test how different spreads affect risk scores."""
    simp_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
    inbox_dir = simp_root / "data/quantumarb_minimal/inbox"
    
    # Test spreads from 0.1% to 1.0%
    test_spreads = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    print("Testing spread impact on risk scores:")
    print("="*60)
    
    for i, spread in enumerate(test_spreads, 1):
        # Create test signal with high spread
        signal = {
            "intent_type": "arbitrage_signal",
            "source_agent": "spread_test",
            "target_agent": "quantumarb_minimal",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "signal_id": f"spread_test_{i}_{int(time.time())}",
                "arb_type": "cross_venue",
                "symbol_a": "BTC-USD",
                "symbol_b": "BTC-USD",
                "venue_a": "coinbase_sandbox",
                "venue_b": "coinbase_sandbox",
                "spread_pct": spread,
                "expected_return_pct": spread - 0.02,  # Assume 0.02% slippage
                "confidence": 0.85,  # High confidence
                "metadata": {
                    "test": True,
                    "spread_test": True,
                    "spread_value": spread
                }
            }
        }
        
        # Send signal
        signal_file = inbox_dir / f"{signal['payload']['signal_id']}.json"
        with open(signal_file, 'w') as f:
            json.dump(signal, f, indent=2)
        
        print(f"\nTest {i}: {spread:.1f}% spread")
        print(f"  Sent signal: {signal_file.name}")
        
        # Wait for processing
        time.sleep(5)
        
        # Check result
        outbox_dir = simp_root / "data/quantumarb_minimal/outbox"
        result_files = list(outbox_dir.glob(f"result_{signal['payload']['signal_id']}.json"))
        
        if result_files:
            with open(result_files[0], 'r') as f:
                result = json.load(f)
            
            decision = result["opportunity"]["decision"]
            reason = result["opportunity"]["decision_reason"]
            risk_score = result["opportunity"]["risk_score"]
            
            print(f"  Result: {decision}")
            print(f"  Risk score: {risk_score:.3f}")
            print(f"  Reason: {reason}")
            
            if decision == "execute":
                print(f"  ✅ APPROVED at {spread:.1f}% spread!")
                return spread, risk_score
        else:
            print(f"  ⚠ No result yet")
    
    print("\n" + "="*60)
    print("No approvals even at 1.0% spread.")
    print("Risk scoring needs adjustment for microscopic trading.")
    return None, None

def calculate_expected_risk_score(spread, confidence=0.85, slippage=0.03):
    """Calculate expected risk score based on current formula."""
    spread_score = min(spread / 1.0, 1.0)
    confidence_score = confidence
    slippage_penalty = max(0, 1.0 - (slippage / 0.1))
    
    risk_score = (
        spread_score * 0.5 +
        confidence_score * 0.3 +
        slippage_penalty * 0.2
    )
    
    return risk_score

def analyze_risk_scoring():
    """Analyze risk scoring formula."""
    print("\n" + "="*60)
    print("RISK SCORING ANALYSIS")
    print("="*60)
    
    print("\nCurrent formula:")
    print("  risk_score = (spread_score * 0.5) + (confidence * 0.3) + (slippage_penalty * 0.2)")
    print("  where spread_score = min(spread_pct / 1.0, 1.0)")
    print("  and slippage_penalty = max(0, 1.0 - (slippage / 0.1))")
    
    print("\nTo reach 0.70 threshold:")
    
    # Solve for required spread
    confidence = 0.85
    slippage = 0.03
    slippage_penalty = max(0, 1.0 - (slippage / 0.1))  # 0.7
    
    # We need: (spread_score * 0.5) + (0.85 * 0.3) + (0.7 * 0.2) >= 0.70
    # => (spread_score * 0.5) + 0.255 + 0.14 >= 0.70
    # => (spread_score * 0.5) >= 0.70 - 0.395
    # => (spread_score * 0.5) >= 0.305
    # => spread_score >= 0.61
    # => spread >= 0.61% (since spread_score = spread/1.0)
    
    required_spread = 0.61
    print(f"  With {confidence:.2f} confidence and {slippage:.2f}% slippage:")
    print(f"  Required spread: {required_spread:.2f}%")
    print(f"  Spread score needed: {required_spread:.2f}")
    
    print("\nAlternative: Adjust weights for microscopic trading:")
    print("  Option 1: Increase spread weight (e.g., 0.7 instead of 0.5)")
    print("  Option 2: Normalize spread differently (e.g., divide by 0.5 instead of 1.0)")
    print("  Option 3: Lower threshold for microscopic trading (e.g., 0.50 instead of 0.70)")
    
    return required_spread

def test_adjusted_signals():
    """Test with signals that should pass adjusted criteria."""
    simp_root = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
    inbox_dir = simp_root / "data/quantumarb_minimal/inbox"
    
    # Test signals with higher spreads
    test_cases = [
        {"spread": 0.65, "confidence": 0.90, "description": "High spread, high confidence"},
        {"spread": 0.80, "confidence": 0.80, "description": "Very high spread, good confidence"},
        {"spread": 0.50, "confidence": 0.95, "description": "Medium spread, very high confidence"},
    ]
    
    print("\n" + "="*60)
    print("TESTING ADJUSTED SIGNALS")
    print("="*60)
    
    for i, test_case in enumerate(test_cases, 1):
        spread = test_case["spread"]
        confidence = test_case["confidence"]
        
        # Calculate expected risk score
        expected_score = calculate_expected_risk_score(spread, confidence)
        
        print(f"\nTest case {i}: {test_case['description']}")
        print(f"  Spread: {spread:.2f}%, Confidence: {confidence:.2f}")
        print(f"  Expected risk score: {expected_score:.3f}")
        print(f"  Pass threshold: {'✅' if expected_score >= 0.70 else '❌'}")
        
        # Create and send signal
        signal = {
            "intent_type": "arbitrage_signal",
            "source_agent": "adjusted_test",
            "target_agent": "quantumarb_minimal",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "signal_id": f"adj_test_{i}_{int(time.time())}",
                "arb_type": "cross_venue",
                "symbol_a": "BTC-USD",
                "symbol_b": "BTC-USD",
                "venue_a": "coinbase_sandbox",
                "venue_b": "coinbase_sandbox",
                "spread_pct": spread,
                "expected_return_pct": spread - 0.02,
                "confidence": confidence,
                "metadata": {
                    "test": True,
                    "adjusted_test": True,
                    "expected_score": expected_score
                }
            }
        }
        
        signal_file = inbox_dir / f"{signal['payload']['signal_id']}.json"
        with open(signal_file, 'w') as f:
            json.dump(signal, f, indent=2)
        
        print(f"  Sent signal: {signal_file.name}")
        
        # Wait and check result
        time.sleep(5)
        
        outbox_dir = simp_root / "data/quantumarb_minimal/outbox"
        result_files = list(outbox_dir.glob(f"result_{signal['payload']['signal_id']}.json"))
        
        if result_files:
            with open(result_files[0], 'r') as f:
                result = json.load(f)
            
            actual_score = result["opportunity"]["risk_score"]
            decision = result["opportunity"]["decision"]
            
            print(f"  Actual risk score: {actual_score:.3f}")
            print(f"  Decision: {decision}")
            print(f"  Score match: {'✅' if abs(actual_score - expected_score) < 0.01 else '❌'}")
            
            if decision == "execute":
                print(f"  🎉 APPROVED! First successful trade!")
                return True
    
    return False

def main():
    """Main function."""
    print("GATE 1 RISK SCORING ANALYSIS")
    print("="*60)
    
    # Test current spreads
    approved_spread, approved_score = test_spread_impact()
    
    if approved_spread:
        print(f"\n✅ Found approval at {approved_spread:.2f}% spread")
        print(f"   Risk score: {approved_score:.3f}")
    else:
        print("\n❌ No approvals with current spreads")
    
    # Analyze risk scoring
    required_spread = analyze_risk_scoring()
    
    # Test adjusted signals
    approved = test_adjusted_signals()
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    if approved:
        print("\n✅ System is working! Found approved trade.")
        print("   Continue with current risk scoring.")
    else:
        print("\n⚠ Risk scoring may be too strict for microscopic trading.")
        print("   Consider adjusting:")
        print("   1. Risk threshold: Lower from 0.70 to 0.50 for Gate 1")
        print("   2. Spread normalization: Divide by 0.5 instead of 1.0")
        print("   3. Weight adjustment: Increase spread weight to 0.7")
    
    print("\n📊 Next steps:")
    print("   1. Review risk scoring formula")
    print("   2. Adjust parameters if needed")
    print("   3. Continue Gate 1 testing")
    print("   4. Monitor approval rate")

if __name__ == "__main__":
    main()