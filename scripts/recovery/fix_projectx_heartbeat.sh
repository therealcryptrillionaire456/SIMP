#!/bin/bash
# Fix for ProjectX native heartbeat 404 error

echo "=== Fixing ProjectX Native Heartbeat 404 ==="

# 1. Check if ProjectX is running
echo -e "\n1. Checking if ProjectX is running..."
if ps aux | grep -q "[p]rojectx_guard_server"; then
    echo "   ✓ ProjectX is running"
    PID=$(ps aux | grep "[p]rojectx_guard_server" | awk '{print $2}' | head -1)
    echo "   PID: $PID"
else
    echo "   ✗ ProjectX is NOT running"
fi

# 2. Check if ProjectX is registered with broker
echo -e "\n2. Checking if projectx_native is registered with broker..."
curl -s "http://127.0.0.1:5555/agents" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    agents = data.get('agents', [])
    found = any(a.get('agent_id') == 'projectx_native' for a in agents)
    if found:
        print('   ✓ projectx_native is registered')
    else:
        print('   ✗ projectx_native is NOT registered')
except:
    print('   ? Could not check broker status')
"

# 3. Update startup script with --register flag
echo -e "\n3. Updating startup script..."
STARTUP_SCRIPT="start_missing_components.sh"
if [ -f "$STARTUP_SCRIPT" ]; then
    # Check current command
    echo "   Current command in $STARTUP_SCRIPT:"
    grep -A 2 "projectx_guard_server.py" "$STARTUP_SCRIPT"
    
    # Create backup
    cp "$STARTUP_SCRIPT" "${STARTUP_SCRIPT}.backup"
    
    # Update the command (simplified - would need proper sed command)
    echo -e "\n   To fix, update the ProjectX startup command to include:"
    echo "   --register --simp-url http://127.0.0.1:5555 --simp-api-key \$SIMP_API_KEY"
else
    echo "   Startup script not found: $STARTUP_SCRIPT"
fi

# 4. Alternative: Start ProjectX directly with registration
echo -e "\n4. Starting ProjectX with registration..."
cd "/Users/kaseymarcelle/ProjectX" 2>/dev/null
if [ $? -eq 0 ]; then
    # Kill existing ProjectX if running
    pkill -f "projectx_guard_server" 2>/dev/null
    sleep 2
    
    # Start with registration
    echo "   Starting ProjectX with --register flag..."
    nohup python3.10 projectx_guard_server.py \
        --register \
        --simp-url "http://127.0.0.1:5555" \
        --simp-api-key "$SIMP_API_KEY" \
        > /tmp/projectx_fixed.log 2>&1 &
    
    echo "   ProjectX started with PID: $!"
    echo "   Logs: /tmp/projectx_fixed.log"
    
    # Wait and check registration
    sleep 5
    echo -e "\n5. Checking registration status..."
    curl -s "http://127.0.0.1:5555/agents/projectx_native" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('status') == 'success':
        print('   ✓ ProjectX registered successfully!')
        print(f'   Agent ID: {data.get(\"agent_id\")}')
        print(f'   Status: {data.get(\"status\")}')
    else:
        print(f'   ✗ Registration failed: {data}')
except Exception as e:
    print(f'   ? Error checking: {e}')
"
else
    echo "   ✗ Could not cd to ProjectX directory"
fi

echo -e "\n=== Fix Complete ==="
