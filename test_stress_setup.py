#!/usr/bin/env python3
"""
Quick test to verify stress test setup.
"""

import requests
import time
import json
import subprocess
import sys

def check_broker():
    """Check if broker is running."""
    try:
        response = requests.get("http://127.0.0.1:5555/health", timeout=5.0)
        if response.status_code == 200:
            print("✅ Broker is running")
            return True
        else:
            print(f"❌ Broker returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to broker: {e}")
        return False

def check_agents():
    """Check registered agents."""
    try:
        response = requests.get("http://127.0.0.1:5555/agents", timeout=5.0)
        agents = response.json()
        print(f"📊 Total agents: {agents.get('count', 0)}")
        
        for agent_id, agent_info in agents.get("agents", {}).items():
            status = "✅" if not agent_info.get("stale", True) else "⚠️ "
            print(f"  {status} {agent_id}: {agent_info.get('agent_type', 'unknown')}")
        
        return "test_agent_1" in agents.get("agents", {})
    except Exception as e:
        print(f"❌ Error checking agents: {e}")
        return False

def start_test_agent():
    """Start test_agent_1."""
    print("🚀 Starting test_agent_1...")
    
    try:
        # Start test agent
        process = subprocess.Popen([
            sys.executable, "test_agent_1.py",
            "--agent-id", "test_agent_1",
            "--port", "8889",
            "--verbose"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print("⏳ Waiting for agent to start...")
        time.sleep(3)
        
        # Check if process is running
        if process.poll() is None:
            print("✅ test_agent_1 started successfully")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ test_agent_1 failed to start")
            print(f"STDOUT: {stdout.decode()[:200]}")
            print(f"STDERR: {stderr.decode()[:200]}")
            return None
    except Exception as e:
        print(f"❌ Error starting test_agent_1: {e}")
        return None

def test_single_intent():
    """Test sending a single intent."""
    print("\n🧪 Testing single intent...")
    
    intent_data = {
        "intent_type": "ping",
        "source_agent": "test_script",
        "target_agent": "test_agent_1",
        "params": {"message": "test"},
        "intent_id": f"test_{int(time.time())}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    try:
        response = requests.post(
            "http://127.0.0.1:5555/intents/route",
            headers={"Content-Type": "application/json"},
            json=intent_data,
            timeout=10.0
        )
        
        print(f"📤 Sent intent, status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"📥 Response: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Error response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error sending intent: {e}")
        return False

def main():
    """Main test function."""
    print("="*60)
    print("SIMP Stress Test Setup Verification")
    print("="*60)
    
    # Check broker
    if not check_broker():
        print("\n❌ Broker check failed. Please start the broker first.")
        print("   Command: python3 -m simp.server.http_server")
        return
    
    # Check agents
    print("\n📋 Checking registered agents...")
    test_agent_registered = check_agents()
    
    # Start test agent if not registered
    agent_process = None
    if not test_agent_registered:
        print("\n🔧 test_agent_1 not found, starting it...")
        agent_process = start_test_agent()
        
        if agent_process:
            # Wait a bit more for registration
            time.sleep(2)
            test_agent_registered = check_agents()
    
    # Test single intent
    if test_agent_registered:
        print("\n✅ test_agent_1 is ready for testing")
        success = test_single_intent()
        
        if success:
            print("\n🎉 Setup verification complete!")
            print("You can now run the stress test:")
            print("  python3 simp_stress_test.py")
        else:
            print("\n❌ Single intent test failed")
    else:
        print("\n❌ test_agent_1 setup failed")
    
    # Cleanup
    if agent_process:
        print("\n🧹 Cleaning up test_agent_1...")
        agent_process.terminate()
        agent_process.wait(timeout=2)
        print("✅ Cleanup complete")

if __name__ == "__main__":
    main()