#!/usr/bin/env python3
"""
Simple test for mesh integration
"""

import time
import requests
import json
import subprocess
import sys
from pathlib import Path

def test_mesh_endpoints():
    """Test mesh HTTP endpoints"""
    base_url = "http://127.0.0.1:5555"
    
    print("Testing mesh endpoints...")
    
    # Test mesh stats
    try:
        response = requests.get(f"{base_url}/mesh/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Mesh stats: {json.dumps(stats, indent=2)}")
            return True
        else:
            print(f"❌ Mesh stats failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error testing mesh stats: {e}")
    
    return False

def test_mesh_send_receive():
    """Test sending and receiving mesh messages"""
    base_url = "http://127.0.0.1:5555"
    
    print("\nTesting mesh send/receive...")
    
    # First, register a test agent
    register_data = {
        "agent_id": "test_mesh_agent",
        "endpoint": "http://127.0.0.1:9999/test",
        "agent_type": "test",
        "capabilities": ["test"]
    }
    
    try:
        response = requests.post(f"{base_url}/agents/register", json=register_data)
        if response.status_code != 200:
            print(f"❌ Failed to register test agent: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error registering agent: {e}")
        return False
    
    # Subscribe to a channel
    subscribe_data = {
        "agent_id": "test_mesh_agent",
        "channel": "test_channel"
    }
    
    try:
        response = requests.post(f"{base_url}/mesh/subscribe", json=subscribe_data)
        if response.status_code == 200:
            print("✅ Subscribed to test_channel")
        else:
            print(f"❌ Failed to subscribe: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error subscribing: {e}")
        return False
    
    # Send a message
    send_data = {
        "sender_id": "test_sender",
        "recipient_id": "test_mesh_agent",
        "channel": "test_channel",
        "msg_type": "event",
        "payload": {"test": "message", "value": 42},
        "priority": "normal",
        "ttl_hops": 10,
        "ttl_seconds": 60
    }
    
    try:
        response = requests.post(f"{base_url}/mesh/send", json=send_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Message sent successfully")
            else:
                print(f"❌ Send failed: {result.get('error')}")
                return False
        else:
            print(f"❌ Send request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False
    
    # Poll for messages
    try:
        response = requests.get(f"{base_url}/mesh/poll?agent_id=test_mesh_agent&max_messages=10")
        if response.status_code == 200:
            messages = response.json()
            if messages:
                print(f"✅ Received {len(messages)} message(s)")
                for msg in messages:
                    print(f"   Message: {json.dumps(msg, indent=2)}")
                return True
            else:
                print("❌ No messages received")
                return False
        else:
            print(f"❌ Poll failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error polling messages: {e}")
        return False

def test_projectx_mesh_client():
    """Test ProjectX mesh client integration"""
    print("\nTesting ProjectX mesh client...")
    
    try:
        # Import the mesh client
        sys.path.insert(0, str(Path(__file__).parent))
        from simp.mesh.client import MeshClient
        
        # Create client
        client = MeshClient(agent_id="projectx_test", broker_url="http://127.0.0.1:5555")
        
        # Subscribe to safety_alerts
        success = client.subscribe("safety_alerts")
        if success:
            print("✅ Subscribed to safety_alerts")
        else:
            print("❌ Failed to subscribe to safety_alerts")
            return False
        
        # Send a test alert
        success = client.send_to_channel(
            channel="safety_alerts",
            payload={
                "alert_type": "test",
                "severity": "INFO",
                "message": "Test safety alert",
                "source": "test_script"
            },
            msg_type="event"
        )
        
        if success:
            print("✅ Test safety alert sent")
        else:
            print("❌ Failed to send test alert")
            return False
        
        # Poll for messages
        messages = client.poll(max_messages=5)
        print(f"✅ Polled {len(messages)} message(s)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing ProjectX mesh client: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("SIMP Mesh Integration Test")
    print("=" * 60)
    
    # Check if broker is running
    try:
        response = requests.get("http://127.0.0.1:5555/health", timeout=2)
        if response.status_code == 200:
            print("✅ Broker is running")
        else:
            print("❌ Broker is not responding properly")
            return False
    except:
        print("❌ Broker is not running. Please start it first.")
        print("Run: python3.10 bin/start_server.py")
        return False
    
    # Run tests
    all_passed = True
    
    if test_mesh_endpoints():
        print("\n✅ Mesh endpoints test PASSED")
    else:
        print("\n❌ Mesh endpoints test FAILED")
        all_passed = False
    
    if test_mesh_send_receive():
        print("\n✅ Mesh send/receive test PASSED")
    else:
        print("\n❌ Mesh send/receive test FAILED")
        all_passed = False
    
    if test_projectx_mesh_client():
        print("\n✅ ProjectX mesh client test PASSED")
    else:
        print("\n❌ ProjectX mesh client test FAILED")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)