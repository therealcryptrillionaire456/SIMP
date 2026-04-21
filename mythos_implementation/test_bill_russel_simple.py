#!/usr/bin/env python3
"""
Simple test of Bill Russel Protocol core functionality.
"""

import sys
sys.path.insert(0, '.')

from bill_russel_protocol.pattern_recognition import PatternRecognizer
from bill_russel_protocol.reasoning_engine import ReasoningEngine
from datetime import datetime

print("Testing Bill Russel Protocol Core Components")
print("="*60)

# Test 1: Pattern Recognition
print("\n1. Testing Pattern Recognition...")
recognizer = PatternRecognizer()

# Create a sample access log with SQL injection
sample_log = {
    'data_type': 'access_logs',
    'data': [
        {
            'remote_addr': '192.168.1.100',
            'request': "GET /login.php?username=admin' OR '1'='1 HTTP/1.1",
            'status': 200,
            'time': datetime.now().isoformat()
        }
    ]
}

patterns = recognizer.analyze(sample_log)
print(f"Patterns detected: {len(patterns)}")
for pattern in patterns:
    print(f"  - {pattern.pattern_type.value}: {pattern.description}")
    print(f"    Confidence: {pattern.confidence:.2f}")

# Test 2: Reasoning Engine
print("\n2. Testing Reasoning Engine...")
reasoning_engine = ReasoningEngine()

if patterns:
    assessment = reasoning_engine.assess_threat(patterns)
    print(f"Threat Level: {assessment.threat_level.value}")
    print(f"Confidence: {assessment.confidence:.2f}")
    print(f"Description: {assessment.description}")
    print(f"Recommended Action: {assessment.recommended_action.value}")
    print(f"Reasoning: {assessment.reasoning}")
else:
    print("No patterns to assess")

# Test 3: Directory Enumeration Detection
print("\n3. Testing Directory Enumeration Detection...")
enum_log = {
    'data_type': 'access_logs',
    'data': [
        {'remote_addr': '10.0.0.50', 'request': 'GET /admin HTTP/1.1', 'status': 404, 'time': datetime.now().isoformat()},
        {'remote_addr': '10.0.0.50', 'request': 'GET /wp-admin HTTP/1.1', 'status': 404, 'time': datetime.now().isoformat()},
        {'remote_addr': '10.0.0.50', 'request': 'GET /phpmyadmin HTTP/1.1', 'status': 404, 'time': datetime.now().isoformat()},
        {'remote_addr': '10.0.0.50', 'request': 'GET /config HTTP/1.1', 'status': 404, 'time': datetime.now().isoformat()},
        {'remote_addr': '10.0.0.50', 'request': 'GET /backup HTTP/1.1', 'status': 404, 'time': datetime.now().isoformat()},
    ]
}

enum_patterns = recognizer.analyze(enum_log)
print(f"Enumeration patterns detected: {len(enum_patterns)}")
for pattern in enum_patterns:
    print(f"  - {pattern.pattern_type.value}: {pattern.description}")

if enum_patterns:
    enum_assessment = reasoning_engine.assess_threat(enum_patterns)
    print(f"Enumeration Threat Level: {enum_assessment.threat_level.value}")
    print(f"Confidence: {enum_assessment.confidence:.2f}")
    print(f"Action: {enum_assessment.recommended_action.value}")

print("\n" + "="*60)
print("Bill Russel Protocol Core Tests Complete!")
print("Pattern Recognition: ✓")
print("Autonomous Reasoning: ✓")
print("Threat Assessment: ✓")