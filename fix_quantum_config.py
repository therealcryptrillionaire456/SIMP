#!/usr/bin/env python3
"""
Fix quantum configuration with correct instance format.
"""

import json
import os
from pathlib import Path

def fix_config():
    config_path = Path.home() / ".simp" / "quantum_config.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Update instance format
        if "ibm_quantum" in config:
            # Remove old hub/group/project format
            if "hub" in config["ibm_quantum"]:
                del config["ibm_quantum"]["hub"]
            if "group" in config["ibm_quantum"]:
                del config["ibm_quantum"]["group"]
            if "project" in config["ibm_quantum"]:
                del config["ibm_quantum"]["project"]
            
            # Add instance field
            config["ibm_quantum"]["instance"] = "open-instance"
        
        # Write back
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Fixed config at {config_path}")
        print("\nUpdated config:")
        print(json.dumps(config, indent=2))
        return True
        
    except Exception as e:
        print(f"❌ Error fixing config: {e}")
        return False

def test_fixed_config():
    """Test the fixed configuration."""
    print("\n🧪 Testing fixed configuration...")
    
    test_code = '''
import os
import json
from pathlib import Path

config_path = Path.home() / ".simp" / "quantum_config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

print(f"Config loaded: {config_path}")
print(f"IBM Quantum enabled: {config.get('ibm_quantum', {}).get('enabled', False)}")
print(f"Instance: {config.get('ibm_quantum', {}).get('instance', 'NOT SET')}")

# Test connection
try:
    from qiskit_ibm_runtime import QiskitRuntimeService
    
    token = config["ibm_quantum"]["api_token"]
    instance = config["ibm_quantum"].get("instance")
    
    if instance:
        service = QiskitRuntimeService(
            channel="ibm_quantum_platform",
            token=token,
            instance=instance
        )
        print(f"✅ Connected with instance: {instance}")
    else:
        service = QiskitRuntimeService(
            channel="ibm_quantum_platform",
            token=token
        )
        print("✅ Connected without instance")
    
    backends = service.backends()
    print(f"✅ Found {len(backends)} backends")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
'''
    
    try:
        import subprocess
        result = subprocess.run(
            ["python3.10", "-c", test_code],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(f"⚠️  Stderr: {result.stderr}")
        
        return "✅ Found" in result.stdout
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("QUANTUM CONFIG FIX")
    print("=" * 60)
    
    if fix_config():
        if test_fixed_config():
            print("\n🎉 CONFIG FIXED AND TESTED SUCCESSFULLY!")
        else:
            print("\n⚠️  Config fixed but test failed")
    else:
        print("\n❌ Config fix failed")
    
    print("\n" + "=" * 60)