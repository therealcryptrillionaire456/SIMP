#!/bin/bash
# SIMP Flock Preflight Checklist

echo "=== SIMP Preflight Checklist ==="
echo "Timestamp: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run check and print result
run_check() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "• $name: "
    OUTPUT=$(eval "$command" 2>/dev/null)
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        if [ -n "$expected" ] && echo "$OUTPUT" | grep -q "$expected"; then
            echo -e "${GREEN}PASS${NC}"
            return 0
        elif [ -z "$expected" ]; then
            echo -e "${GREEN}PASS${NC}"
            return 0
        else
            echo -e "${YELLOW}WARN${NC} (unexpected output)"
            return 1
        fi
    else
        echo -e "${RED}FAIL${NC}"
        return 1
    fi
}

# 1. tmux session
run_check "tmux session" 'tmux has-session -t mothergoose 2>/dev/null && echo "exists"' "exists"

# 2. broker process
run_check "broker process" 'ps aux | grep -v grep | grep -c "python.*broker"' ""

# 3. broker health endpoint
run_check "broker health" 'curl -s -m 3 http://127.0.0.1:5555/health >/dev/null 2>&1 && echo "healthy"' "healthy"

# 4. current directory (check if in SIMP repo)
if pwd | grep -q "kashclaw.*simp"; then
    echo -e "• SIMP repo location: ${GREEN}PASS${NC} ($(pwd))"
else
    echo -e "• SIMP repo location: ${YELLOW}WARN${NC} (not in SIMP repo: $(pwd))"
fi

# 5. test infrastructure
run_check "pytest available" 'python3.10 -m pytest --version 2>&1 | head -1' "pytest"

# 6. python version
PYTHON_VERSION=$(python3.10 --version 2>&1 | awk '{print $2}')
if [[ "$PYTHON_VERSION" == 3.10* ]]; then
    echo -e "• Python version: ${GREEN}PASS${NC} ($PYTHON_VERSION)"
else
    echo -e "• Python version: ${RED}FAIL${NC} (found: $PYTHON_VERSION, need 3.10.x)"
fi

# 7. basic imports (quick check)
run_check "SIMP imports" 'python3.10 -c "import sys; sys.path.insert(0, \".\"); from simp.server.http_server import create_http_server; print(\"imports ok\")" 2>/dev/null' "imports ok"

echo ""
echo "=== Quick Health Check ==="
# Try to get broker status if available
if curl -s -m 3 http://127.0.0.1:5555/health >/dev/null 2>&1; then
    echo -e "${GREEN}Broker is running${NC}"
    # Try to get agent count
    AGENT_COUNT=$(curl -s -m 3 http://127.0.0.1:5555/stats 2>/dev/null | grep -o '"agents_count":[0-9]*' | cut -d: -f2 || echo "0")
    echo "Registered agents: $AGENT_COUNT"
else
    echo -e "${YELLOW}Broker not running${NC}"
    echo "Start with: ./bin/start_broker.sh"
fi

echo ""
echo "=== Recommendations ==="
if curl -s -m 3 http://127.0.0.1:5555/health >/dev/null 2>&1; then
    echo "1. System appears healthy"
    echo "2. Proceed with Mother Goose mission board"
else
    echo "1. Start broker: ./bin/start_broker.sh"
    echo "2. Wait 5 seconds for startup"
    echo "3. Re-run preflight: ./scripts/preflight_check.sh"
fi

echo ""
echo "=== Pane Verification ==="
echo "Verify each pane is in correct directory:"
echo "• SIMP Goose pane: Should be in SIMP repo"
echo "• Stray Goose pane: Should be in ~/stray_goose"
echo "• Watchtower pane: Can run ./scripts/watchtower.sh"