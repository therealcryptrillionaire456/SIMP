#!/usr/bin/env python3.10
"""
Test SIMP system components before full go-live.
"""

import os
import sys
import time
import json
import requests
from pathlib import Path

BROKER_URL = "http://127.0.0.1:5555"
API_KEY = "test-key-123"

def test_broker():
    """Test broker connectivity."""
    print("Testing broker connectivity...")
    try:
        response = requests.get(f"{BROKER_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Broker is running: {data}")
            return True
        else:
            print(f"✗ Broker returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Broker connection failed: {e}")
        return False

def test_agents():
    """Test agent registration."""
    print("\nTesting agent registration...")
    try:
        response = requests.get(f"{BROKER_URL}/agents", timeout=5)
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", {})
            print(f"✓ Found {len(agents)} registered agents")
            for agent_id, agent_info in agents.items():
                print(f"  - {agent_id}: {agent_info.get('status', 'unknown')}")
            return True
        else:
            print(f"✗ Failed to get agents: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Agent test failed: {e}")
        return False

def test_financial_ops():
    """Test FinancialOps compatibility layer."""
    print("\nTesting FinancialOps...")
    try:
        response = requests.get(
            f"{BROKER_URL}/a2a/agents/financial_ops/agent.json",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ FinancialOps agent card: {data.get('name', 'unknown')}")
            return True
        else:
            print(f"✗ FinancialOps returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ FinancialOps test failed: {e}")
        return False

def test_intent_routing():
    """Test intent routing."""
    print("\nTesting intent routing...")
    
    test_intent = {
        "intent_type": "ping",
        "source_agent": "tester",
        "target_agent": "auto",
        "payload": {"message": "test"},
        "metadata": {"test": True}
    }
    
    try:
        response = requests.post(
            f"{BROKER_URL}/intents/route",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": API_KEY
            },
            json=test_intent,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Intent routed successfully: {data.get('status')}")
            print(f"  Target agent: {data.get('target_agent', 'unknown')}")
            return True
        else:
            print(f"✗ Intent routing failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Intent routing test failed: {e}")
        return False

def test_quantumarb_components():
    """Test QuantumArb components."""
    print("\nTesting QuantumArb components...")
    
    # Check if QuantumArb agent file exists
    agent_path = Path("simp/agents/quantumarb_agent.py")
    if not agent_path.exists():
        print(f"✗ QuantumArb agent not found: {agent_path}")
        return False
    
    print(f"✓ QuantumArb agent file exists: {agent_path}")
    
    # Check if QuantumArb organ exists
    organ_dir = Path("simp/organs/quantumarb")
    if not organ_dir.exists():
        print(f"✗ QuantumArb organ directory not found: {organ_dir}")
        return False
    
    print(f"✓ QuantumArb organ directory exists")
    
    # List organ files
    organ_files = list(organ_dir.glob("*.py"))
    print(f"  Found {len(organ_files)} organ files:")
    for file in organ_files:
        print(f"    - {file.name}")
    
    return True

def test_ledgers():
    """Test ledger files."""
    print("\nTesting ledger files...")
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"✗ Data directory not found: {data_dir}")
        return False
    
    print(f"✓ Data directory exists: {data_dir}")
    
    # Check required ledger files
    required_files = [
        "task_ledger.jsonl",
        "financial_ops_proposals.jsonl",
        "live_spend_ledger.jsonl"
    ]
    
    all_exist = True
    for file_name in required_files:
        file_path = data_dir / file_name
        if file_path.exists():
            print(f"✓ Ledger exists: {file_name}")
        else:
            print(f"✗ Ledger missing: {file_name}")
            all_exist = False
    
    return all_exist

def test_dashboard():
    """Test dashboard."""
    print("\nTesting dashboard...")
    
    dashboard_url = "http://127.0.0.1:8050"
    
    try:
        response = requests.get(f"{dashboard_url}/", timeout=5)
        if response.status_code == 200:
            print("✓ Dashboard is running")
            return True
        else:
            print(f"✗ Dashboard returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Dashboard connection failed: {e}")
        return False

def main():
    """Run all tests."""
    print("="*80)
    print("SIMP SYSTEM COMPONENT TESTS")
    print("="*80)
    
    tests = [
        ("Broker", test_broker),
        ("Agents", test_agents),
        ("FinancialOps", test_financial_ops),
        ("Intent Routing", test_intent_routing),
        ("QuantumArb Components", test_quantumarb_components),
        ("Ledgers", test_ledgers),
        ("Dashboard", test_dashboard)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - System is ready for go-live!")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed - Review issues before go-live")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)