#!/usr/bin/env python3
"""
Secure setup for IBM Quantum API key.
Reads from protected file and sets up environment/config.
"""

import os
import json
import sys
from pathlib import Path

def read_quantum_api_key():
    """Read IBM Quantum API key from secure location."""
    key_path = Path("/Users/kaseymarcelle/Downloads/SIMP_QUANTUM_API_KEY.json")
    
    if not key_path.exists():
        print(f"❌ API key file not found: {key_path}")
        return None
    
    try:
        with open(key_path, 'r') as f:
            data = json.load(f)
        
        api_key = data.get('apikey')
        if not api_key:
            print("❌ No 'apikey' field in JSON file")
            return None
        
        print(f"✅ Read IBM Quantum API key: {api_key[:8]}...{api_key[-4:]}")
        return api_key
        
    except Exception as e:
        print(f"❌ Error reading API key: {e}")
        return None

def setup_environment_variable(api_key):
    """Set IBM Quantum API key as environment variable."""
    os.environ['IBM_QUANTUM_TOKEN'] = api_key
    print("✅ Set IBM_QUANTUM_TOKEN environment variable")
    return True

def update_quantum_config(api_key):
    """Update quantum config file with real API key."""
    config_path = Path.home() / ".simp" / "quantum_config.json"
    
    if not config_path.parent.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Read existing config or create default
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {
                "preferred_backend": "local_simulator",
                "fallback_order": ["local_simulator", "qiskit_aer", "ibm_quantum"],
                "max_shots": 1024,
                "timeout_seconds": 30,
                "cost_limit_per_month": 0.0,
                "enable_real_hardware": False,
                "ibm_quantum": {
                    "enabled": True,
                    "api_token": "",
                    "hub": "ibm-q",
                    "group": "open",
                    "project": "main"
                },
                "amazon_braket": {"enabled": False, "region": "us-east-1"},
                "azure_quantum": {"enabled": False, "subscription_id": "", "resource_group": "", "workspace": ""}
            }
        
        # Update with real API key
        config['ibm_quantum']['api_token'] = api_key
        config['enable_real_hardware'] = True
        
        # Write back
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Updated quantum config at: {config_path}")
        print(f"   - API key: {api_key[:8]}...{api_key[-4:]}")
        print(f"   - Real hardware enabled: {config['enable_real_hardware']}")
        
        # Set secure permissions
        config_path.chmod(0o600)
        print(f"   - File permissions: {oct(config_path.stat().st_mode)[-3:]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

def test_ibm_quantum_connection(api_key):
    """Test the IBM Quantum API key connection."""
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        
        print("\n🔗 Testing IBM Quantum connection...")
        service = QiskitRuntimeService(
            channel="ibm_quantum",
            token=api_key
        )
        
        backends = service.backends()
        print(f"✅ Connection successful!")
        print(f"   Available backends: {len(backends)}")
        
        # Show available hardware
        hardware_backends = [b for b in backends if b.status().operational]
        if hardware_backends:
            print("\n   Operational hardware:")
            for backend in hardware_backends[:5]:  # Show first 5
                status = backend.status()
                print(f"   - {backend.name}: {backend.num_qubits} qubits ({status.pending_jobs} jobs queued)")
        
        # Show simulators
        simulator_backends = [b for b in backends if not b.status().operational]
        if simulator_backends:
            print(f"\n   Simulators: {len(simulator_backends)} available")
        
        return True
        
    except ImportError:
        print("❌ qiskit_ibm_runtime not installed")
        print("   Install with: pip install qiskit_ibm_runtime")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def setup_quantum_backend_manager(api_key):
    """Configure quantum backend manager with real API key."""
    try:
        from simp.organs.quantum_intelligence.quantum_backend_manager import (
            get_quantum_backend_manager, QuantumBackendManager
        )
        
        print("\n⚙️ Configuring QuantumBackendManager...")
        manager = get_quantum_backend_manager()
        
        # Configure IBM Quantum
        manager.configure_ibm_quantum(
            api_token=api_key,
            hub="ibm-q",
            group="open",
            project="main"
        )
        
        # Save configuration
        manager.save_config()
        
        # Test backend availability
        backends = manager.get_available_backends()
        print(f"✅ Backend manager configured")
        print(f"   Available backends: {len(backends)}")
        
        for backend in backends[:3]:  # Show first 3
            status = "🔴 REAL HARDWARE" if backend.backend_type == "ibm_quantum" else "🟡 SIMULATOR"
            print(f"   - {backend.backend_id}: {backend.num_qubits} qubits {status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error configuring backend manager: {e}")
        return False

def main():
    """Main setup function."""
    print("=" * 60)
    print("IBM QUANTUM API KEY SETUP")
    print("=" * 60)
    
    # Step 1: Read API key
    print("\n1. Reading API key from secure location...")
    api_key = read_quantum_api_key()
    if not api_key:
        return False
    
    # Step 2: Setup environment variable
    print("\n2. Setting up environment...")
    if not setup_environment_variable(api_key):
        print("⚠️  Environment setup failed, continuing with config file...")
    
    # Step 3: Update config file
    print("\n3. Updating quantum configuration...")
    if not update_quantum_config(api_key):
        return False
    
    # Step 4: Test connection
    print("\n4. Testing IBM Quantum connection...")
    connection_ok = test_ibm_quantum_connection(api_key)
    
    if not connection_ok:
        print("\n⚠️  Connection test failed, but configuration saved.")
        print("   You can still use simulators until connection is fixed.")
    
    # Step 5: Configure backend manager
    print("\n5. Configuring SIMP quantum backend...")
    if not setup_quantum_backend_manager(api_key):
        print("⚠️  Backend manager configuration failed")
    
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    
    print("\n✅ IBM Quantum API key configured securely")
    print("\n📋 Next steps:")
    print("   1. Run: python activate_phase3.py --quantum")
    print("   2. Check for real hardware execution")
    print("   3. Monitor quantum jobs in dashboard")
    
    print("\n🔒 Security notes:")
    print("   - API key stored in ~/.simp/quantum_config.json (chmod 600)")
    print("   - Environment variable set for current session")
    print("   - Never commit config files to version control")
    
    return True

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎯 Ready for quantum hardware execution!")
        print("\nRun: python activate_phase3.py --quantum")
    else:
        print("\n❌ Setup failed. Check errors above.")
        sys.exit(1)