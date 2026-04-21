# IBM Quantum Token Setup Guide

## Current Status
✅ **Quantum routing is working** with local simulator  
⚠️ **IBM hardware access blocked** by placeholder token  
🎯 **Ready for real IBM Quantum token**

## How to Get IBM Quantum Token

### Option 1: IBM Quantum Platform (Free Tier)
1. **Sign up** at [quantum.ibm.com](https://quantum.ibm.com)
2. **Create account** with IBMid
3. **Navigate to** "Account" → "API token"
4. **Generate new token** or copy existing one
5. **Free tier includes:**
   - 10 minutes/month on real quantum hardware
   - Unlimited simulator access
   - Access to 127+ qubit processors

### Option 2: IBM Quantum Credits Program
1. **Apply** for research credits at [IBM Quantum Credits](https://quantum-computing.ibm.com/services/programs)
2. **Academic/research** projects get additional credits
3. **Commercial** projects can purchase credits

### Option 3: IBM Quantum Network (Enterprise)
1. **Join** IBM Quantum Network for enterprise access
2. **Get** dedicated hardware time
3. **Access** premium features and support

## Setup Instructions

### Method A: Environment Variable (Recommended)
```bash
# Add to your shell profile (~/.zshrc, ~/.bashrc, etc.)
export IBM_QUANTUM_TOKEN="your_actual_token_here"
export IBM_QUANTUM_HUB="ibm-q"
export IBM_QUANTUM_GROUP="open" 
export IBM_QUANTUM_PROJECT="main"

# Reload shell or source profile
source ~/.zshrc
```

### Method B: Update Config File
```bash
# Edit the quantum config file
nano ~/.simp/quantum_config.json

# Update the ibm_quantum section:
{
  "ibm_quantum": {
    "enabled": true,
    "api_token": "your_actual_token_here",
    "hub": "ibm-q",
    "group": "open",
    "project": "main"
  }
}
```

### Method C: Programmatic Setup
```python
from simp.organs.quantum_intelligence.quantum_backend_manager import (
    get_quantum_backend_manager, QuantumBackendManager
)

# Get manager
manager = get_quantum_backend_manager()

# Configure IBM Quantum with real token
manager.configure_ibm_quantum(
    api_token="your_actual_token_here",
    hub="ibm-q",
    group="open",
    project="main"
)

# Save configuration
manager.save_config()
```

## Verification Steps

### 1. Test Token Validity
```python
from qiskit_ibm_runtime import QiskitRuntimeService

try:
    service = QiskitRuntimeService(
        channel="ibm_quantum",
        token="your_token_here"
    )
    backends = service.backends()
    print(f"✅ Token valid. Available backends: {len(backends)}")
    for backend in backends[:3]:  # Show first 3
        print(f"  - {backend.name} ({backend.num_qubits} qubits)")
except Exception as e:
    print(f"❌ Token invalid: {e}")
```

### 2. Update SIMP Configuration
```bash
# Run the quantum activation script with real token
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp

# Set environment variable
export IBM_QUANTUM_TOKEN="your_token_here"

# Activate quantum phase
python activate_phase3.py --quantum --verbose
```

### 3. Verify Hardware Access
```python
# Check if real hardware is available
from simp.organs.quantum_intelligence.quantum_backend_manager import (
    get_quantum_backend_manager
)

manager = get_quantum_backend_manager()
backends = manager.get_available_backends()

print("Available backends:")
for backend in backends:
    status = "✅ REAL HARDWARE" if backend.backend_type == "ibm_quantum" else "simulator"
    print(f"  - {backend.backend_id}: {backend.num_qubits} qubits ({status})")
```

## Expected Results After Setup

### With Valid Token:
```
✅ Quantum advantage: 1.000 (real hardware)
✅ Broker agents: quantumarb_primary, quantum_intelligence_prime
✅ Payment channels: seq=4+ with real quantum results
✅ L5 consensus: 3 votes with hardware verification
✅ Portfolio optimization: Real quantum-enhanced results
```

### Current (Placeholder Token):
```
⚠️ Quantum advantage: 1.000 (simulator only)
⚠️ Using: local_simulator (fallback)
ℹ️  Set IBM_QUANTUM_TOKEN for real hardware access
```

## Troubleshooting

### Common Issues:

1. **Invalid token error**
   ```bash
   # Regenerate token at quantum.ibm.com
   # Ensure no extra spaces in token
   echo -n "your_token" | pbcopy  # Copy without newline
   ```

2. **Token expired**
   ```bash
   # Tokens expire after 90 days
   # Generate new token at quantum.ibm.com
   ```

3. **Rate limiting**
   ```bash
   # Free tier: 10 minutes/month
   # Check usage: quantum.ibm.com → Account → Usage
   ```

4. **Backend not available**
   ```bash
   # Some backends require reservation
   # Check availability: quantum.ibm.com → Systems
   ```

### Debug Commands:
```bash
# Check token in environment
echo $IBM_QUANTUM_TOKEN | wc -c  # Should be ~50 characters

# Test direct API access
curl -X GET "https://auth.quantum-computing.ibm.com/api/users/me" \
  -H "Authorization: Bearer $IBM_QUANTUM_TOKEN"

# Check qiskit installation
python -c "import qiskit_ibm_runtime; print(qiskit_ibm_runtime.__version__)"
```

## Security Notes

### 🔒 Token Security:
- **Never commit** tokens to version control
- **Use environment variables** or secure config stores
- **Rotate tokens** every 90 days
- **Restrict token permissions** to minimum required

### 🛡️ Safe Practices:
```bash
# Add to .gitignore
echo ".simp/quantum_config.json" >> .gitignore
echo "*.env" >> .gitignore

# Set file permissions
chmod 600 ~/.simp/quantum_config.json
```

## Next Steps After Token Setup

1. **Run full verification:**
   ```bash
   python activate_phase3.py --quantum --verify-all
   ```

2. **Test real hardware:**
   ```bash
   python -c "from activate_phase3 import main; main(['--quantum', '--backend', 'ibm_brisbane'])"
   ```

3. **Update dashboard:**
   - Quantum hardware status panel
   - Real-time job monitoring
   - Cost tracking and alerts

4. **Integrate with mesh:**
   - Quantum results over mesh network
   - Distributed quantum computation
   - Mesh-routed quantum intents

## Support Resources

- **IBM Quantum Documentation:** [docs.quantum.ibm.com](https://docs.quantum.ibm.com)
- **Qiskit Runtime Docs:** [qiskit.org/documentation/partners/qiskit_ibm_runtime](https://qiskit.org/documentation/partners/qiskit_ibm_runtime)
- **Community Support:** [quantum-computing.ibm.com/community](https://quantum-computing.ibm.com/community)
- **GitHub Issues:** [github.com/Qiskit/qiskit-ibm-runtime](https://github.com/Qiskit/qiskit-ibm-runtime)

---

**Once you have your IBM Quantum token, the system will automatically switch from simulator to real quantum hardware, enabling true quantum advantage in your predictions and optimizations.**