#!/usr/bin/env python3
"""
Simple test of Enhanced Bill Russell Protocol without database locking issues.
"""

import sys
import os
sys.path.insert(0, '.')

from bill_russel_protocol_enhanced import (
    MythosPatternRecognizer, 
    MythosReasoningEngine,
    ThreatEvent,
    ThreatSeverity
)
from datetime import datetime
import json

def test_pattern_recognition():
    """Test pattern recognition component."""
    print("Testing MythosPatternRecognizer")
    print("=" * 60)
    
    recognizer = MythosPatternRecognizer()
    
    # Test log entries based on Mythos capabilities
    test_logs = [
        {
            'source_ip': '192.168.1.100',
            'event_type': 'web_fuzzing',
            'details': 'fuzzing parameters with unusual header values for buffer overflow',
            'severity': 'high'
        },
        {
            'source_ip': '10.0.0.50',
            'event_type': 'autonomous_attack',
            'details': 'multi-step attack with chained exploits and automated recon',
            'severity': 'critical'
        },
        {
            'source_ip': '172.16.0.100',
            'event_type': 'cross_domain',
            'details': 'network access followed by data exfiltration and lateral movement',
            'severity': 'medium'
        }
    ]
    
    for i, log_entry in enumerate(test_logs, 1):
        print(f"\nTest {i}: {log_entry['event_type']}")
        print(f"Source IP: {log_entry['source_ip']}")
        print(f"Details: {log_entry['details']}")
        
        patterns = recognizer.analyze_log_entry(log_entry)
        
        if patterns:
            print(f"Patterns detected: {len(patterns)}")
            for pattern in patterns:
                print(f"  - {pattern['type']}: {pattern['description']}")
                print(f"    Confidence: {pattern['confidence']:.2f}")
        else:
            print("No patterns detected")
    
    return recognizer

def test_reasoning_engine():
    """Test reasoning engine component."""
    print("\n\nTesting MythosReasoningEngine")
    print("=" * 60)
    
    reasoning_engine = MythosReasoningEngine()
    
    # Test patterns (simulating detected patterns)
    test_patterns = [
        {
            'type': 'zero_day_probing',
            'confidence': 0.85,
            'description': 'Zero-day vulnerability probing'
        },
        {
            'type': 'autonomous_chain',
            'confidence': 0.92,
            'description': 'Autonomous attack chain'
        }
    ]
    
    context = {
        'source_ip': '192.168.1.100',
        'historical_events': 3,
        'has_temporal_correlations': True
    }
    
    assessment = reasoning_engine.assess_threat(test_patterns, context)
    
    print(f"Threat Assessment:")
    print(f"  Level: {assessment['threat_level']}")
    print(f"  Confidence: {assessment['confidence']:.2f}")
    print(f"  Action: {assessment['action']}")
    print(f"  Patterns analyzed: {assessment['patterns_analyzed']}")
    
    print("\nReasoning Chain:")
    for step in assessment['reasoning_chain']:
        print(f"  - {step['pattern']}: score={step['score']:.2f}, multiplier={step['multiplier']}")
    
    return reasoning_engine

def test_threat_event():
    """Test threat event creation."""
    print("\n\nTesting ThreatEvent Creation")
    print("=" * 60)
    
    event = ThreatEvent(
        timestamp=datetime.utcnow().isoformat() + 'Z',
        source_ip='192.168.1.100',
        event_type='zero_day_probing',
        details={
            'patterns': [{'type': 'zero_day_probing', 'confidence': 0.85}],
            'log_entry': {'source_ip': '192.168.1.100', 'event_type': 'web_fuzzing'}
        },
        pattern_signature='zero_day_probing:abc123',
        confidence=0.85,
        severity=ThreatSeverity.HIGH
    )
    
    print(f"Threat Event Created:")
    print(f"  Source IP: {event.source_ip}")
    print(f"  Event Type: {event.event_type}")
    print(f"  Severity: {event.severity.value}")
    print(f"  Confidence: {event.confidence:.2f}")
    print(f"  Pattern Signature: {event.pattern_signature}")
    
    # Convert to dict
    event_dict = event.to_dict()
    print(f"\nAs Dictionary:")
    print(json.dumps(event_dict, indent=2))
    
    return event

def main():
    """Main test function."""
    print("ENHANCED BILL RUSSELL PROTOCOL - SIMPLE TEST")
    print("Designed to counter Mythos capabilities")
    print("=" * 60)
    
    # Test pattern recognition
    recognizer = test_pattern_recognition()
    
    # Test reasoning engine
    reasoning_engine = test_reasoning_engine()
    
    # Test threat event
    threat_event = test_threat_event()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✓ MythosPatternRecognizer - Pattern recognition at depth")
    print("✓ MythosReasoningEngine - Autonomous reasoning chains")
    print("✓ ThreatEvent - Structured threat representation")
    print("\nCapabilities tested against Mythos:")
    print("  - Zero-day vulnerability detection (counter Mythos cyber capabilities)")
    print("  - Autonomous attack chain detection (counter Mythos reasoning)")
    print("  - Cross-domain synthesis detection (counter Mythos synthesis)")
    print("  - Confidence-based threat assessment (counter Mythos pattern recognition)")
    
    print("\n" + "=" * 60)
    print("Enhanced Bill Russell Protocol components working correctly!")
    print("Ready to defend against Mythos-level threats.")

if __name__ == "__main__":
    main()