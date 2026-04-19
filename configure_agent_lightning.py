#!/usr/bin/env python3.10
"""
Configure Agent Lightning properly for SIMP integration
"""

import os
import sys
import json

# Set environment variables before importing
os.environ['AGENT_LIGHTNING_ENABLED'] = 'true'
os.environ['AGENT_LIGHTNING_PROXY_HOST'] = 'localhost'
os.environ['AGENT_LIGHTNING_PROXY_PORT'] = '8320'  # Our APO wrapper
os.environ['AGENT_LIGHTNING_STORE_HOST'] = 'localhost'
os.environ['AGENT_LIGHTNING_STORE_PORT'] = '43887'
os.environ['AGENT_LIGHTNING_MODEL'] = 'glm-4-plus'
os.environ['AGENT_LIGHTNING_ENABLE_APO'] = 'true'
os.environ['AGENT_LIGHTNING_TRACE_ALL_AGENTS'] = 'true'

# Configure APO narrowly for Stray Goose
os.environ['AGENT_LIGHTNING_TRACE_SPECIFIC_AGENTS'] = 'stray_goose'
os.environ['AGENT_LIGHTNING_APO_AGENTS'] = 'stray_goose'

print("🚀 Configuring Agent Lightning for SIMP integration")
print("=" * 50)

# Now import and configure
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Force reload of the module
    import simp.integrations.agent_lightning as agl_module
    import importlib
    importlib.reload(agl_module)
    
    from simp.integrations.agent_lightning import agent_lightning_manager
    
    # Manually update configuration
    agent_lightning_manager.config.enabled = True
    agent_lightning_manager.config.proxy_port = 8320
    agent_lightning_manager.config.trace_all_agents = True
    agent_lightning_manager.config.enable_apo = True
    agent_lightning_manager.config.trace_specific_agents = ['stray_goose']
    
    print("✅ Agent Lightning configuration updated:")
    print(json.dumps(agent_lightning_manager.config.__dict__, indent=2))
    
    # Test health check
    health = agent_lightning_manager.health_check()
    print("\n✅ Agent Lightning health check:")
    print(json.dumps(health, indent=2))
    
    # Test proxy
    proxy_healthy = agent_lightning_manager.start_proxy()
    if proxy_healthy:
        print("\n✅ Agent Lightning proxy is healthy")
    else:
        print("\n⚠️ Agent Lightning proxy check failed")
    
    # Create APO configuration for Stray Goose
    print("\n🎯 Creating APO configuration for Stray Goose...")
    
    apo_config = {
        "agent": "stray_goose",
        "enabled": True,
        "scope": "narrow",
        "optimization_targets": [
            "reprompts_per_task",
            "task_completion_rate",
            "tool_call_efficiency"
        ],
        "constraints": {
            "never_modify": ["safety_checks", "ethical_guidelines"],
            "optimize_freely": ["tool_selection", "code_generation"]
        }
    }
    
    # Save APO config
    config_path = "/tmp/stray_goose_apo_config.json"
    with open(config_path, 'w') as f:
        json.dump(apo_config, f, indent=2)
    
    print(f"✅ APO configuration saved to {config_path}")
    
    # Test trace collection
    print("\n🧪 Testing trace collection...")
    
    from simp.integrations.agent_lightning import LLMCallTrace
    import uuid
    from datetime import datetime
    
    test_trace = LLMCallTrace(
        trace_id=str(uuid.uuid4()),
        agent_id="stray_goose",
        intent_type="test",
        model="glm-4-plus",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        response_time_ms=2500,
        success=True,
        metadata={"test": True, "timestamp": datetime.now().isoformat()}
    )
    
    trace_sent = agent_lightning_manager.trace_llm_call(test_trace)
    if trace_sent:
        print("✅ Test trace sent successfully")
    else:
        print("⚠️ Test trace not sent (store may not be running)")
    
    print("\n" + "=" * 50)
    print("🎉 Agent Lightning configuration complete!")
    print("\nNext steps:")
    print("1. Test with actual agent interactions")
    print("2. Check /tmp/apo_wrapper.log for APO activity")
    print("3. Integrate dashboard endpoints")
    print("4. Set up daily evaluation loop")
    
except Exception as e:
    print(f"❌ Error configuring Agent Lightning: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)