#!/usr/bin/env python3
"""
Basic test for BRP Enhanced Framework.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration.brp_enhanced_framework import BRPEnhancedFramework, OperationMode, ThreatSeverity
import json
import time

def test_framework_initialization():
    """Test framework initialization."""
    print("=== Test 1: Framework Initialization ===")
    
    # Test defensive mode
    framework = BRPEnhancedFramework(mode=OperationMode.DEFENSIVE)
    status = framework.get_system_status()
    
    print(f"Mode: {status['system']['mode']}")
    print(f"Repositories: {status['system']['repositories_integrated']}")
    print(f"Capabilities: {status['system']['total_capabilities']}")
    
    assert status['system']['mode'] == 'defensive'
    assert status['system']['repositories_integrated'] == 5
    assert status['system']['total_capabilities'] == 9
    
    print("✓ Framework initialization successful")
    return framework

def test_event_processing(framework):
    """Test event processing."""
    print("\n=== Test 2: Event Processing ===")
    
    # Submit test events
    test_events = [
        {
            'source': '192.168.1.100',
            'event_type': 'network_scan',
            'content': 'Port scanning detected',
            'timestamp': '2024-01-01T12:00:00Z'
        },
        {
            'source': '10.0.0.50',
            'event_type': 'binary_upload',
            'content': 'Suspicious binary file uploaded',
            'timestamp': '2024-01-01T12:01:00Z'
        },
        {
            'source': 'malicious.ai',
            'event_type': 'ai_prompt_injection',
            'content': 'Attempted prompt injection attack',
            'timestamp': '2024-01-01T12:02:00Z'
        }
    ]
    
    for event in test_events:
        framework.submit_event(event)
        print(f"Submitted event: {event['event_type']} from {event['source']}")
    
    # Wait for processing
    print("Waiting for event processing...")
    time.sleep(2)
    
    # Check status
    status = framework.get_system_status()
    print(f"Total events processed: {status['threats']['total_events']}")
    print(f"Unique sources: {status['threats']['unique_sources']}")
    
    assert status['threats']['total_events'] >= 3
    assert status['threats']['unique_sources'] >= 3
    
    print("✓ Event processing successful")

def test_defensive_scan(framework):
    """Test defensive scan."""
    print("\n=== Test 3: Defensive Scan ===")
    
    results = framework.run_defensive_scan()
    
    print(f"Repositories checked: {len(results['repositories_used'])}")
    print("Findings:")
    for finding in results['findings']:
        print(f"  - {finding['repository']}: {'Available' if finding['available'] else 'Not available'}")
    
    assert len(results['repositories_used']) > 0
    assert 'timestamp' in results
    
    print("✓ Defensive scan successful")

def test_offensive_test(framework):
    """Test offensive capability testing."""
    print("\n=== Test 4: Offensive Capability Test ===")
    
    # Test in defensive mode (should still work but be simulated)
    results = framework.test_offensive_capability("pentagi_scan", "test-target.local")
    
    print(f"Capability tested: {results['capability']}")
    print(f"Target: {results['target']}")
    print(f"Status: {results['status']}")
    
    assert results['capability'] == 'pentagi_scan'
    assert results['target'] == 'test-target.local'
    assert results['status'] == 'simulated'
    
    print("✓ Offensive capability test successful")

def test_mode_switching():
    """Test different operation modes."""
    print("\n=== Test 5: Mode Switching ===")
    
    modes_to_test = [
        OperationMode.DEFENSIVE,
        OperationMode.OFFENSIVE,
        OperationMode.HYBRID,
        OperationMode.INTELLIGENCE
    ]
    
    for mode in modes_to_test:
        framework = BRPEnhancedFramework(mode=mode)
        status = framework.get_system_status()
        print(f"  {mode.value}: {status['system']['mode']}")
        assert status['system']['mode'] == mode.value
    
    print("✓ Mode switching successful")

def test_database_integrity():
    """Test database integrity."""
    print("\n=== Test 6: Database Integrity ===")
    
    framework = BRPEnhancedFramework()
    
    # Submit some events
    for i in range(5):
        framework.submit_event({
            'source': f'test-source-{i}',
            'event_type': 'test_event',
            'content': f'Test content {i}',
            'timestamp': f'2024-01-01T12:{i:02d}:00Z'
        })
    
    time.sleep(1)
    
    # Run defensive scan
    framework.run_defensive_scan()
    
    # Test offensive capability
    framework.test_offensive_capability("test_capability")
    
    # Check all tables have data
    status = framework.get_system_status()
    
    print(f"Threat events: {status['threats']['total_events']}")
    print(f"Operations: {status['operations']['total']}")
    print(f"Capability stats: {len(status['capabilities'])} categories")
    
    assert status['threats']['total_events'] >= 5
    assert status['operations']['total'] >= 2  # scan + test
    
    print("✓ Database integrity verified")

def main():
    """Run all tests."""
    print("BRP Enhanced Framework - Basic Tests")
    print("=" * 50)
    
    try:
        # Test 1: Initialization
        framework = test_framework_initialization()
        
        # Test 2: Event processing
        test_event_processing(framework)
        
        # Test 3: Defensive scan
        test_defensive_scan(framework)
        
        # Test 4: Offensive test
        test_offensive_test(framework)
        
        # Test 5: Mode switching
        test_mode_switching()
        
        # Test 6: Database integrity
        test_database_integrity()
        
        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("\nFramework capabilities:")
        status = BRPEnhancedFramework().get_system_status()
        print(f"- Repositories: {status['system']['repositories_integrated']}")
        print(f"- Capabilities: {status['system']['total_capabilities']}")
        print(f"- Modes: defensive, offensive, hybrid, intelligence")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())