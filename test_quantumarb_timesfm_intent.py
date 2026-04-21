#!/usr/bin/env python3
"""Test QuantumArb intent with TimesFM integration."""

import os
import json
import requests
import uuid
from datetime import datetime

# Set environment variables for TimesFM
os.environ['SIMP_TIMESFM_ENABLED'] = 'true'
os.environ['SIMP_TIMESFM_SHADOW_MODE'] = 'true'

# Broker URL
BROKER_URL = "http://127.0.0.1:5555"
API_KEY = os.environ.get("SIMP_API_KEY", "test-key")

def test_quantumarb_timesfm_intent():
    """Send a QuantumArb intent with TimesFM usage."""
    
    # Create a QuantumArb intent with TimesFM
    intent_id = str(uuid.uuid4())
    
    intent = {
        "intent_id": intent_id,
        "intent_type": "arbitrage_opportunity",
        "source_agent": "goose",
        "target_agent": "auto",  # Let broker route to quantumarb
        "payload": {
            "asset_pair": "BTC-USD",
            "analysis_type": "cross_exchange",
            "exchanges": ["coinbase", "kraken"],
            "timesfm_requested": True,
            "dry_run": True,
            "confidence_threshold": 0.7
        },
        "metadata": {
            "priority": "high",
            "requires_timesfm": True,
            "test_timesfm_integration": True
        }
    }
    
    print("Sending QuantumArb intent with TimesFM...")
    print(f"Intent ID: {intent_id}")
    
    # Send intent to broker
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    try:
        response = requests.post(
            f"{BROKER_URL}/intents/route",
            json=intent,
            headers=headers,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Intent routed successfully")
            print(f"Target agent: {result.get('target_agent')}")
            print(f"Delivery status: {result.get('delivery_status')}")
            
            # Check if TimesFM was mentioned in the response
            if 'timesfm' in json.dumps(result).lower():
                print("✓ TimesFM referenced in response")
            else:
                print("⚠ TimesFM not referenced in response")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error sending intent: {e}")
    
    # Check broker stats for TimesFM activity
    print("\nChecking TimesFM stats...")
    try:
        stats_response = requests.get(f"{BROKER_URL}/stats", timeout=5)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            timesfm_stats = stats.get('timesfm', {})
            
            if timesfm_stats:
                print("TimesFM Stats:")
                print(f"  Enabled: {timesfm_stats.get('enabled', False)}")
                print(f"  Shadow Mode: {timesfm_stats.get('shadow_mode', False)}")
                print(f"  Model Loaded: {timesfm_stats.get('model_loaded', False)}")
                print(f"  Total Requests: {timesfm_stats.get('total_requests', 0)}")
                print(f"  Cache Hits: {timesfm_stats.get('cache_hits', 0)}")
                
                if timesfm_stats.get('total_requests', 0) > 0:
                    print("✓ TimesFM is processing requests!")
                else:
                    print("⚠ TimesFM not yet processing requests (may need agent trigger)")
            else:
                print("TimesFM stats not available yet")
    except Exception as e:
        print(f"Error checking stats: {e}")
    
    # Check task ledger for the intent
    print("\nChecking task ledger...")
    try:
        # Get recent tasks
        tasks_response = requests.get(
            f"{BROKER_URL}/tasks?limit=5",
            headers=headers,
            timeout=5
        )
        if tasks_response.status_code == 200:
            tasks = tasks_response.json()
            print(f"Recent tasks: {len(tasks.get('tasks', []))}")
            
            # Look for our intent
            for task in tasks.get('tasks', []):
                if task.get('intent_id') == intent_id:
                    print(f"Found our intent in task ledger:")
                    print(f"  Status: {task.get('status')}")
                    print(f"  Created: {task.get('created_at')}")
                    if task.get('payload'):
                        payload_str = json.dumps(task.get('payload'))
                        if 'timesfm' in payload_str.lower():
                            print("✓ TimesFM referenced in task payload")
                    break
    except Exception as e:
        print(f"Error checking task ledger: {e}")

if __name__ == "__main__":
    test_quantumarb_timesfm_intent()