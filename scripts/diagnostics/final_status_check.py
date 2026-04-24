#!/usr/bin/env python3.10
"""
Final status check of the revenue pipeline
"""

import json
import requests
import os
from datetime import datetime

BROKER = "http://127.0.0.1:5555"

def check_qip_status():
    """Check QIP agent status"""
    print("🔍 Checking QIP Status:")
    try:
        resp = requests.get(f"{BROKER}/agents/quantum_intelligence_prime", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            agent = data.get("agent", {})
            print(f"   ✅ QIP is registered")
            print(f"   - Heartbeats: {agent.get('heartbeat_count', 0)}")
            print(f"   - Intents received: {agent.get('intents_received', 0)}")
            print(f"   - Intents completed: {agent.get('intents_completed', 0)}")
            print(f"   - Transport: {agent.get('metadata', {}).get('transport', 'unknown')}")
            return agent.get('intents_completed', 0)
        else:
            print(f"   ❌ QIP not found (HTTP {resp.status_code})")
            return 0
    except Exception as e:
        print(f"   ❌ Error checking QIP: {e}")
        return 0

def check_gate4_inbox():
    """Check gate4 inbox for signals"""
    print("\n📥 Checking Gate4 Inbox:")
    inbox_path = "data/inboxes/gate4_real"
    
    if not os.path.exists(inbox_path):
        print(f"   ❌ Inbox path not found: {inbox_path}")
        return 0
    
    # Check for processed signals
    processed_dir = os.path.join(inbox_path, "_processed")
    if os.path.exists(processed_dir):
        files = [f for f in os.listdir(processed_dir) if f.endswith('.json')]
        print(f"   ✅ Found {len(files)} processed signal files")
        
        # Check most recent files
        if files:
            files.sort(key=lambda x: os.path.getmtime(os.path.join(processed_dir, x)), reverse=True)
            recent = files[:3]
            print(f"   - Most recent: {recent[0]}")
            
            # Check source of most recent signal
            try:
                with open(os.path.join(processed_dir, recent[0]), 'r') as f:
                    signal = json.load(f)
                source = signal.get('metadata', {}).get('signal_source', 'unknown')
                print(f"   - Signal source: {source}")
                return len(files)
            except:
                print(f"   - Could not read signal file")
    else:
        print(f"   ⚠️ No processed directory found")
    
    return 0

def check_gate4_consumer():
    """Check if gate4 consumer is running"""
    print("\n🔄 Checking Gate4 Consumer:")
    try:
        result = os.popen("ps aux | grep gate4_inbox_consumer | grep -v grep").read().strip()
        if result:
            print(f"   ✅ Gate4 consumer is running")
            if "dry-run" in result.lower():
                print(f"   ⚠️ Running in DRY-RUN mode (no live trading)")
            return True
        else:
            print(f"   ❌ Gate4 consumer is NOT running")
            return False
    except:
        print(f"   ❌ Error checking gate4 consumer")
        return False

def check_broker_health():
    """Check SIMP broker health"""
    print("\n🏥 Checking SIMP Broker:")
    try:
        resp = requests.get(f"{BROKER}/agents", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            agents = data.get("agents", {})
            print(f"   ✅ Broker is healthy")
            print(f"   - Active agents: {len(agents)}")
            
            # Count agents by type
            types = {}
            for agent_id, agent in agents.items():
                agent_type = agent.get('agent_type', 'unknown')
                types[agent_type] = types.get(agent_type, 0) + 1
            
            for agent_type, count in types.items():
                print(f"   - {agent_type}: {count}")
            return True
        else:
            print(f"   ❌ Broker error: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Broker unreachable: {e}")
        return False

def check_kloutbot_bridge():
    """Check KLOUTBOT bridge"""
    print("\n🤖 Checking KLOUTBOT Bridge:")
    try:
        result = os.popen("ps aux | grep kloutbot_bridge | grep -v grep").read().strip()
        if result:
            print(f"   ✅ KLOUTBOT bridge is running")
            return True
        else:
            print(f"   ❌ KLOUTBOT bridge is NOT running")
            return False
    except:
        print(f"   ❌ Error checking KLOUTBOT bridge")
        return False

def main():
    print("=" * 60)
    print("FINAL REVENUE PIPELINE STATUS CHECK")
    print("=" * 60)
    
    # Run all checks
    broker_ok = check_broker_health()
    qip_intents = check_qip_status()
    gate4_signals = check_gate4_inbox()
    gate4_running = check_gate4_consumer()
    kloutbot_ok = check_kloutbot_bridge()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    # Overall status
    if gate4_signals > 0 and gate4_running:
        print("✅ REVENUE WIRE IS LIVE")
        print(f"   - {gate4_signals} signals processed by gate4")
        print(f"   - Gate4 consumer is running")
    else:
        print("⚠️ REVENUE WIRE HAS ISSUES")
        if gate4_signals == 0:
            print("   - No signals processed by gate4")
        if not gate4_running:
            print("   - Gate4 consumer not running")
    
    # QIP status
    if qip_intents == 0:
        print("⚠️ QUANTUM INTELLIGENCE OFFLINE")
        print(f"   - QIP has completed 0 intents")
        print("   - System using fallback signals")
    else:
        print(f"✅ QUANTUM INTELLIGENCE ACTIVE")
        print(f"   - QIP has completed {qip_intents} intents")
    
    # KLOUTBOT status
    if kloutbot_ok:
        print("✅ KLOUTBOT INTEGRATION READY")
        print("   - Claude ↔ Goose communication operational")
    else:
        print("⚠️ KLOUTBOT INTEGRATION OFFLINE")
        print("   - Need to start scripts/kloutbot/kloutbot_bridge.py")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if qip_intents == 0:
        print("1. Fix QIP transport issue:")
        print("   - QIP uses mesh bus but needs HTTP polling")
        print("   - Or switch QIP to HTTP transport completely")
    
    if not gate4_running:
        print("2. Start gate4 consumer:")
        print("   cd /path/to/simp")
        print("   source venv_gate4/bin/activate")
        print("   python3.10 gate4_inbox_consumer.py")
    
    if not kloutbot_ok:
        print("3. Start KLOUTBOT bridge:")
        print("   python3.10 scripts/kloutbot/kloutbot_bridge.py --loop")
    
    print("\n" + "=" * 60)
    print(f"Check completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
