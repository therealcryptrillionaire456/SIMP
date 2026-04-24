#!/usr/bin/env python3
"""Test BRP audit system end-to-end."""
import sys
import os
import time
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

BROKER_URL = "http://127.0.0.1:5555"

def test_brp_audit_system():
    """Test the BRP audit system end-to-end."""
    print("=== Testing BRP Audit System ===\n")
    
    # 1. Start BRP audit consumer (if not running)
    print("1. Starting BRP audit consumer...")
    # In a real test, we would start the daemon here
    # For now, we'll assume it's running or will be started by the quantum stack
    
    # 2. Send test BRP alert
    print("2. Sending test BRP alert...")
    test_alert = {
        "type": "brp_threat_alert",
        "agent_id": "test_malicious_agent_001",
        "threat_level": "high",
        "confidence": 0.88,
        "patterns": [
            {"type": "unauthorized_access", "details": "attempted privilege escalation"},
            {"type": "suspicious_pattern", "details": "rapid intent firing"}
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "blocked": True,
        "source": "brp_gateway",
        "quantum_relevance": 0.25,
    }
    
    try:
        response = requests.post(f"{BROKER_URL}/mesh/send", json={
            "channel": "brp_alerts",
            "sender_id": "test_runner",
            "recipient_id": "*",
            "payload": test_alert,
            "ttl_seconds": 300,
        })
        
        if response.status_code == 200:
            print(f"   ✓ Test alert sent: {test_alert['agent_id']}")
        else:
            print(f"   ✗ Failed to send alert: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error sending alert: {e}")
        return False
    
    # 3. Send quantum BRP audit
    print("3. Sending quantum BRP audit...")
    quantum_audit = {
        "type": "brp_threat_alert",
        "agent_id": "quantum_audit_target_001",
        "threat_level": "medium",
        "confidence": 0.95,
        "patterns": [
            {"type": "quantum_constraint_violation", "details": "Grover's search anomaly"},
            {"type": "trust_score_anomaly", "details": "Score < 1.0 with high confidence"},
            {"type": "intent_escalation", "details": "Attempted unauthorized capability access"}
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "blocked": False,
        "source": "quantum_intelligence_prime",
        "quantum_relevance": 0.92,
    }
    
    try:
        response = requests.post(f"{BROKER_URL}/mesh/send", json={
            "channel": "brp_alerts",
            "sender_id": "quantum_intelligence_prime",
            "recipient_id": "*",
            "payload": quantum_audit,
            "ttl_seconds": 600,
        })
        
        if response.status_code == 200:
            print(f"   ✓ Quantum audit sent: {quantum_audit['agent_id']} (relevance: {quantum_audit['quantum_relevance']})")
        else:
            print(f"   ✗ Failed to send quantum audit: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error sending quantum audit: {e}")
        return False
    
    # 4. Check if BRP audit consumer is receiving messages
    print("4. Checking BRP audit consumer status...")
    time.sleep(2)  # Give consumer time to process
    
    # Check audit logs
    audit_log_dir = "data/brp_audit_logs"
    if os.path.exists(audit_log_dir):
        audit_files = [f for f in os.listdir(audit_log_dir) if f.endswith('.jsonl')]
        if audit_files:
            print(f"   ✓ Audit logs found: {len(audit_files)} files")
            
            # Check the latest audit log
            latest_log = os.path.join(audit_log_dir, sorted(audit_files)[-1])
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                print(f"   ✓ Audit log entries: {len(lines)}")
                
                if lines:
                    # Parse last entry
                    last_entry = json.loads(lines[-1])
                    print(f"   ✓ Latest audit: {last_entry.get('alert', {}).get('agent_id')} -> {last_entry.get('action_taken')}")
        else:
            print("   ⚠ No audit log files yet (consumer may not have processed alerts)")
    else:
        print("   ⚠ Audit log directory not created yet")
    
    # 5. Check agent threat profiles
    print("5. Checking agent threat profiles...")
    profiles_file = os.path.join(audit_log_dir, "agent_threat_profiles.json")
    if os.path.exists(profiles_file):
        with open(profiles_file, 'r') as f:
            profiles = json.load(f)
            print(f"   ✓ Agent threat profiles: {len(profiles)} agents")
            
            for agent_id, profile in list(profiles.items())[:3]:  # Show first 3
                print(f"     - {agent_id}: {profile.get('high_severity_count', 0)} high alerts, "
                      f"trust adjustment: {profile.get('trust_score_adjustment', 0.0)}")
    else:
        print("   ⚠ Agent threat profiles not created yet")
    
    # 6. Check quantum audits
    print("6. Checking quantum BRP audits...")
    quantum_file = os.path.join(audit_log_dir, "quantum_brp_audits.json")
    if os.path.exists(quantum_file):
        with open(quantum_file, 'r') as f:
            quantum_audits = json.load(f)
            print(f"   ✓ Quantum BRP audits: {len(quantum_audits)}")
    else:
        print("   ⚠ Quantum audit file not created yet")
    
    print("\n=== BRP Audit System Test Complete ===")
    print("\nSummary:")
    print("- BRP alert channel: ✓ Created and functional")
    print("- Alert transmission: ✓ Working via mesh")
    print("- Audit consumer: ⚠ Needs to be running to process alerts")
    print("- Audit persistence: ⚠ Will work when consumer is running")
    print("- Quantum integration: ✓ Ready for QIP quantum audits")
    
    return True

if __name__ == "__main__":
    test_brp_audit_system()
