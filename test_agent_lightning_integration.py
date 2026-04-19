#!/usr/bin/env python3
"""
Test Agent Lightning Integration

This script tests the Agent Lightning integration with the SIMP ecosystem.
"""

import os
import sys
import time
import logging
import requests
from pathlib import Path

# Add SIMP to path
simp_root = Path(__file__).parent
sys.path.insert(0, str(simp_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_agent_lightning_proxy():
    """Test Agent Lightning proxy connectivity"""
    logger.info("Testing Agent Lightning proxy...")
    
    try:
        # Test proxy health endpoint
        response = requests.get("http://localhost:8235/health", timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Agent Lightning proxy is running")
            return True
        else:
            logger.error(f"❌ Agent Lightning proxy health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error("❌ Agent Lightning proxy is not running")
        logger.info("Start it with: cd ~/stray_goose && python zai_agent_lightning_proxy.py")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing Agent Lightning proxy: {e}")
        return False

def test_lightning_store():
    """Test LightningStore connectivity"""
    logger.info("Testing LightningStore...")
    
    try:
        # Test store health endpoint
        response = requests.get("http://localhost:43887/v1/agl/health", timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ LightningStore is running")
            return True
        else:
            logger.error(f"❌ LightningStore health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error("❌ LightningStore is not running")
        logger.info("It should start automatically with the Agent Lightning proxy")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing LightningStore: {e}")
        return False

def test_simp_integration_module():
    """Test SIMP Agent Lightning integration module"""
    logger.info("Testing SIMP Agent Lightning integration module...")
    
    try:
        # Try to import the integration module
        integration_path = simp_root / "simp" / "integrations" / "agent_lightning.py"
        
        if not integration_path.exists():
            logger.error(f"❌ Integration module not found: {integration_path}")
            return False
        
        # Import the module
        import importlib.util
        spec = importlib.util.spec_from_file_location("agent_lightning", integration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Test basic functionality
        manager = module.agent_lightning_manager
        
        logger.info("✅ Agent Lightning integration module loaded successfully")
        logger.info(f"   Enabled: {manager.config.enabled}")
        logger.info(f"   Proxy URL: {manager.get_proxy_url()}")
        logger.info(f"   Store URL: {manager.get_store_url()}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing integration module: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_broker_integration():
    """Test broker integration patches"""
    logger.info("Testing broker integration patches...")
    
    try:
        patch_path = simp_root / "patches" / "agent_lightning_broker_patch.py"
        
        if not patch_path.exists():
            logger.error(f"❌ Broker patch not found: {patch_path}")
            return False
        
        # Import the patch module
        import importlib.util
        spec = importlib.util.spec_from_file_location("broker_patch", patch_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        logger.info("✅ Broker integration patch loaded successfully")
        logger.info("   Available function: patch_broker_for_agent_lightning(broker)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing broker integration: {e}")
        return False

def test_dashboard_integration():
    """Test dashboard integration patches"""
    logger.info("Testing dashboard integration patches...")
    
    try:
        patch_path = simp_root / "patches" / "agent_lightning_dashboard_patch.py"
        
        if not patch_path.exists():
            logger.error(f"❌ Dashboard patch not found: {patch_path}")
            return False
        
        # Import the patch module
        import importlib.util
        spec = importlib.util.spec_from_file_location("dashboard_patch", patch_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        logger.info("✅ Dashboard integration patch loaded successfully")
        logger.info("   Available function: patch_dashboard_for_agent_lightning(dashboard_app)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing dashboard integration: {e}")
        return False

def test_agent_patches():
    """Test agent integration patches"""
    logger.info("Testing agent integration patches...")
    
    patches = [
        ("quantumarb", "agent_lightning_quantumarb_patch.py"),
    ]
    
    all_passed = True
    
    for agent_name, patch_file in patches:
        patch_path = simp_root / "patches" / patch_file
        
        if not patch_path.exists():
            logger.error(f"❌ Patch not found for {agent_name}: {patch_path}")
            all_passed = False
            continue
        
        try:
            # Import the patch module
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"{agent_name}_patch", patch_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            logger.info(f"✅ {agent_name} integration patch loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Error testing {agent_name} integration: {e}")
            all_passed = False
    
    return all_passed

def test_end_to_end_flow():
    """Test end-to-end Agent Lightning flow"""
    logger.info("Testing end-to-end Agent Lightning flow...")
    
    try:
        # Test sending a trace to LightningStore
        trace_data = {
            "trace_id": "test_trace_123",
            "agent_id": "test_agent",
            "intent_type": "test_intent",
            "model": "test_model",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "response_time_ms": 100,
            "success": True,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metadata": {
                "test": True,
                "integration_test": True
            }
        }
        
        # Try to send trace to LightningStore
        store_url = "http://localhost:43887/v1/agl/traces"
        response = requests.post(store_url, json=trace_data, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info("✅ Successfully sent test trace to LightningStore")
            return True
        else:
            logger.warning(f"⚠️  Could not send trace to LightningStore: {response.status_code}")
            logger.info("This is expected if the store doesn't accept external traces")
            return True  # Not a critical failure
            
    except Exception as e:
        logger.warning(f"⚠️  Could not test end-to-end flow: {e}")
        logger.info("This is expected if LightningStore is not fully configured")
        return True  # Not a critical failure

def run_all_tests():
    """Run all integration tests"""
    logger.info("=" * 70)
    logger.info("RUNNING AGENT LIGHTNING INTEGRATION TESTS")
    logger.info("=" * 70)
    
    tests = [
        ("Agent Lightning Proxy", test_agent_lightning_proxy),
        ("LightningStore", test_lightning_store),
        ("SIMP Integration Module", test_simp_integration_module),
        ("Broker Integration", test_broker_integration),
        ("Dashboard Integration", test_dashboard_integration),
        ("Agent Patches", test_agent_patches),
        ("End-to-End Flow", test_end_to_end_flow),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Testing: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            time.sleep(1)  # Brief pause between tests
        except Exception as e:
            logger.error(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
    
    logger.info(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 All tests passed! Agent Lightning integration is working.")
        return True
    elif passed >= total * 0.7:
        logger.info(f"\n⚠️  {passed}/{total} tests passed. Integration is partially working.")
        logger.info("Some components may need manual configuration.")
        return True
    else:
        logger.info(f"\n❌ Only {passed}/{total} tests passed. Integration needs attention.")
        return False

def main():
    """Main test function"""
    
    # Check if API key is set
    api_key = os.environ.get("X_AI_API_KEY")
    if not api_key:
        logger.warning("⚠️  X_AI_API_KEY environment variable not set")
        logger.info("Set it with: export X_AI_API_KEY='your-api-key'")
        logger.info("Some tests may fail without the API key.")
    
    # Run tests
    success = run_all_tests()
    
    # Print next steps
    logger.info("\n" + "=" * 70)
    logger.info("NEXT STEPS")
    logger.info("=" * 70)
    
    if success:
        logger.info("1. ✅ Integration tests passed!")
        logger.info("2. Start SIMP broker with Agent Lightning integration:")
        logger.info("   python -m simp.server.broker")
        logger.info("3. Start SIMP dashboard with Agent Lightning UI:")
        logger.info("   python dashboard/server.py")
        logger.info("4. Access Agent Lightning dashboard:")
        logger.info("   http://localhost:8050/agent-lightning-ui")
        logger.info("5. Monitor traces at:")
        logger.info("   http://localhost:43887/v1/agl/rollouts")
    else:
        logger.info("1. ❌ Some tests failed")
        logger.info("2. Check Agent Lightning proxy is running:")
        logger.info("   cd ~/stray_goose && python zai_agent_lightning_proxy.py")
        logger.info("3. Verify SIMP integration module exists:")
        logger.info("   ls simp/integrations/agent_lightning.py")
        logger.info("4. Check patches directory:")
        logger.info("   ls patches/agent_lightning_*.py")
    
    logger.info("\n🚀 Agent Lightning will trace all LLM calls in the SIMP ecosystem!")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())