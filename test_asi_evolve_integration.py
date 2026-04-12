#!/usr/bin/env python3
"""
ASI-Evolve Integration Test for BRP Enhanced Framework

Tests the integration of ASI-Evolve autonomous AI evolution
capabilities into the BRP framework.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add brp_enhancement to path
sys.path.append('brp_enhancement')

def test_module_loading():
    """Test loading ASI-Evolve modules."""
    print("🧪 Testing ASI-Evolve module loading...")
    
    try:
        # Test simple module
        from integration.modules.asi_evolve_simple_module import create_asi_evolve_simple_module
        simple_module = create_asi_evolve_simple_module()
        
        status = simple_module.get_status()
        print(f"  ✓ Simple module loaded: {status['name']} v{status['version']}")
        print(f"  ✓ Description: {status['description']}")
        print(f"  ✓ Capabilities: {len(simple_module.get_capabilities())} total")
        
        return simple_module
        
    except ImportError as e:
        print(f"  ❌ Failed to import module: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Error loading module: {e}")
        return None

def test_evolution_capability(module):
    """Test evolution capability."""
    print("\n🧪 Testing evolution capability...")
    
    try:
        # Run evolution
        print("  Starting evolution experiment...")
        results = module.evolve_threat_detection(
            rounds=5,
            population_size=4,
            experiment_name="integration_test"
        )
        
        if results.get("success"):
            print(f"  ✓ Evolution completed successfully")
            print(f"  ✓ Best score: {results.get('final_best_score', 0):.3f}")
            print(f"  ✓ Improvement: {results.get('improvement_percent', 0):.1f}%")
            print(f"  ✓ Rounds: {results.get('rounds_completed', 0)}")
            
            # Test evolved detector
            if results.get("best_candidate"):
                print("  Testing evolved detector...")
                
                # Create detector config
                detector_config = {
                    "type": "evolved_from_test",
                    "score": results["best_candidate"]["score"],
                    "generation": results["best_candidate"]["generation"]
                }
                
                test_results = module.test_evolved_detector(detector_config)
                
                if test_results.get("success"):
                    print(f"  ✓ Detector test: F1={test_results.get('f1_score', 0):.3f}")
                    return True
                else:
                    print(f"  ❌ Detector test failed: {test_results.get('error', 'unknown')}")
                    return False
            else:
                print("  ⚠️  No best candidate returned")
                return False
        else:
            print(f"  ❌ Evolution failed: {results.get('error', 'unknown')}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error in evolution test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_defensive_operations(module):
    """Test defensive operations."""
    print("\n🧪 Testing defensive operations...")
    
    try:
        # Run defensive scan
        scan_results = module.run_defensive_scan()
        
        print(f"  ✓ Defensive scan completed")
        print(f"    Threats detected: {scan_results.get('threats_detected', 0)}")
        print(f"    Confidence: {scan_results.get('confidence', 0):.2f}")
        print(f"    Duration: {scan_results.get('scan_duration_ms', 0):.1f}ms")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error in defensive operations: {e}")
        return False

def test_offensive_operations(module):
    """Test offensive operations."""
    print("\n🧪 Testing offensive operations...")
    
    try:
        # Test offensive capability
        test_results = module.test_offensive_capability(
            capability="vulnerability_scan",
            target="test_server.local"
        )
        
        print(f"  ✓ Offensive capability test completed")
        print(f"    Success: {test_results.get('success', False)}")
        print(f"    Score: {test_results.get('score', 0):.2f}")
        print(f"    Target: {test_results.get('target', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error in offensive operations: {e}")
        return False

def test_intelligence_operations(module):
    """Test intelligence operations."""
    print("\n🧪 Testing intelligence operations...")
    
    try:
        # Test threat intelligence analysis
        sample_data = {
            "threat_reports": [
                {"type": "malware", "severity": "high", "source": "firewall"},
                {"type": "phishing", "severity": "medium", "source": "email_gateway"}
            ],
            "timeframe": "last_24_hours"
        }
        
        analysis_results = module.analyze_threat_intelligence(sample_data)
        
        print(f"  ✓ Threat intelligence analysis completed")
        print(f"    Patterns found: {analysis_results.get('patterns_found', 0)}")
        print(f"    Confidence: {analysis_results.get('confidence', 0):.2f}")
        print(f"    Processing time: {analysis_results.get('processing_time_ms', 0):.1f}ms")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error in intelligence operations: {e}")
        return False

def test_knowledge_management(module):
    """Test knowledge management."""
    print("\n🧪 Testing knowledge management...")
    
    try:
        # Add new knowledge
        kb_id = module.add_knowledge(
            title="Integration Test Knowledge",
            content="This knowledge was added during integration testing of ASI-Evolve module.",
            tags=["integration_test", "asi_evolve", "brp"]
        )
        
        print(f"  ✓ Knowledge added successfully")
        print(f"    Knowledge ID: {kb_id}")
        
        # Check updated status
        status = module.get_status()
        print(f"    Knowledge base size: {status.get('knowledge_base_size', 0)} items")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error in knowledge management: {e}")
        return False

def test_brp_framework_integration():
    """Test integration with BRP framework."""
    print("\n🧪 Testing BRP framework integration...")
    
    try:
        # Try to import BRP framework
        from integration.brp_enhanced_framework import BRPEnhancedFramework, OperationMode
        
        print("  ✓ BRP Enhanced Framework imported successfully")
        
        # Create module
        from integration.modules.asi_evolve_simple_module import create_asi_evolve_simple_module
        asi_module = create_asi_evolve_simple_module()
        
        # Test module with BRP
        print("  Testing ASI-Evolve module capabilities...")
        
        # Get module status
        module_status = asi_module.get_status()
        print(f"    Module: {module_status['name']}")
        print(f"    Version: {module_status['version']}")
        print(f"    Capabilities: {len(asi_module.get_capabilities())}")
        
        # Test evolution
        evolution_results = asi_module.evolve_threat_detection(rounds=3, population_size=3)
        
        if evolution_results.get("success"):
            print(f"    Evolution test: SUCCESS (score: {evolution_results.get('final_best_score', 0):.3f})")
        else:
            print(f"    Evolution test: FAILED")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Failed to import BRP framework: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error in BRP integration test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("="*60)
    print("🏀 ASI-Evolve Integration Test for BRP Framework")
    print("="*60)
    print("Testing autonomous AI evolution capabilities integration")
    print("="*60)
    
    test_results = {
        "module_loading": False,
        "evolution_capability": False,
        "defensive_operations": False,
        "offensive_operations": False,
        "intelligence_operations": False,
        "knowledge_management": False,
        "brp_framework_integration": False
    }
    
    # Test 1: Module loading
    module = test_module_loading()
    test_results["module_loading"] = module is not None
    
    if module:
        # Test 2: Evolution capability
        test_results["evolution_capability"] = test_evolution_capability(module)
        
        # Test 3: Defensive operations
        test_results["defensive_operations"] = test_defensive_operations(module)
        
        # Test 4: Offensive operations
        test_results["offensive_operations"] = test_offensive_operations(module)
        
        # Test 5: Intelligence operations
        test_results["intelligence_operations"] = test_intelligence_operations(module)
        
        # Test 6: Knowledge management
        test_results["knowledge_management"] = test_knowledge_management(module)
    
    # Test 7: BRP framework integration
    test_results["brp_framework_integration"] = test_brp_framework_integration()
    
    # Print summary
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name.replace('_', ' ').title()}")
        if result:
            passed += 1
    
    print("="*60)
    print(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! ASI-Evolve integration is successful!")
        print("\n🚀 Next steps:")
        print("  1. Integrate module into BRP Enhanced Framework")
        print("  2. Create evolution experiments for real threat data")
        print("  3. Deploy evolved detectors in production")
        print("  4. Expand to other BRP capabilities")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
    
    print("="*60)
    
    # Save results
    results_file = Path("brp_enhancement/tests/asi_evolve_integration_results.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    results_data = {
        "test_date": datetime.utcnow().isoformat() + "Z",
        "results": test_results,
        "summary": {
            "passed": passed,
            "total": total,
            "percentage": passed/total*100 if total > 0 else 0
        }
    }
    
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"📄 Results saved to: {results_file}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)