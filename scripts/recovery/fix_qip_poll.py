#!/usr/bin/env python3.10
"""
Fix QIP polling issue by switching from mesh bus to HTTP transport.
This script will:
1. Modify quantum_mesh_consumer.py to use HTTP only (no mesh bus)
2. Restart QIP
3. Send a test intent
4. Wait and check if intents_completed increases
"""

import os
import sys
import time
import requests
import subprocess
import json

BROKER = "http://127.0.0.1:5555"
QIP_FILE = "quantum_mesh_consumer.py"
BACKUP_FILE = "quantum_mesh_consumer.py.backup_fix"

def backup_file():
    """Create backup of original file"""
    if os.path.exists(QIP_FILE):
        with open(QIP_FILE, 'r') as f:
            original = f.read()
        with open(BACKUP_FILE, 'w') as f:
            f.write(original)
        print(f"✅ Created backup: {BACKUP_FILE}")
        return original
    else:
        print(f"❌ File not found: {QIP_FILE}")
        return None

def fix_qip_file():
    """Modify QIP file to use HTTP transport only"""
    with open(QIP_FILE, 'r') as f:
        content = f.read()
    
    # Remove mesh bus imports and usage
    fixes = [
        # Remove mesh bus import
        ("from simp.mesh.bus import get_mesh_bus\n", ""),
        
        # Replace mesh bus registration with HTTP registration
        ("""    # Try mesh bus first
    mesh_bus = get_mesh_bus()
    if agent_id not in mesh_bus._registered_agents:
        try:
            mesh_bus.register_agent(agent_id)
            logger.info(f"Registered {agent_id} with MeshBus")
        except Exception as e:
            logger.error(f"MeshBus registration failed: {e}")
            return False""",
         """    # Use HTTP registration only
    try:
        result = _post(f"{broker}/agents/register", {
            "agent_id": agent_id,
            "agent_type": "quantum",
            "endpoint": "",
            "simp_versions": ["1.0"],
            "metadata": {
                "capabilities": [
                    "health_check",
                    "get_deployment_status",
                    "solve_quantum_problem",
                    "optimize_portfolio",
                    "evolve_quantum_skills"
                ],
                "transport": "http",
                "mesh_native": false,
                "version": "1.0.0"
            }
        })
        if result and result.get("status") == "success":
            logger.info(f"Registered {agent_id} via HTTP")
            return True
        else:
            logger.error(f"HTTP registration failed: {result}")
            return False
    except Exception as e:
        logger.error(f"HTTP registration exception: {e}")
        return False"""),
        
        # Replace mesh bus subscription with HTTP subscription
        ("""    # Subscribe via mesh bus
    try:
        success = mesh_bus.subscribe(agent_id, channel)
        if success:
            logger.info(f"Directly subscribed to channel '{channel}' ✅")
            return True
        else:
            logger.warning(f"MeshBus subscription failed for {channel}")
    except Exception as e:
        logger.error(f"MeshBus subscription error: {e}")""",
         """    # Subscribe via HTTP
    try:
        result = _post(f"{broker}/mesh/subscribe", {
            "agent_id": agent_id,
            "channel": channel,
            "simp_versions": ["1.0"]
        })
        if result and result.get("status") == "success":
            logger.info(f"Subscribed to channel '{channel}' via HTTP ✅")
            return True
        else:
            logger.warning(f"HTTP subscription failed for {channel}: {result}")
            return False
    except Exception as e:
        logger.error(f"HTTP subscription error: {e}")
        return False"""),
        
        # Remove mesh bus from main registration function
        ("""    # Register with mesh bus
    mesh_bus = get_mesh_bus()
    if AGENT_ID not in mesh_bus._registered_agents:
        try:
            mesh_bus.register_agent(AGENT_ID)
            logger.info(f"Pre-registered {AGENT_ID} with mesh bus ✅")
        except Exception as e:
            logger.error(f"MeshBus pre-registration failed: {e}")
    
    # Pre-subscribe to channels
    for channel in ["quantum", "intent_requests"]:
        try:
            mesh_bus.subscribe(AGENT_ID, channel)
            logger.info(f"Pre-subscribed to {channel} ✅")
        except Exception as e:
            logger.error(f"MeshBus pre-subscription to {channel} failed: {e}")""",
         """    # Register via HTTP
    try:
        result = _post(f"{BROKER}/agents/register", {
            "agent_id": AGENT_ID,
            "agent_type": "quantum",
            "endpoint": "",
            "simp_versions": ["1.0"],
            "metadata": {
                "capabilities": [
                    "health_check",
                    "get_deployment_status",
                    "solve_quantum_problem",
                    "optimize_portfolio",
                    "evolve_quantum_skills"
                ],
                "transport": "http",
                "mesh_native": False,
                "version": "1.0.0"
            }
        })
        if result and result.get("status") == "success":
            logger.info(f"Registered {AGENT_ID} via HTTP ✅")
        else:
            logger.error(f"HTTP registration failed: {result}")
    except Exception as e:
        logger.error(f"HTTP registration exception: {e}")
    
    # Subscribe to channels via HTTP
    for channel in ["quantum", "intent_requests"]:
        try:
            result = _post(f"{BROKER}/mesh/subscribe", {
                "agent_id": AGENT_ID,
                "channel": channel,
                "simp_versions": ["1.0"]
            })
            if result and result.get("status") == "success":
                logger.info(f"Subscribed to {channel} via HTTP ✅")
            else:
                logger.error(f"HTTP subscription to {channel} failed: {result}")
        except Exception as e:
            logger.error(f"HTTP subscription exception for {channel}: {e}")""")
    ]
    
    original_content = content
    for old, new in fixes:
        content = content.replace(old, new)
    
    if content != original_content:
        with open(QIP_FILE, 'w') as f:
            f.write(content)
        print("✅ Modified QIP file to use HTTP transport only")
        return True
    else:
        print("⚠️ No changes made (fixes might already be applied)")
        return False

def restart_qip():
    """Restart QIP process"""
    print("\n🔄 Restarting QIP...")
    
    # Kill existing QIP processes
    subprocess.run(["pkill", "-f", "quantum_mesh_consumer.py"], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    # Start QIP
    cmd = ["python3.10", "quantum_mesh_consumer.py"]
    process = subprocess.Popen(cmd, 
                               stdout=open("data/logs/goose/qip_fixed.log", "w"),
                               stderr=subprocess.STDOUT)
    time.sleep(3)
    
    # Check if process is running
    result = subprocess.run(["pgrep", "-f", "quantum_mesh_consumer.py"], 
                           capture_output=True, text=True)
    if result.stdout.strip():
        print("✅ QIP restarted successfully")
        return True
    else:
        print("❌ Failed to restart QIP")
        return False

def get_qip_status():
    """Get current QIP status"""
    try:
        resp = requests.get(f"{BROKER}/agents/quantum_intelligence_prime", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            agent = data.get("agent", {})
            return {
                "heartbeats": agent.get("heartbeat_count", 0),
                "received": agent.get("intents_received", 0),
                "completed": agent.get("intents_completed", 0),
                "transport": agent.get("metadata", {}).get("transport", "unknown"),
                "mesh_native": agent.get("metadata", {}).get("mesh_native", False)
            }
    except Exception as e:
        print(f"❌ Error getting QIP status: {e}")
    return None

def send_test_intent():
    """Send a test intent to QIP"""
    print("\n📤 Sending test intent to QIP...")
    
    message = {
        "sender_id": "fix_qip_test",
        "recipient_id": "quantum_intelligence_prime",
        "channel": "intent_requests",
        "msg_type": "health_check",
        "payload": {"command": "diagnostic", "test": "fix_qip_poll"},
        "ttl_hops": 10,
        "ttl_seconds": 60
    }
    
    try:
        resp = requests.post(f"{BROKER}/mesh/send", json=message, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            print(f"✅ Test intent sent: {result.get('message_id')}")
            return True
        else:
            print(f"❌ Failed to send intent: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending intent: {e}")
        return False

def main():
    print("=" * 60)
    print("FIX QIP POLLING ISSUE")
    print("Switching from mesh bus to HTTP transport")
    print("=" * 60)
    
    # Step 1: Backup original file
    print("\n📋 Step 1: Backup original file")
    original = backup_file()
    if not original:
        return
    
    # Step 2: Fix the file
    print("\n🔧 Step 2: Modify QIP file")
    if not fix_qip_file():
        print("⚠️ Proceeding anyway...")
    
    # Step 3: Get initial status
    print("\n📊 Step 3: Check initial QIP status")
    initial_status = get_qip_status()
    if initial_status:
        print(f"   Initial intents_completed: {initial_status['completed']}")
        print(f"   Initial transport: {initial_status['transport']}")
        print(f"   Initial mesh_native: {initial_status['mesh_native']}")
    else:
        print("❌ Could not get initial status")
    
    # Step 4: Restart QIP
    if not restart_qip():
        print("⚠️ Continuing despite restart issues...")
    
    # Step 5: Wait for QIP to register
    print("\n⏳ Step 4: Waiting for QIP to register (10 seconds)...")
    time.sleep(10)
    
    # Step 6: Check new status
    print("\n📊 Step 5: Check QIP status after restart")
    new_status = get_qip_status()
    if new_status:
        print(f"   New intents_completed: {new_status['completed']}")
        print(f"   New transport: {new_status['transport']}")
        print(f"   New mesh_native: {new_status['mesh_native']}")
    else:
        print("❌ Could not get new status")
    
    # Step 7: Send test intent
    if send_test_intent():
        # Step 8: Wait and check if intent was processed
        print("\n⏳ Step 6: Waiting for intent processing (20 seconds)...")
        time.sleep(20)
        
        # Step 9: Check final status
        print("\n📊 Step 7: Check final QIP status")
        final_status = get_qip_status()
        if final_status and initial_status:
            delta = final_status['completed'] - initial_status['completed']
            if delta > 0:
                print(f"🎉 SUCCESS: intents_completed increased by {delta}!")
                print(f"   From {initial_status['completed']} to {final_status['completed']}")
            else:
                print(f"⚠️ No increase in intents_completed (still {final_status['completed']})")
                print("   Possible issues:")
                print("   1. QIP not subscribed to channels")
                print("   2. Message not delivered to QIP")
                print("   3. QIP not processing intents")
        else:
            print("❌ Could not compare status")
    else:
        print("❌ Could not send test intent")
    
    print("\n" + "=" * 60)
    print("FIX COMPLETE")
    print("=" * 60)
    
    if initial_status and new_status:
        print(f"\nSummary:")
        print(f"  Initial intents_completed: {initial_status['completed']}")
        print(f"  Final intents_completed: {new_status.get('completed', 'unknown')}")
        print(f"  Transport changed to: {new_status.get('transport', 'unknown')}")
        print(f"  Mesh native changed to: {new_status.get('mesh_native', 'unknown')}")
    
    print(f"\nNext steps:")
    print("1. Check QIP logs: tail -f data/logs/goose/qip_fixed.log")
    print("2. Check gate4 inbox for quantum signals")
    print("3. Monitor intents_completed via:")
    print(f"   curl {BROKER}/agents/quantum_intelligence_prime | jq .agent.intents_completed")

if __name__ == "__main__":
    main()
