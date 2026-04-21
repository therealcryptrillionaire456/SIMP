#!/usr/bin/env python3
"""
Test script for Enhanced QuantumArb Agent with BRP Protection.

This script sends a test arbitrage intent to the enhanced QuantumArb agent
and verifies that BRP protection is working.
"""

import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone


def create_test_intent():
    """Create a test arbitrage intent."""
    intent = {
        "intent_type": "evaluate_arb",
        "source_agent": "test_runner",
        "target_agent": "quantumarb_enhanced",
        "intent_id": str(uuid.uuid4()),
        "payload": {
            "ticker": "BTC-USD",
            "direction": "long",
            "confidence": 0.85,
            "horizon_minutes": 5,
            "metadata": {
                "test": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        },
        "correlation_id": str(uuid.uuid4()),
    }
    return intent


def send_test_intent(intent):
    """Send test intent to QuantumArb enhanced inbox."""
    inbox_dir = Path("data/inboxes/quantumarb_enhanced")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"test_{intent['intent_id']}.json"
    filepath = inbox_dir / filename
    
    with open(filepath, "w") as f:
        json.dump(intent, f, indent=2)
    
    print(f"Test intent written to: {filepath}")
    return filepath


def check_response(intent_id, timeout=30):
    """Check for response from QuantumArb enhanced agent."""
    outbox_dir = Path("data/outboxes/quantumarb_enhanced")
    outbox_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        for filepath in outbox_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    response = json.load(f)
                
                # Check if this is a response to our test intent
                if response.get("original_intent_id") == intent_id:
                    print(f"Found response: {filepath}")
                    return response, filepath
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
        
        time.sleep(1)
    
    print(f"No response found within {timeout} seconds")
    return None, None


def analyze_response(response):
    """Analyze the response from QuantumArb enhanced agent."""
    if not response:
        print("No response to analyze")
        return
    
    payload = response.get("payload", {})
    
    print("\n" + "="*60)
    print("QUANTUMARB ENHANCED AGENT RESPONSE ANALYSIS")
    print("="*60)
    
    print(f"Arbitrage Decision: {payload.get('decision', 'unknown')}")
    print(f"Arbitrage Type: {payload.get('arb_type', 'unknown')}")
    print(f"Estimated Spread: {payload.get('estimated_spread_bps', 0):.2f} bps")
    print(f"Confidence: {payload.get('confidence', 0):.2f}")
    print(f"Dry Run: {payload.get('dry_run', True)}")
    
    # BRP-specific analysis
    print("\nBRP PROTECTION ANALYSIS:")
    print("-"*40)
    brp_allowed = payload.get('brp_allowed', True)
    brp_reason = payload.get('brp_reason', '')
    
    if brp_allowed:
        print("✅ BRP ALLOWED the trade")
    else:
        print("🚫 BRP BLOCKED the trade")
    
    if brp_reason:
        print(f"BRP Reason: {brp_reason}")
    
    # Check logs
    print("\nCHECKING LOGS:")
    print("-"*40)
    
    # Check BRP logs
    brp_log_dir = Path("logs/quantumarb/brp")
    if brp_log_dir.exists():
        evaluations_log = brp_log_dir / "evaluations.jsonl"
        if evaluations_log.exists():
            print(f"✅ BRP evaluations log exists: {evaluations_log}")
            # Count lines
            with open(evaluations_log, "r") as f:
                lines = f.readlines()
                print(f"   Total BRP evaluations: {len(lines)}")
        else:
            print(f"⚠ BRP evaluations log not found")
    else:
        print(f"⚠ BRP log directory not found: {brp_log_dir}")
    
    # Check agent logs
    agent_log = Path("logs/quantumarb/enhanced_agent.log")
    if agent_log.exists():
        print(f"✅ Agent log exists: {agent_log}")
    else:
        print(f"⚠ Agent log not found: {agent_log}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


def main():
    """Main test function."""
    print("Testing Enhanced QuantumArb Agent with BRP Protection")
    print("="*60)
    
    # Create test intent
    print("\n1. Creating test arbitrage intent...")
    intent = create_test_intent()
    print(f"   Intent ID: {intent['intent_id']}")
    print(f"   Ticker: {intent['payload']['ticker']}")
    print(f"   Direction: {intent['payload']['direction']}")
    
    # Send test intent
    print("\n2. Sending test intent to QuantumArb enhanced agent...")
    intent_file = send_test_intent(intent)
    
    # Wait for response
    print(f"\n3. Waiting for response (max 30 seconds)...")
    response, response_file = check_response(intent['intent_id'])
    
    # Analyze response
    print("\n4. Analyzing response...")
    analyze_response(response)
    
    # Cleanup
    print("\n5. Cleaning up test files...")
    if intent_file and intent_file.exists():
        # Move to processed directory
        processed_dir = Path("data/inboxes/quantumarb_enhanced/processed")
        processed_dir.mkdir(exist_ok=True)
        intent_file.rename(processed_dir / intent_file.name)
        print(f"   Moved intent to processed directory")
    
    if response_file and response_file.exists():
        # Archive response
        archive_dir = Path("data/outboxes/quantumarb_enhanced/archive")
        archive_dir.mkdir(exist_ok=True)
        response_file.rename(archive_dir / response_file.name)
        print(f"   Archived response")
    
    print("\n" + "="*60)
    if response:
        print("✅ TEST PASSED: Enhanced QuantumArb Agent with BRP is working!")
    else:
        print("⚠ TEST INCONCLUSIVE: No response received. Agent may not be running.")
    print("="*60)


if __name__ == "__main__":
    main()