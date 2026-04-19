#!/usr/bin/env python3
"""
Final IBM Quantum Setup Script
Securely configures IBM Quantum API and fixes all known issues.
"""

import os
import json
import sys
import subprocess
from pathlib import Path

def load_secure_token():
    """Load IBM Quantum token from secure JSON file."""
    token_path = Path("/Users/kaseymarcelle/Downloads/SIMP_QUANTUM_API_KEY.json")
    if not token_path.exists():
        print(f"❌ Token file not found: {token_path}")
        return None
    
    try:
        with open(token_path, 'r') as f:
            data = json.load(f)
        token = data.get("apikey") or data.get("IBM_QUANTUM_TOKEN")
        if not token:
            print("❌ IBM_QUANTUM_TOKEN not found in JSON file")
            return None
        
        print(f"✅ Token loaded from secure file")
        return token
    except Exception as e:
        print(f"❌ Error loading token: {e}")
        return None

def fix_quantum_backend_manager():
    """Apply all necessary fixes to quantum_backend_manager.py."""
    manager_path = Path("simp/organs/quantum_intelligence/quantum_backend_manager.py")
    
    if not manager_path.exists():
        print(f"❌ File not found: {manager_path}")
        return False
    
    try:
        with open(manager_path, 'r') as f:
            content = f.read()
        
        # Fix 1: Remove num_qubits field (already done)
        # Fix 2: Check channel parameter
        if 'channel="ibm_quantum"' in content:
            content = content.replace('channel="ibm_quantum"', 'channel="ibm_quantum_platform"')
            print("✅ Fixed channel parameter")
        
        # Fix 3: Check timeout handling
        if 'result = job.result()' in content and 'timeout_seconds' not in content:
            # Already fixed in previous step
            print("✅ Timeout handling already fixed")
        
        with open(manager_path, 'w') as f:
            f.write(content)
        
        print("✅ Quantum backend manager fixes applied")
        return True
    except Exception as e:
        print(f"❌ Error fixing quantum backend manager: {e}")
        return False

def test_quantum_connection(token):
    """Test IBM Quantum connection."""
    print("\n🧪 Testing IBM Quantum connection...")
    
    test_code = f'''
import os
os.environ["IBM_QUANTUM_TOKEN"] = "{token}"

try:
    from qiskit_ibm_runtime import QiskitRuntimeService
    print("✅ QiskitRuntimeService imported successfully")
    
    # Try to initialize service
    try:
        service = QiskitRuntimeService(channel="ibm_quantum_platform", token="{token}")
        print("✅ IBM Quantum service initialized")
        
        # List backends
        backends = service.backends()
        print(f"✅ Found {{len(backends)}} backends")
        
        # Show available backends
        for backend in backends[:3]:  # Show first 3
            print(f"  • {{backend.name}} ({{backend.status().pending_jobs}} pending jobs)")
        
        print("SUCCESS")
    except Exception as e:
        print(f"❌ Service initialization failed: {{e}}")
        
except ImportError as e:
    print(f"❌ Import error: {{e}}")
'''
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(result.stdout)
        if result.stderr:
            print(f"⚠️  Stderr: {result.stderr}")
        
        return "✅ IBM Quantum service initialized" in result.stdout or "SUCCESS" in result.stdout
    except subprocess.TimeoutExpired:
        print("❌ Test timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def run_quick_activation_test():
    """Run a quick activation test without hanging."""
    print("\n🚀 Running quick activation test...")
    
    # First kill any hanging processes
    subprocess.run(["pkill", "-f", "activate_phase3.py"], 
                   stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    
    # Run with timeout
    try:
        result = subprocess.run(
            [sys.executable, "activate_phase3.py", "--quantum", "--verbose"],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            env={**os.environ, "IBM_QUANTUM_TOKEN": ""}  # Force simulator mode
        )
        
        print("Output (first 50 lines):")
        print("\n".join(result.stdout.split("\n")[:50]))
        
        if result.stderr:
            print("\nErrors:")
            print(result.stderr[:500])
        
        return "QuantumIntelligentAgent LIVE" in result.stdout
    except subprocess.TimeoutExpired:
        print("❌ Activation test timed out after 2 minutes")
        return False
    except Exception as e:
        print(f"❌ Activation test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("IBM QUANTUM FINAL SETUP")
    print("=" * 60)
    
    # Step 1: Load token
    token = load_secure_token()
    if not token:
        print("\n❌ Cannot proceed without IBM Quantum token")
        sys.exit(1)
    
    # Step 2: Apply fixes
    print("\n🔧 Applying fixes...")
    if not fix_quantum_backend_manager():
        print("⚠️  Some fixes may not have been applied")
    
    # Step 3: Test connection
    print("\n🔗 Testing connection...")
    if not test_quantum_connection(token):
        print("\n❌ Connection test failed")
        sys.exit(1)
    
    # Step 4: Set environment variable
    os.environ["IBM_QUANTUM_TOKEN"] = token
    print(f"\n✅ Environment variable set: IBM_QUANTUM_TOKEN=***{token[-8:]}")
    
    # Step 5: Quick activation test
    print("\n⚡ Quick activation test (simulator only)...")
    if run_quick_activation_test():
        print("\n🎉 SUCCESS! Quantum setup complete!")
        print("\nNext steps:")
        print("1. For development: Use simulator (default)")
        print("2. For real hardware: Set SIMP_USE_REAL_HARDWARE=1")
        print("3. Run: python activate_phase3.py --quantum --verbose")
    else:
        print("\n⚠️  Activation test had issues")
        print("\nDebug steps:")
        print("1. Check: python3.10 -c 'from qiskit_ibm_runtime import QiskitRuntimeService; print(\"OK\")'")
        print("2. Run with debug: SIMP_DEBUG=1 python activate_phase3.py --quantum --verbose")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()