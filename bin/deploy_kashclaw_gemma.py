#!/usr/bin/env python3
"""
Deployment script for kashclaw_gemma integration
"""
import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Optional

# Add simp to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from simp.agent_registration import AgentRegistrar

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_api_key() -> Optional[str]:
    """Get API key from environment or config."""
    # Try environment variable first
    api_key = os.environ.get("SIMP_API_KEY")
    if api_key:
        return api_key
    
    # Try config file
    config_path = Path(__file__).parent.parent / "config" / "config.py"
    if config_path.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", config_path)
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
            if hasattr(config, "SIMP_API_KEY"):
                return config.SIMP_API_KEY
        except:
            pass
    
    return None

def deploy_kashclaw_gemma(port: int = 8780, broker_url: str = "http://localhost:5555", 
                         api_key: Optional[str] = None, skip_verification: bool = False):
    """
    Deploy kashclaw_gemma integration.
    
    Args:
        port: Port where kashclaw_gemma is running
        broker_url: SIMP broker URL
        api_key: API key for broker authentication
        skip_verification: Skip agent verification (not recommended)
    """
    print("=" * 60)
    print("kashclaw_gemma Integration Deployment")
    print("=" * 60)
    
    # Get API key if not provided
    if not api_key:
        api_key = get_api_key()
        if api_key:
            print(f"Using API key from environment/config")
        else:
            print("⚠ No API key provided. Some operations may fail.")
    
    registrar = AgentRegistrar(broker_url=broker_url, api_key=api_key)
    
    # Step 1: Verification
    if not skip_verification:
        print("\n[1/3] Verifying kashclaw_gemma agent...")
        verification = registrar.verify_agent(
            agent_id="kashclaw_gemma",
            endpoint=f"http://localhost:{port}"
        )
        
        if not verification.passed:
            print(f"\n❌ Verification FAILED:")
            for error in verification.errors:
                print(f"  - {error}")
            print(f"\nPlease ensure kashclaw_gemma is running on port {port}")
            print("Start it with: python /Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py")
            print("\nYou can skip verification with --skip-verification (not recommended)")
            sys.exit(1)
        
        print(f"✓ Agent reachable: {verification.reachable}")
        print(f"✓ Health status: {verification.health_status}")
        if verification.capabilities:
            print(f"✓ Capabilities: {', '.join(verification.capabilities)}")
        print(f"✓ Response time: {verification.response_time_ms:.0f}ms")
    else:
        print("\n⚠ Skipping verification (not recommended)")
    
    # Step 2: Registration
    print("\n[2/3] Registering with SIMP broker...")
    registration_result = registrar.register_kashclaw_gemma(port=port, verify=False)  # Already verified
    
    if registration_result.get("success"):
        print(f"✓ Successfully registered kashclaw_gemma")
        print(f"  Agent ID: {registration_result.get('agent_id')}")
        print(f"  Registered at: {registration_result.get('registered_at', 'N/A')}")
    else:
        print(f"❌ Registration failed: {registration_result.get('error')}")
        
        # Check if agent already exists
        print("\nChecking existing agents...")
        agents_result = registrar.list_agents()
        if agents_result.get("success"):
            agents = agents_result.get("agents", {})
            if "kashclaw_gemma" in agents:
                print("⚠ kashclaw_gemma already registered. Attempting to deregister and retry...")
                
                # Try to deregister first
                dereg_result = registrar.deregister_agent("kashclaw_gemma")
                if dereg_result.get("success"):
                    print("✓ Deregistered existing agent. Retrying registration...")
                    registration_result = registrar.register_kashclaw_gemma(port=port, verify=False)
                    if registration_result.get("success"):
                        print("✓ Successfully re-registered kashclaw_gemma")
                    else:
                        print(f"❌ Re-registration failed: {registration_result.get('error')}")
                        sys.exit(1)
                else:
                    print(f"❌ Failed to deregister existing agent: {dereg_result.get('error')}")
                    sys.exit(1)
        sys.exit(1)
    
    # Step 3: Test integration
    print("\n[3/3] Testing integration...")
    try:
        import requests
        
        # Test 1: Check agent appears in list
        agents_result = registrar.list_agents()
        if agents_result.get("success"):
            agents = agents_result.get("agents", {})
            if "kashclaw_gemma" in agents:
                print("✓ Agent appears in registered agents list")
            else:
                print("⚠ Agent not found in registered agents list")
        
        # Test 2: Send test intent through broker
        test_payload = {
            "intent_type": "ping",
            "source_agent": "deployment_script",
            "target_agent": "kashclaw_gemma",
            "params": {"message": "integration test from deployment"}
        }
        
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
            
        response = requests.post(
            f"{broker_url}/intents/route",
            json=test_payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✓ Integration test passed")
            result = response.json()
            print(f"  Delivery method: {result.get('delivery_method')}")
            print(f"  Intent ID: {result.get('intent_id')}")
            
            # Check if intent was actually delivered
            if result.get("delivery_method") == "http":
                print("  Note: Intent was queued for HTTP delivery")
            elif result.get("delivery_method") == "file_based":
                print("  Note: Intent was written to file for processing")
        else:
            print(f"⚠ Integration test returned status {response.status_code}")
            print(f"  Response: {response.text}")
            
    except Exception as e:
        print(f"⚠ Integration test error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ kashclaw_gemma integration COMPLETE")
    print("=" * 60)
    
    # Show next steps
    print("\n📋 Next steps:")
    print("1. Check agent status:")
    print(f"   curl {broker_url}/agents")
    print("2. Update routing policy to include kashclaw_gemma for planning/research intents")
    print("3. Test with a planning intent:")
    print(f"""   curl -X POST {broker_url}/intents/route \\
     -H "Content-Type: application/json" \\
     -H "X-API-Key: YOUR_API_KEY" \\
     -d '{{"intent_type":"planning","source_agent":"test","params":{{"task":"test planning"}}}}'""")
    print("4. Monitor health: Watch broker logs for agent heartbeats")
    print("\n📝 Notes:")
    print("- The routing policy needs to be updated to route planning/research intents to kashclaw_gemma")
    print("- See docs/phase1_kashclaw_gemma_integration.md for routing policy updates")
    print("- Run integration tests: python -m pytest tests/test_kashclaw_gemma_integration.py")

def check_prerequisites():
    """Check system prerequisites."""
    print("Checking prerequisites...")
    
    # Check Python version
    import platform
    python_version = platform.python_version()
    print(f"✓ Python version: {python_version}")
    
    # Check required packages
    required_packages = ["requests"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ Package: {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ Package missing: {package}")
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install requests")
        return False
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy kashclaw_gemma integration")
    parser.add_argument("--port", type=int, default=8780, help="kashclaw_gemma port")
    parser.add_argument("--broker", default="http://localhost:5555", help="SIMP broker URL")
    parser.add_argument("--api-key", help="Broker API key (default: from SIMP_API_KEY env var)")
    parser.add_argument("--skip-verification", action="store_true", help="Skip agent verification")
    parser.add_argument("--check-prerequisites", action="store_true", help="Check prerequisites only")
    
    args = parser.parse_args()
    
    if args.check_prerequisites:
        if check_prerequisites():
            print("\n✅ All prerequisites met")
            sys.exit(0)
        else:
            sys.exit(1)
    
    deploy_kashclaw_gemma(
        port=args.port,
        broker_url=args.broker,
        api_key=args.api_key,
        skip_verification=args.skip_verification
    )