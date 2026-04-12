#!/bin/bash
echo "Verifying enhanced watchtower script updates..."
echo "=============================================="
echo ""

# Requirement 1: Handle new API response format {'agents': {...}, 'count': N}
echo "1. Checking if script handles new API format..."
if grep -q "Check for new API response structure: {'agents': \[...\], 'count': N}" scripts/enhanced_watchtower.sh; then
    echo "   ✓ Script has comment about new API structure"
else
    echo "   ✗ Missing comment about new API structure"
fi

if grep -q 'has_agents=\$(echo "\$dashboard_api_agents" | jq -r '"'"'has("agents")'"'" scripts/enhanced_watchtower.sh; then
    echo "   ✓ Script checks for 'agents' field"
else
    echo "   ✗ Missing check for 'agents' field"
fi

if grep -q 'has_count=\$(echo "\$dashboard_api_agents" | jq -r '"'"'has("count")'"'" scripts/enhanced_watchtower.sh; then
    echo "   ✓ Script checks for 'count' field"
else
    echo "   ✗ Missing check for 'count' field"
fi

echo ""

# Requirement 2: Check if /api/agents returns valid JSON with 'agents' field
echo "2. Checking if script validates JSON with 'agents' field..."
if grep -q 'if \[ "\$has_agents" = "true" \] && \[ "\$has_count" = "true" \]; then' scripts/enhanced_watchtower.sh; then
    echo "   ✓ Script validates both 'agents' and 'count' fields exist"
else
    echo "   ✗ Missing validation for fields existence"
fi

echo ""

# Requirement 3: Verify 'count' field matches number of agents
echo "3. Checking if script verifies count matches number of agents..."
if grep -q 'agent_count=\$(echo "\$dashboard_api_agents" | jq -r '"'"'.count // 0'"'" scripts/enhanced_watchtower.sh; then
    echo "   ✓ Script extracts agent count"
else
    echo "   ✗ Missing agent count extraction"
fi

if grep -q 'agents_array_length=\$(echo "\$dashboard_api_agents" | jq -r '"'"'.agents | length'"'" scripts/enhanced_watchtower.sh; then
    echo "   ✓ Script gets agents array length"
else
    echo "   ✗ Missing agents array length check"
fi

if grep -q 'if \[ "\$agent_count" -eq "\$agents_array_length" \]; then' scripts/enhanced_watchtower.sh; then
    echo "   ✓ Script compares count with array length"
else
    echo "   ✗ Missing count comparison"
fi

echo ""

# Requirement 4: Update status messages to reflect new structure
echo "4. Checking if status messages reflect new structure..."
if grep -q 'print_status "OK" "Dashboard API agents endpoint working (\$agent_count agent(s))"' scripts/enhanced_watchtower.sh; then
    echo "   ✓ Success message includes agent count"
else
    echo "   ✗ Success message doesn't include agent count"
fi

if grep -q 'print_status "WARN" "Dashboard API count mismatch: count=\$agent_count, actual agents=\$agents_array_length"' scripts/enhanced_watchtower.sh; then
    echo "   ✓ Warning message for count mismatch"
else
    echo "   ✗ Missing warning for count mismatch"
fi

if grep -q 'print_status "ERROR" "Dashboard API agents shows invalid format or data fetching issue"' scripts/enhanced_watchtower.sh; then
    echo "   ✓ Error message for invalid format"
else
    echo "   ✗ Missing error message for invalid format"
fi

echo ""

# Requirement 5: Ensure all dashboard health checks pass correctly
echo "5. Checking if dashboard health checks work correctly..."
echo "   Running script test (dashboard section only)..."
echo ""

# Run the script and capture dashboard section
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
output=$(bash scripts/enhanced_watchtower.sh 2>&1 | grep -A 10 "DASHBOARD HEALTH")

echo "$output" | grep -q "Dashboard API agents endpoint working" && echo "   ✓ Dashboard API check passes" || echo "   ✗ Dashboard API check fails"
echo "$output" | grep -q "agent(s)" && echo "   ✓ Shows agent count" || echo "   ✗ Doesn't show agent count"

echo ""
echo "=============================================="
echo "Verification complete!"