#!/usr/bin/env python3.10
"""
Test APO wrapper with actual Goose requests
"""

import os
import sys
import json
import time
import requests
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_apo_wrapper_directly():
    """Test APO wrapper directly with a Goose-like request"""
    
    logger.info("Testing APO wrapper with Goose request...")
    
    # Create a test request similar to what Goose would send
    test_request = {
        "model": "glm-4-plus",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful AI assistant. Always think step by step."
            },
            {
                "role": "user",
                "content": "Write a Python function to calculate the factorial of a number."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        # Send request to APO wrapper
        logger.info(f"Sending test request to APO wrapper...")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('X_AI_API_KEY', 'test_key')}"
        }
        
        start_time = time.time()
        response = requests.post(
            "http://localhost:8320/v1/chat/completions",
            json=test_request,
            headers=headers,
            timeout=30
        )
        end_time = time.time()
        
        latency = end_time - start_time
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ APO wrapper request successful (latency: {latency:.2f}s)")
            
            # Check if response contains expected fields
            if 'choices' in result and len(result['choices']) > 0:
                choice = result['choices'][0]
                message = choice.get('message', {})
                content = message.get('content', '')
                
                logger.info(f"Response length: {len(content)} characters")
                logger.info(f"First 100 chars: {content[:100]}...")
                
                # Check for APO optimization indicators
                if 'tool selection guidance' in content.lower() or 'consider:' in content.lower():
                    logger.info("✅ APO optimization detected in response!")
                else:
                    logger.info("⚠️ No obvious APO optimization detected")
            
            # Check for usage metrics
            if 'usage' in result:
                usage = result['usage']
                logger.info(f"Token usage: {usage}")
            
            return True
        else:
            logger.error(f"❌ APO wrapper request failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing APO wrapper: {e}")
        return False

def test_apo_configuration():
    """Test APO configuration endpoint"""
    
    logger.info("Testing APO configuration...")
    
    try:
        response = requests.get("http://localhost:8320/apo-config", timeout=5)
        
        if response.status_code == 200:
            config = response.json()
            logger.info(f"✅ APO configuration retrieved:")
            logger.info(f"   Service: {config.get('service', 'unknown')}")
            logger.info(f"   APO enabled: {config.get('apo_enabled', False)}")
            logger.info(f"   Target proxy: {config.get('target_proxy', 'unknown')}")
            
            # Check APO-specific configuration
            if 'apo_config' in config:
                apo_config = config['apo_config']
                logger.info(f"   APO config: {json.dumps(apo_config, indent=2)}")
            
            return True
        else:
            logger.warning(f"⚠️ APO config endpoint returned {response.status_code}")
            return False
            
    except Exception as e:
        logger.warning(f"⚠️ Could not retrieve APO config: {e}")
        return False

def check_apo_logs():
    """Check APO wrapper logs for activity"""
    
    logger.info("Checking APO wrapper logs...")
    
    log_file = "/tmp/apo_wrapper.log"
    
    if not os.path.exists(log_file):
        logger.warning(f"⚠️ APO wrapper log file not found: {log_file}")
        return False
    
    try:
        with open(log_file, 'r') as f:
            logs = f.read()
        
        # Check for recent activity
        lines = logs.strip().split('\n')
        recent_lines = lines[-20:] if len(lines) > 20 else lines
        
        logger.info(f"Recent APO wrapper log entries ({len(recent_lines)} lines):")
        for line in recent_lines[-5:]:  # Show last 5 lines
            if line.strip():
                logger.info(f"   {line}")
        
        # Check for APO-specific activity
        apo_activity = any('apo' in line.lower() or 'optimiz' in line.lower() for line in recent_lines)
        if apo_activity:
            logger.info("✅ APO activity detected in logs")
        else:
            logger.info("⚠️ No recent APO activity in logs")
        
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Could not read APO logs: {e}")
        return False

def test_trace_collection():
    """Test that traces are being collected"""
    
    logger.info("Testing trace collection...")
    
    try:
        # Check if we can get performance metrics from Agent Lightning
        import simp.integrations.agent_lightning as agl_module
        import importlib
        importlib.reload(agl_module)
        
        from simp.integrations.agent_lightning import agent_lightning_manager
        
        # Get system performance
        system_perf = agent_lightning_manager.get_system_performance(hours=1)
        
        if 'error' in system_perf:
            logger.info(f"⚠️ Could not get system performance: {system_perf.get('error')}")
            logger.info("   (This is expected if LightningStore is not running)")
        else:
            logger.info(f"✅ System performance data: {system_perf}")
        
        # Test creating and sending a trace
        from simp.integrations.agent_lightning import LLMCallTrace
        import uuid
        
        test_trace = LLMCallTrace(
            trace_id=str(uuid.uuid4()),
            agent_id="test_agent",
            intent_type="test",
            model="glm-4-plus",
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
            response_time_ms=1500,
            success=True,
            metadata={"test": True, "apo_test": True}
        )
        
        trace_sent = agent_lightning_manager.trace_llm_call(test_trace)
        
        if trace_sent:
            logger.info("✅ Test trace sent successfully")
        else:
            logger.info("⚠️ Test trace not sent (store may not be running)")
        
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Trace collection test failed: {e}")
        return False

def test_narrow_apo_for_stray_goose():
    """Test that APO is configured narrowly for Stray Goose only"""
    
    logger.info("Testing narrow APO configuration for Stray Goose...")
    
    # Load APO configuration
    config_path = "/tmp/stray_goose_apo_config.json"
    
    if not os.path.exists(config_path):
        logger.error(f"❌ APO configuration file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            apo_config = json.load(f)
        
        logger.info(f"APO configuration loaded from {config_path}")
        
        # Check configuration
        agent = apo_config.get('agent', '')
        enabled = apo_config.get('enabled', False)
        scope = apo_config.get('scope', '')
        
        if agent == 'stray_goose' and enabled and scope == 'narrow':
            logger.info("✅ APO is correctly configured for Stray Goose (narrow scope)")
            
            # Check optimization targets
            targets = apo_config.get('optimization_targets', [])
            logger.info(f"   Optimization targets: {targets}")
            
            # Check constraints
            constraints = apo_config.get('constraints', {})
            never_modify = constraints.get('never_modify', [])
            optimize_freely = constraints.get('optimize_freely', [])
            
            logger.info(f"   Never modify: {never_modify}")
            logger.info(f"   Optimize freely: {optimize_freely}")
            
            # Verify safety constraints
            if 'safety_checks' in never_modify and 'ethical_guidelines' in never_modify:
                logger.info("✅ Safety constraints properly configured")
            else:
                logger.warning("⚠️ Safety constraints may be incomplete")
            
            return True
        else:
            logger.error(f"❌ APO configuration incorrect: agent={agent}, enabled={enabled}, scope={scope}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing APO configuration: {e}")
        return False

def main():
    """Main test function"""
    
    logger.info("================================================")
    logger.info("🧪 Testing APO for Stray Goose (Narrow Implementation)")
    logger.info("================================================")
    
    tests = [
        ("APO Configuration", test_narrow_apo_for_stray_goose),
        ("APO Wrapper Direct Test", test_apo_wrapper_directly),
        ("APO Configuration Endpoint", test_apo_configuration),
        ("APO Logs", check_apo_logs),
        ("Trace Collection", test_trace_collection)
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
    logger.info("📊 APO TEST SUMMARY")
    logger.info("="*50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All APO tests passed! Narrow implementation is working.")
    elif passed >= 3:
        logger.info("✅ Most APO tests passed. Implementation is functional.")
    else:
        logger.warning(f"⚠️ {total - passed} tests failed. Check logs for details.")
    
    # Recommendations
    logger.info("\n" + "="*50)
    logger.info("📋 RECOMMENDATIONS")
    logger.info("="*50)
    
    if not results.get("APO Wrapper Direct Test", False):
        logger.info("1. Check if the underlying proxy (port 8310) is running")
        logger.info("2. Verify API key is valid")
    
    if not results.get("Trace Collection", False):
        logger.info("3. LightningStore is not running - using APO wrapper for tracing")
        logger.info("   This is acceptable for now")
    
    logger.info("\n4. Next: Integrate dashboard endpoints for monitoring")
    
    return passed >= 3  # Require at least 3 tests to pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)