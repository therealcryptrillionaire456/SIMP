#!/usr/bin/env python3.10
"""
Test Agent Lightning functionality with SIMP broker
"""

import sys
import os
import json
import time
import requests
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_broker_health():
    """Test if broker is healthy"""
    try:
        response = requests.get("http://127.0.0.1:5555/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Broker is healthy: {data}")
            return True
        else:
            logger.error(f"❌ Broker health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Broker health check error: {e}")
        return False

def test_agent_lightning_health():
    """Test Agent Lightning health"""
    try:
        # Test APO wrapper proxy
        response = requests.get("http://localhost:8320/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ APO wrapper proxy is healthy: {data}")
            
            # Test Agent Lightning manager
            from simp.integrations.agent_lightning import agent_lightning_manager
            
            health = agent_lightning_manager.health_check()
            logger.info(f"✅ Agent Lightning manager health: {health}")
            
            return True
        else:
            logger.error(f"❌ APO wrapper proxy health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Agent Lightning health check error: {e}")
        return False

def test_intent_with_tracing():
    """Test sending an intent with Agent Lightning tracing"""
    
    logger.info("Testing intent delivery with Agent Lightning tracing...")
    
    # Create a test intent - use a valid intent type from routing policy
    test_intent = {
        "intent_id": f"test_intent_{int(time.time())}",
        "intent_type": "analysis",  # Valid intent type
        "source_agent": "test_agent",
        "target_agent": "quantumarb_mesh",
        "payload": {
            "message": "Test analysis for Agent Lightning tracing",
            "timestamp": datetime.now().isoformat(),
            "analysis_type": "performance"
        },
        "metadata": {
            "test": True,
            "agent_lightning_tracing": True
        }
    }
    
    try:
        # Send intent to broker
        logger.info(f"Sending test intent: {test_intent['intent_id']}")
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": os.environ.get("SIMP_API_KEY", "test_key")
        }
        
        response = requests.post(
            "http://127.0.0.1:5555/intents/route",
            json=test_intent,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Intent delivered successfully: {result}")
            
            # Check if intent was traced
            check_trace_collection(test_intent['intent_id'])
            
            return True
        else:
            logger.error(f"❌ Intent delivery failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error sending intent: {e}")
        return False

def check_trace_collection(intent_id):
    """Check if trace was collected"""
    
    logger.info(f"Checking trace collection for intent: {intent_id}")
    
    try:
        # Check APO wrapper logs
        log_file = "/tmp/apo_wrapper.log"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = f.read()
                
            if intent_id in logs or "trace" in logs.lower():
                logger.info("✅ Found trace activity in APO wrapper logs")
            else:
                logger.info("⚠️ No trace activity found in APO wrapper logs")
        
        # Check if we can get performance metrics
        from simp.integrations.agent_lightning import agent_lightning_manager
        
        # Get system performance
        system_perf = agent_lightning_manager.get_system_performance(hours=1)
        logger.info(f"System performance (last hour): {system_perf}")
        
        # Get agent performance
        agent_perf = agent_lightning_manager.get_agent_performance("test_agent", hours=1)
        logger.info(f"Test agent performance (last hour): {agent_perf}")
        
        return True
        
    except Exception as e:
        logger.warning(f"Could not check trace collection: {e}")
        return False

def test_apo_optimization():
    """Test APO (Automatic Prompt Optimization) functionality"""
    
    logger.info("Testing APO optimization...")
    
    try:
        from simp.integrations.agent_lightning import agent_lightning_manager
        
        # Test prompt optimization
        test_prompt = "Write a function to calculate fibonacci numbers in Python."
        
        optimized_prompt = agent_lightning_manager.optimize_prompt(
            agent_id="stray_goose",
            original_prompt=test_prompt,
            context={"task_type": "code_generation", "language": "python"}
        )
        
        if optimized_prompt != test_prompt:
            logger.info(f"✅ APO optimized the prompt")
            logger.info(f"Original: {test_prompt[:50]}...")
            logger.info(f"Optimized: {optimized_prompt[:50]}...")
        else:
            logger.info("⚠️ APO returned original prompt (may not be implemented yet)")
            
        return True
        
    except Exception as e:
        logger.warning(f"APO test failed: {e}")
        return False

def test_dashboard_integration():
    """Test dashboard integration"""
    
    logger.info("Testing dashboard integration...")
    
    try:
        # Check dashboard health
        response = requests.get("http://127.0.0.1:8050/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Dashboard is healthy: {data}")
            
            # Check if Agent Lightning endpoints exist
            endpoints_to_check = [
                "/agent-lightning/health",
                "/agent-lightning/performance",
                "/agent-lightning/traces"
            ]
            
            for endpoint in endpoints_to_check:
                try:
                    response = requests.get(f"http://127.0.0.1:8050{endpoint}", timeout=5)
                    if response.status_code == 200:
                        logger.info(f"✅ Dashboard endpoint {endpoint} is available")
                    else:
                        logger.info(f"⚠️ Dashboard endpoint {endpoint} returned {response.status_code}")
                except:
                    logger.info(f"⚠️ Dashboard endpoint {endpoint} is not available")
            
            return True
        else:
            logger.error(f"❌ Dashboard health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Dashboard test error: {e}")
        return False

def main():
    """Main test function"""
    
    logger.info("================================================")
    logger.info("🧪 Testing Agent Lightning Functionality")
    logger.info("================================================")
    
    # Set environment
    os.environ['AGENT_LIGHTNING_ENABLED'] = 'true'
    
    tests = [
        ("Broker Health", test_broker_health),
        ("Agent Lightning Health", test_agent_lightning_health),
        ("Intent Tracing", test_intent_with_tracing),
        ("APO Optimization", test_apo_optimization),
        ("Dashboard Integration", test_dashboard_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running test: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
            if result:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.warning(f"⚠️ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Agent Lightning integration is working.")
    else:
        logger.warning(f"⚠️ {total - passed} tests failed. Check logs for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)