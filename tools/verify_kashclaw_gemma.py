#!/usr/bin/env python3
"""
Verification script for kashclaw_gemma agent on port 8780
"""
import requests
import json
import sys
import time
from typing import Dict, Optional

def verify_kashclaw_gemma(port: int = 8780, timeout: int = 10) -> Dict:
    """Verify kashclaw_gemma agent is running and healthy."""
    base_url = f"http://localhost:{port}"
    
    checks = {
        "reachable": False,
        "health_endpoint": False,
        "capabilities": False,
        "sample_query": False
    }
    
    print(f"Verifying kashclaw_gemma at {base_url}...")
    
    try:
        # Check if port is open and responding
        print("1. Checking health endpoint...")
        start_time = time.time()
        response = requests.get(f"{base_url}/health", timeout=timeout)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            checks["reachable"] = True
            checks["health_endpoint"] = True
            
            health_data = response.json()
            print(f"   ✓ Health endpoint OK ({response_time:.0f}ms): {health_data}")
            
            # Check capabilities (if endpoint exists)
            print("2. Checking capabilities...")
            try:
                caps_response = requests.get(f"{base_url}/capabilities", timeout=timeout)
                if caps_response.status_code == 200:
                    checks["capabilities"] = True
                    caps_data = caps_response.json()
                    print(f"   ✓ Capabilities: {caps_data}")
                else:
                    print(f"   ⚠ Capabilities endpoint returned {caps_response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"   ⚠ Capabilities endpoint not available: {e}")
                
            # Test with sample query
            print("3. Testing sample query...")
            test_payload = {
                "intent_type": "ping",
                "source_agent": "verification_script",
                "params": {"message": "verification test"}
            }
            
            try:
                test_response = requests.post(
                    f"{base_url}/handle",
                    json=test_payload,
                    timeout=timeout * 2  # Longer timeout for LLM queries
                )
                
                if test_response.status_code == 200:
                    checks["sample_query"] = True
                    test_result = test_response.json()
                    print(f"   ✓ Sample query successful: {test_result}")
                else:
                    print(f"   ✗ Sample query failed with status {test_response.status_code}")
                    
            except requests.exceptions.Timeout:
                print(f"   ✗ Sample query timeout (>{timeout*2}s)")
            except Exception as e:
                print(f"   ✗ Sample query error: {e}")
                
        else:
            print(f"✗ Health endpoint returned status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to kashclaw_gemma on port {port}")
        print(f"  Make sure kashclaw_gemma is running:")
        print(f"  python /Users/kaseymarcelle/bullbear/agents/kashclaw_gemma_agent.py")
    except requests.exceptions.Timeout:
        print(f"✗ Timeout connecting to kashclaw_gemma on port {port}")
    except Exception as e:
        print(f"✗ Verification error: {e}")
    
    return checks

def main():
    """Main verification function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify kashclaw_gemma agent")
    parser.add_argument("--port", type=int, default=8780, help="Port to check")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    
    args = parser.parse_args()
    
    if args.json:
        # JSON output for programmatic use
        import json as json_module
        results = verify_kashclaw_gemma(args.port, args.timeout)
        print(json_module.dumps(results, indent=2))
        sys.exit(0 if all(results.values()) else 1)
    else:
        # Human-readable output
        print("=" * 60)
        print("kashclaw_gemma Agent Verification")
        print("=" * 60)
        
        results = verify_kashclaw_gemma(args.port, args.timeout)
        
        print("\n" + "=" * 60)
        print("Verification Summary:")
        print("=" * 60)
        
        all_passed = True
        for check, status in results.items():
            status_symbol = "✓" if status else "✗"
            check_name = check.replace("_", " ").title()
            print(f"  {status_symbol} {check_name}")
            if not status:
                all_passed = False
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ kashclaw_gemma verification PASSED")
            print("\nAgent is ready for integration with SIMP broker.")
            sys.exit(0)
        else:
            print("❌ kashclaw_gemma verification FAILED")
            print("\nPlease fix the issues above before proceeding.")
            sys.exit(1)

if __name__ == "__main__":
    main()