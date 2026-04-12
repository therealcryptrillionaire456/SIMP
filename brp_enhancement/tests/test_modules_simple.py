#!/usr/bin/env python3
"""
Simple test to verify all modules work correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration.modules.cai_module import CAIModule
from integration.modules.hexstrike_module import HexstrikeModule
from integration.modules.pentagi_module import PentagiModule
from integration.modules.openshell_module import OpenShellModule
from integration.modules.strix_module import StrixModule

def test_module(module_class, module_name):
    """Test a single module."""
    print(f"\nTesting {module_name}...")
    try:
        module = module_class()
        
        # Initialize
        print(f"  Initializing...")
        initialized = module.initialize()
        
        if not initialized:
            print(f"  ✗ Failed to initialize")
            return False
        
        print(f"  ✓ Initialized successfully")
        print(f"    Type: {module.module_type}")
        print(f"    Capabilities: {len(module.capabilities)}")
        
        # Check availability
        available = module.check_availability()
        print(f"    Available: {available}")
        
        # Get status
        status = module.get_status()
        print(f"    Status keys: {list(status.keys())}")
        
        # Test a simple operation if possible
        if module_name == "CAI":
            result = module.execute('analyze_prompt', {'prompt': 'Test prompt'})
            print(f"    Test operation: analyze_prompt -> {result.get('risk_score', 'N/A')}")
        elif module_name == "OpenShell":
            result = module.execute('system_info', {})
            print(f"    Test operation: system_info -> {'success' if 'system_info' in result else 'failed'}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Test all modules."""
    print("BRP Module Simple Test")
    print("=" * 50)
    
    modules_to_test = [
        (CAIModule, "CAI"),
        (HexstrikeModule, "hexstrike-ai"),
        (PentagiModule, "pentagi"),
        (OpenShellModule, "OpenShell"),
        (StrixModule, "strix")
    ]
    
    results = {}
    for module_class, module_name in modules_to_test:
        success = test_module(module_class, module_name)
        results[module_name] = success
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    print(f"\nModules tested: {total}")
    print(f"Modules passed: {passed}")
    print(f"Modules failed: {total - passed}")
    
    for module_name, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {module_name}")
    
    if passed == total:
        print("\n✅ ALL MODULES PASSED")
        return 0
    else:
        print(f"\n⚠️ {total - passed} MODULES FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())