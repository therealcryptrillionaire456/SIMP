#!/usr/bin/env python3
"""
Test if the Bill Russell agent can import our enhanced protocol.
"""

import sys
import os
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")

# Try to import the enhanced protocol
try:
    from mythos_implementation.bill_russel_protocol_enhanced import (
        MythosPatternRecognizer,
        MythosReasoningEngine,
        MythosMemorySystem,
        EnhancedBillRussellProtocol,
        ThreatEvent,
        ThreatSeverity
    )
    print("✓ Successfully imported enhanced Bill Russell Protocol")
    
    # Test creating instances
    print("\nTesting component creation:")
    
    recognizer = MythosPatternRecognizer()
    print(f"  ✓ MythosPatternRecognizer created")
    
    memory = MythosMemorySystem('test_import.db')
    print(f"  ✓ MythosMemorySystem created")
    
    reasoning = MythosReasoningEngine(memory)
    print(f"  ✓ MythosReasoningEngine created")
    
    protocol = EnhancedBillRussellProtocol('test_protocol.db')
    print(f"  ✓ EnhancedBillRussellProtocol created")
    
    # Test a simple analysis
    test_log = {
        'source_ip': '192.168.1.100',
        'event_type': 'test',
        'details': 'fuzzing parameters test',
        'severity': 'medium'
    }
    
    result = protocol.analyze_event(test_log)
    print(f"\n✓ Protocol analysis successful")
    print(f"  Patterns detected: {result['patterns_detected']}")
    print(f"  Threat level: {result['threat_assessment']['threat_level']}")
    
    # Clean up test databases
    for db_file in ['test_import.db', 'test_protocol.db']:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"  Cleaned up: {db_file}")
    
    print("\n" + "=" * 60)
    print("IMPORT TEST SUCCESSFUL!")
    print("Enhanced Bill Russell Protocol is ready for agent integration.")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("\nTrying to diagnose the issue...")
    
    # Check if file exists
    enhanced_file = project_root / 'mythos_implementation' / 'bill_russel_protocol_enhanced.py'
    print(f"Enhanced protocol file exists: {enhanced_file.exists()}")
    
    if enhanced_file.exists():
        print(f"File size: {enhanced_file.stat().st_size} bytes")
        
        # Try to read the file
        try:
            with open(enhanced_file, 'r') as f:
                content = f.read(500)
                print(f"First 500 chars:\n{content}")
        except Exception as e2:
            print(f"Error reading file: {e2}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()