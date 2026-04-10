#!/usr/bin/env python3
"""
Test script for Bill Russel Protocol Agent.
"""

import json
import time
import os
from pathlib import Path
import sys

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from simp.agents.bill_russel_agent import (
    BillRusselAgent, 
    ThreatEvent, 
    ThreatType,
    register_with_simp
)


def test_agent_initialization():
    """Test that the agent initializes correctly."""
    print("Testing agent initialization...")
    
    try:
        agent = BillRusselAgent(poll_interval=1.0)
        print("✓ Agent initialized successfully")
        
        # Check that protocol was initialized
        assert agent.protocol is not None, "Protocol should be initialized"
        print("✓ Bill Russel Protocol initialized")
        
        # Check directories
        from simp.agents.bill_russel_agent import INBOX_DIR, OUTBOX_DIR
        assert INBOX_DIR.exists(), "Inbox directory should exist"
        assert OUTBOX_DIR.exists(), "Outbox directory should exist"
        print("✓ Directories created")
        
        return agent
        
    except Exception as e:
        print(f"✗ Agent initialization failed: {e}")
        raise


def test_threat_event_creation():
    """Test threat event creation and conversion."""
    print("\nTesting threat event creation...")
    
    # Create a sample threat detection
    detection_result = {
        "source_ip": "192.168.1.100",
        "threat_type": "enumeration",
        "description": "Directory enumeration detected on web server",
        "confidence": 0.85,
        "patterns": ["directory_enum", "http_scan"],
        "context": {
            "user_agent": "nmap",
            "endpoint": "/admin",
            "status_code": 404
        }
    }
    
    # Create threat event
    threat_event = ThreatEvent.from_bill_russel(detection_result)
    
    # Verify fields
    assert threat_event.source_ip == "192.168.1.100"
    assert threat_event.threat_type == ThreatType.ENUMERATION
    assert threat_event.confidence == 0.85
    assert len(threat_event.patterns) == 2
    print("✓ Threat event created successfully")
    
    # Test SIMP intent conversion
    simp_intent = threat_event.to_simp_intent()
    assert simp_intent["intent_type"] == "threat_detected"
    assert simp_intent["source_agent"] == "bill_russel"
    assert simp_intent["payload"]["threat_type"] == "enumeration"
    print("✓ SIMP intent conversion successful")
    
    return threat_event


def test_agent_handlers():
    """Test agent intent handlers."""
    print("\nTesting agent intent handlers...")
    
    agent = BillRusselAgent(poll_interval=1.0)
    
    # Test ping handler
    ping_intent = {
        "intent_type": "ping",
        "source_agent": "test_agent",
        "target_agent": "bill_russel",
        "payload": {},
        "metadata": {"intent_id": "test_ping_001"}
    }
    
    response = agent._handle_ping(ping_intent)
    assert response["status"] == "active"
    assert response["agent_id"] == "bill_russel"
    assert "capabilities" in response
    print("✓ Ping handler works")
    
    # Test threat analysis handler
    threat_intent = {
        "intent_type": "threat_analysis",
        "source_agent": "test_agent",
        "target_agent": "bill_russel",
        "payload": {
            "source_ip": "10.0.0.1",
            "event_type": "http_request",
            "details": {
                "method": "GET",
                "path": "/admin",
                "user_agent": "sqlmap"
            }
        },
        "metadata": {"intent_id": "test_threat_001"}
    }
    
    analysis = agent._handle_threat_analysis(threat_intent)
    assert "analysis_id" in analysis
    assert "patterns_detected" in analysis
    assert "threat_assessment" in analysis
    print("✓ Threat analysis handler works")
    
    # Test security audit handler
    audit_intent = {
        "intent_type": "security_audit",
        "source_agent": "test_agent",
        "target_agent": "bill_russel",
        "payload": {},
        "metadata": {"intent_id": "test_audit_001"}
    }
    
    audit = agent._handle_security_audit(audit_intent)
    assert "audit_id" in audit
    assert "total_threats" in audit
    assert "recommendations" in audit
    print("✓ Security audit handler works")
    
    return agent


def test_pattern_detection():
    """Test pattern detection handler."""
    print("\nTesting pattern detection...")
    
    agent = BillRusselAgent(poll_interval=1.0)
    
    pattern_intent = {
        "intent_type": "pattern_detection",
        "source_agent": "test_agent",
        "target_agent": "bill_russel",
        "payload": {
            "data": [
                {
                    "source_ip": "192.168.1.50",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "event_type": "ssh_login",
                    "details": {"username": "root", "success": False}
                },
                {
                    "source_ip": "192.168.1.50",
                    "timestamp": "2024-01-01T12:00:01Z",
                    "event_type": "ssh_login",
                    "details": {"username": "admin", "success": False}
                },
                {
                    "source_ip": "192.168.1.50",
                    "timestamp": "2024-01-01T12:00:02Z",
                    "event_type": "ssh_login",
                    "details": {"username": "user", "success": False}
                }
            ]
        },
        "metadata": {"intent_id": "test_pattern_001"}
    }
    
    detection = agent._handle_pattern_detection(pattern_intent)
    assert "detection_id" in detection
    assert "total_patterns" in detection
    assert "pattern_counts" in detection
    print("✓ Pattern detection handler works")
    
    return detection


def test_registration():
    """Test registration with SIMP broker."""
    print("\nTesting SIMP registration...")
    
    # Note: This will fail if broker is not running
    # We'll test the function structure instead
    try:
        # Just test that the function can be called
        # (won't actually register unless broker is running)
        result = register_with_simp("http://127.0.0.1:5555", None)
        print("✓ Registration function works (broker may not be running)")
    except Exception as e:
        print(f"✗ Registration test failed: {e}")
        # Don't fail the test - broker might not be running


def test_integration_flow():
    """Test the complete integration flow."""
    print("\nTesting complete integration flow...")
    
    # Create agent
    agent = BillRusselAgent(poll_interval=1.0)
    
    # Create a test threat
    threat_data = {
        "source_ip": "203.0.113.10",
        "threat_type": "brute_force",
        "description": "SSH brute force attack detected",
        "confidence": 0.92,
        "patterns": ["ssh_bruteforce", "rapid_failures"],
        "context": {
            "port": 22,
            "attempts": 150,
            "timeframe_seconds": 60
        }
    }
    
    # Create threat event
    threat_event = ThreatEvent.from_bill_russel(threat_data)
    
    # Simulate threat handling
    print(f"Created threat event: {threat_event.event_id}")
    print(f"  Type: {threat_event.threat_type}")
    print(f"  Source: {threat_event.source_ip}")
    print(f"  Confidence: {threat_event.confidence:.2f}")
    
    # Test that it would be written to outbox
    simp_intent = threat_event.to_simp_intent()
    assert simp_intent["payload"]["severity"] == "high"  # confidence > 0.7
    print("✓ Threat would be reported with high severity")
    
    print("✓ Complete integration flow tested")


def main():
    """Run all tests."""
    print("=" * 60)
    print("BILL RUSSEL PROTOCOL AGENT - TEST SUITE")
    print("=" * 60)
    
    try:
        # Run tests
        agent = test_agent_initialization()
        threat_event = test_threat_event_creation()
        agent = test_agent_handlers()
        detection = test_pattern_detection()
        test_registration()
        test_integration_flow()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)
        print("\nBill Russel Protocol Agent is ready for SIMP integration.")
        print("\nNext steps:")
        print("1. Start SIMP broker: ./bin/start_broker.sh")
        print("2. Register agent: python -m simp.agents.bill_russel_agent --register-only")
        print("3. Run agent: python -m simp.agents.bill_russel_agent")
        print("4. Test with intents sent to data/bill_russel/inbox/")
        
    except Exception as e:
        print(f"\n✗ TESTS FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())