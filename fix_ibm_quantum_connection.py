#!/usr/bin/env python3
"""
Fix IBM Quantum connection issues.
"""

import os
import sys
from pathlib import Path

def fix_qiskit_channel_issue():
    """Fix the channel parameter issue with newer qiskit_ibm_runtime."""
    print("Fixing IBM Quantum channel parameter issue...")
    
    # Check qiskit_ibm_runtime version
    try:
        import qiskit_ibm_runtime
        print(f"qiskit_ibm_runtime version: {qiskit_ibm_runtime.__version__}")
        
        # For newer versions, channel should be 'ibm_quantum' or 'ibm_cloud'
        # Let's test both
        test_channel = "ibm_quantum"
        
        # Update quantum_backend_manager.py
        backend_manager_path = Path("simp/organs/quantum_intelligence/quantum_backend_manager.py")
        
        if backend_manager_path.exists():
            with open(backend_manager_path, 'r') as f:
                content = f.read()
            
            # Fix the channel parameter
            if "channel=\"ibm_quantum\"" in content:
                print("Channel parameter already correct")
            else:
                # Look for QiskitRuntimeService initialization
                import re
                pattern = r'QiskitRuntimeService\([^)]+channel\s*=\s*["\'][^"\']+["\']'
                new_content = re.sub(
                    pattern,
                    'QiskitRuntimeService(channel="ibm_quantum"',
                    content
                )
                
                if new_content != content:
                    with open(backend_manager_path, 'w') as f:
                        f.write(new_content)
                    print("✅ Fixed channel parameter in quantum_backend_manager.py")
                else:
                    print("Could not find channel parameter to fix")
        
        return True
        
    except ImportError:
        print("qiskit_ibm_runtime not installed")
        return False
    except Exception as e:
        print(f"Error fixing channel issue: {e}")
        return False

def fix_backend_info_attribute():
    """Fix the num_qubits attribute issue."""
    print("\nFixing QuantumBackendInfo attribute issue...")
    
    backend_manager_path = Path("simp/organs/quantum_intelligence/quantum_backend_manager.py")
    
    if not backend_manager_path.exists():
        print("❌ quantum_backend_manager.py not found")
        return False
    
    with open(backend_manager_path, 'r') as f:
        content = f.read()
    
    # Check if num_qubits attribute exists in QuantumBackendInfo
    if "num_qubits: int" in content:
        print("✅ num_qubits attribute already defined")
        return True
    
    # Find the QuantumBackendInfo dataclass
    lines = content.split('\n')
    fixed_lines = []
    in_dataclass = False
    fixed = False
    
    for i, line in enumerate(lines):
        fixed_lines.append(line)
        
        if "@dataclass" in line and i+1 < len(lines) and "QuantumBackendInfo" in lines[i+1]:
            in_dataclass = True
        
        if in_dataclass and "backend_id: str" in line and not fixed:
            # Add num_qubits after backend_id
            fixed_lines.append("    num_qubits: int = 0")
            fixed = True
            print("✅ Added num_qubits attribute to QuantumBackendInfo")
    
    if fixed:
        with open(backend_manager_path, 'w') as f:
            f.write('\n'.join(fixed_lines))
        return True
    else:
        print("❌ Could not find QuantumBackendInfo dataclass")
        return False

def test_fixed_connection():
    """Test the fixed connection."""
    print("\nTesting fixed IBM Quantum connection...")
    
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        
        # Get API key from environment
        api_key = os.environ.get('IBM_QUANTUM_TOKEN')
        if not api_key:
            print("❌ IBM_QUANTUM_TOKEN not set")
            return False
        
        print(f"Testing with API key: {api_key[:8]}...{api_key[-4:]}")
        
        # Try with correct channel parameter
        service = QiskitRuntimeService(
            channel="ibm_quantum",
            token=api_key
        )
        
        backends = service.backends()
        print(f"✅ Connection successful!")
        print(f"   Available backends: {len(backends)}")
        
        # Show available backends
        for backend in backends[:5]:
            try:
                num_qubits = backend.num_qubits
                status = backend.status()
                print(f"   - {backend.name}: {num_qubits} qubits ({status.pending_jobs} jobs queued)")
            except:
                print(f"   - {backend.name}: (qubit count unknown)")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def update_activate_script():
    """Update activate_phase3.py to handle timeouts better."""
    print("\nUpdating activate_phase3.py timeout handling...")
    
    activate_path = Path("activate_phase3.py")
    
    if not activate_path.exists():
        print("❌ activate_phase3.py not found")
        return False
    
    with open(activate_path, 'r') as f:
        content = f.read()
    
    # Check for timeout handling
    if "timeout=" in content:
        print("✅ Timeout handling already present")
        return True
    
    # Look for subprocess.run calls
    import re
    
    # Add timeout to subprocess.run calls
    pattern = r'subprocess\.run\(\[.*?\](?=\))'
    
    def add_timeout(match):
        call = match.group(0)
        if 'timeout=' not in call:
            return call[:-1] + ', timeout=60)'
        return call
    
    new_content = re.sub(pattern, add_timeout, content, flags=re.DOTALL)
    
    if new_content != content:
        with open(activate_path, 'w') as f:
            f.write(new_content)
        print("✅ Added timeout handling to subprocess calls")
        return True
    else:
        print("⚠️  Could not find subprocess.run calls to update")
        return False

def main():
    """Main fix function."""
    print("=" * 60)
    print("IBM QUANTUM CONNECTION FIXES")
    print("=" * 60)
    
    fixes = [
        ("Fix channel parameter", fix_qiskit_channel_issue),
        ("Fix num_qubits attribute", fix_backend_info_attribute),
        ("Update timeout handling", update_activate_script),
        ("Test fixed connection", test_fixed_connection),
    ]
    
    all_fixed = True
    for fix_name, fix_func in fixes:
        print(f"\n{fix_name}...")
        if fix_func():
            print(f"✅ {fix_name} successful")
        else:
            print(f"⚠️  {fix_name} had issues")
            all_fixed = False
    
    print("\n" + "=" * 60)
    if all_fixed:
        print("✅ ALL FIXES APPLIED SUCCESSFULLY")
        print("\nNext: Run python activate_phase3.py --quantum")
    else:
        print("⚠️  SOME FIXES HAD ISSUES")
        print("\nCheck the specific issues above.")
    
    return all_fixed

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎯 Ready to test quantum activation!")
    else:
        print("\n❌ Fixes incomplete")
        sys.exit(1)