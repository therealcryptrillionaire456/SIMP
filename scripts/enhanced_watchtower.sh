#!/bin/bash
# Enhanced Watchtower - SIMP System Health Monitor
# Comprehensive observability for all SIMP components
# Version: 2.0

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BROKER_URL="http://127.0.0.1:5555"
DASHBOARD_URL="http://127.0.0.1:8050"
PROJECTX_URL="http://127.0.0.1:8771"
TEST_AGENT_URL="http://127.0.0.1:8888"
TIMEOUT=5

# Check if jq is available
if command -v jq &> /dev/null; then
    USE_JQ=true
else
    USE_JQ=false
    echo -e "${YELLOW}WARNING: jq not found. Install with: brew install jq${NC}"
    echo -e "${YELLOW}Falling back to basic checks...${NC}"
fi

# Helper functions
print_header() {
    echo -e "\n${CYAN}=== $1 ===${NC}"
}

print_status() {
    if [ "$1" = "OK" ]; then
        echo -e "  ${GREEN}✓ $2${NC}"
    elif [ "$1" = "WARN" ]; then
        echo -e "  ${YELLOW}⚠ $2${NC}"
    else
        echo -e "  ${RED}✗ $2${NC}"
    fi
}

check_endpoint() {
    local url=$1
    local endpoint=$2
    local description=$3
    
    local response
    response=$(curl -s -m "$TIMEOUT" "${url}${endpoint}" 2>/dev/null || echo "ERROR")
    
    if [ "$response" = "ERROR" ]; then
        echo "UNREACHABLE"
    elif [ -z "$response" ]; then
        echo "EMPTY_RESPONSE"
    else
        echo "$response"
    fi
}

# Main execution
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    SIMP Enhanced Watchtower v2.0${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Timestamp: $(date)"
echo -e "Working directory: $(pwd)"
echo ""

# Initialize status tracking
OVERALL_STATUS="HEALTHY"
ISSUES=()

# 1. BROKER HEALTH CHECKS
print_header "1. BROKER HEALTH (port 5555)"

# Check broker /health
broker_health=$(check_endpoint "$BROKER_URL" "/health" "Broker health")
if [ "$broker_health" = "UNREACHABLE" ]; then
    print_status "ERROR" "Broker not reachable at $BROKER_URL"
    OVERALL_STATUS="UNHEALTHY"
    ISSUES+=("Broker not reachable")
else
    if $USE_JQ; then
        status=$(echo "$broker_health" | jq -r '.status // "unknown"' 2>/dev/null || echo "INVALID_JSON")
        state=$(echo "$broker_health" | jq -r '.state // "unknown"' 2>/dev/null || echo "INVALID_JSON")
        agents_online=$(echo "$broker_health" | jq -r '.agents_online // 0' 2>/dev/null || echo "0")
        
        if [ "$status" = "healthy" ] && [ "$state" = "running" ]; then
            print_status "OK" "Broker healthy (state: $state, agents online: $agents_online)"
        else
            print_status "WARN" "Broker status: $status, state: $state"
            ISSUES+=("Broker status: $status, state: $state")
        fi
    else
        if echo "$broker_health" | grep -q "healthy"; then
            print_status "OK" "Broker responding"
        else
            print_status "WARN" "Broker response doesn't contain 'healthy'"
            ISSUES+=("Broker response doesn't contain 'healthy'")
        fi
    fi
fi

# Check broker /stats
broker_stats=$(check_endpoint "$BROKER_URL" "/stats" "Broker stats")
if [ "$broker_stats" = "UNREACHABLE" ]; then
    print_status "ERROR" "Broker stats endpoint unreachable"
else
    if $USE_JQ; then
        agents_registered=$(echo "$broker_stats" | jq -r '.stats.agents_registered // 0' 2>/dev/null || echo "0")
        intents_received=$(echo "$broker_stats" | jq -r '.stats.intents_received // 0' 2>/dev/null || echo "0")
        intents_completed=$(echo "$broker_stats" | jq -r '.stats.intents_completed // 0' 2>/dev/null || echo "0")
        pending_intents=$(echo "$broker_stats" | jq -r '.stats.pending_intents // 0' 2>/dev/null || echo "0")
        
        print_status "OK" "Stats: $agents_registered agents, $intents_received intents received, $intents_completed completed, $pending_intents pending"
        
        # Check for issues
        if [ "$pending_intents" -gt 10 ]; then
            print_status "WARN" "High pending intents: $pending_intents"
            ISSUES+=("High pending intents: $pending_intents")
        fi
    else
        print_status "OK" "Broker stats endpoint responding"
    fi
fi

# Check broker /agents
broker_agents=$(check_endpoint "$BROKER_URL" "/agents" "Broker agents")
if [ "$broker_agents" = "UNREACHABLE" ]; then
    print_status "ERROR" "Broker agents endpoint unreachable"
else
    if $USE_JQ; then
        agent_count=$(echo "$broker_agents" | jq -r '.count // 0' 2>/dev/null || echo "0")
        
        if [ "$agent_count" -eq 0 ]; then
            print_status "WARN" "No agents registered with broker"
            ISSUES+=("No agents registered with broker")
        else
            print_status "OK" "$agent_count agent(s) registered"
            
            # List agents
            echo "  Registered agents:"
            echo "$broker_agents" | jq -r '.agents | to_entries[] | "    - \(.key): \(.value.status) (\(.value.agent_type))"' 2>/dev/null || echo "    (Unable to parse agent list)"
        fi
    else
        print_status "OK" "Broker agents endpoint responding"
    fi
fi

# 2. DASHBOARD HEALTH CHECKS
print_header "2. DASHBOARD HEALTH (port 8050)"

# Check dashboard /health
dashboard_health=$(check_endpoint "$DASHBOARD_URL" "/health" "Dashboard health")
if [ "$dashboard_health" = "UNREACHABLE" ]; then
    print_status "ERROR" "Dashboard not reachable at $DASHBOARD_URL"
    OVERALL_STATUS="UNHEALTHY"
    ISSUES+=("Dashboard not reachable")
else
    if $USE_JQ; then
        status=$(echo "$dashboard_health" | jq -r '.status // "unknown"' 2>/dev/null || echo "INVALID_JSON")
        broker_reachable=$(echo "$dashboard_health" | jq -r '.broker_reachable // false' 2>/dev/null || echo "false")
        
        if [ "$status" = "healthy" ]; then
            if [ "$broker_reachable" = "true" ]; then
                print_status "OK" "Dashboard healthy and broker reachable"
            else
                print_status "WARN" "Dashboard healthy but broker NOT reachable from dashboard"
                ISSUES+=("Dashboard cannot reach broker")
            fi
        else
            print_status "WARN" "Dashboard status: $status"
            ISSUES+=("Dashboard status: $status")
        fi
    else
        if echo "$dashboard_health" | grep -q "healthy"; then
            print_status "OK" "Dashboard responding"
        else
            print_status "WARN" "Dashboard response doesn't contain 'healthy'"
            ISSUES+=("Dashboard response doesn't contain 'healthy'")
        fi
    fi
fi

# Check dashboard /api/agents (this is where data fetching issues appear)
dashboard_api_agents=$(check_endpoint "$DASHBOARD_URL" "/api/agents" "Dashboard API agents")
if [ "$dashboard_api_agents" = "UNREACHABLE" ]; then
    print_status "ERROR" "Dashboard API agents endpoint unreachable"
    ISSUES+=("Dashboard API agents endpoint unreachable")
else
    if $USE_JQ; then
        # Check for new API response structure: {'agents': [...], 'count': N}
        has_agents=$(echo "$dashboard_api_agents" | jq -r 'has("agents")' 2>/dev/null || echo "false")
        has_count=$(echo "$dashboard_api_agents" | jq -r 'has("count")' 2>/dev/null || echo "false")
        
        if [ "$has_agents" = "true" ] && [ "$has_count" = "true" ]; then
            agent_count=$(echo "$dashboard_api_agents" | jq -r '.count // 0' 2>/dev/null || echo "0")
            agents_array_length=$(echo "$dashboard_api_agents" | jq -r '.agents | length' 2>/dev/null || echo "0")
            
            if [ "$agent_count" -eq "$agents_array_length" ]; then
                print_status "OK" "Dashboard API agents endpoint working ($agent_count agent(s))"
                
                # List agents if count is small
                if [ "$agent_count" -gt 0 ] && [ "$agent_count" -le 5 ]; then
                    echo "  Agents from dashboard:"
                    echo "$dashboard_api_agents" | jq -r '.agents[] | "    - \(.agent_id): \(.status) (\(.agent_type))"' 2>/dev/null || echo "    (Unable to parse agent details)"
                fi
            else
                print_status "WARN" "Dashboard API count mismatch: count=$agent_count, actual agents=$agents_array_length"
                ISSUES+=("Dashboard API count mismatch: count=$agent_count, actual agents=$agents_array_length")
            fi
        else
            # Fallback: check for old structure or other indicators
            status=$(echo "$dashboard_api_agents" | jq -r '.status // "unknown"' 2>/dev/null || echo "INVALID_JSON")
            broker_url_reachable=$(echo "$dashboard_api_agents" | jq -r '.broker_url_reachable // false' 2>/dev/null || echo "false")
            
            if [ "$status" = "success" ] || [ "$broker_url_reachable" = "true" ]; then
                print_status "OK" "Dashboard API agents endpoint working (legacy format)"
            else
                print_status "ERROR" "Dashboard API agents shows invalid format or data fetching issue"
                ISSUES+=("Dashboard API agents invalid format or data fetching issue")
                
                # Provide diagnostic info
                echo "  Diagnostic info:"
                echo "    - Dashboard URL: $DASHBOARD_URL"
                echo "    - Broker URL from dashboard perspective: $BROKER_URL"
                echo "    - Response format: missing 'agents' or 'count' fields"
                echo "    - Check dashboard server logs for data fetching errors"
            fi
        fi
    else
        # Basic check without jq
        if echo "$dashboard_api_agents" | grep -q "\"agents\"" && echo "$dashboard_api_agents" | grep -q "\"count\""; then
            print_status "OK" "Dashboard API agents endpoint responding (has agents and count fields)"
        elif echo "$dashboard_api_agents" | grep -q "success\|reachable"; then
            print_status "OK" "Dashboard API agents endpoint responding (legacy format)"
        else
            print_status "WARN" "Dashboard API agents may have data fetching issue"
            ISSUES+=("Dashboard API agents may have data fetching issue")
        fi
    fi
fi

# 3. AGENT STATUS CHECKS
print_header "3. AGENT STATUS"

# Check test_agent_1 on port 8888
test_agent_health=$(check_endpoint "$TEST_AGENT_URL" "/health" "Test agent health")
if [ "$test_agent_health" = "UNREACHABLE" ]; then
    print_status "ERROR" "Test agent (test_agent_1) not reachable at $TEST_AGENT_URL"
    ISSUES+=("Test agent not reachable")
else
    if $USE_JQ; then
        status=$(echo "$test_agent_health" | jq -r '.status // "unknown"' 2>/dev/null || echo "INVALID_JSON")
        agent_id=$(echo "$test_agent_health" | jq -r '.agent_id // "unknown"' 2>/dev/null || echo "unknown")
        
        if [ "$status" = "healthy" ]; then
            print_status "OK" "Test agent $agent_id healthy"
        else
            print_status "WARN" "Test agent status: $status"
            ISSUES+=("Test agent status: $status")
        fi
    else
        if echo "$test_agent_health" | grep -q "healthy"; then
            print_status "OK" "Test agent responding"
        else
            print_status "WARN" "Test agent response doesn't contain 'healthy'"
            ISSUES+=("Test agent response doesn't contain 'healthy'")
        fi
    fi
fi

# 4. PROJECTX CHECK (if running)
print_header "4. PROJECTX CHECK (port 8771)"

projectx_health=$(check_endpoint "$PROJECTX_URL" "/health" "ProjectX health")
if [ "$projectx_health" = "UNREACHABLE" ]; then
    print_status "INFO" "ProjectX not running on port 8771 (this is normal if not started)"
else
    if $USE_JQ; then
        status=$(echo "$projectx_health" | jq -r '.status // "unknown"' 2>/dev/null || echo "INVALID_JSON")
        
        if [ "$status" = "healthy" ] || [ "$status" = "ok" ]; then
            print_status "OK" "ProjectX healthy"
        else
            print_status "WARN" "ProjectX status: $status"
            ISSUES+=("ProjectX status: $status")
        fi
    else
        print_status "OK" "ProjectX responding"
    fi
fi

# 5. PROCESS CHECK
print_header "5. PROCESS CHECK"

broker_processes=$(ps aux | grep -v grep | grep -c "python.*broker" || true)
dashboard_processes=$(ps aux | grep -v grep | grep -c "python.*dashboard" || true)
test_agent_processes=$(ps aux | grep -v grep | grep -c "test_agent.py.*8888" || true)

if [ "$broker_processes" -eq 0 ]; then
    print_status "ERROR" "Broker process not running"
    OVERALL_STATUS="UNHEALTHY"
    ISSUES+=("Broker process not running")
else
    print_status "OK" "Broker process running ($broker_processes found)"
fi

if [ "$dashboard_processes" -eq 0 ]; then
    print_status "ERROR" "Dashboard process not running"
    OVERALL_STATUS="UNHEALTHY"
    ISSUES+=("Dashboard process not running")
else
    print_status "OK" "Dashboard process running ($dashboard_processes found)"
fi

if [ "$test_agent_processes" -eq 0 ]; then
    print_status "WARN" "Test agent process not running"
    ISSUES+=("Test agent process not running")
else
    print_status "OK" "Test agent process running ($test_agent_processes found)"
fi

# 6. PORT CHECK
print_header "6. PORT AVAILABILITY"

check_port() {
    local port=$1
    local service=$2
    
    if lsof -i ":$port" > /dev/null 2>&1; then
        print_status "OK" "Port $port ($service) is listening"
    else
        print_status "WARN" "Port $port ($service) is NOT listening"
        ISSUES+=("Port $port ($service) not listening")
    fi
}

check_port 5555 "Broker"
check_port 8050 "Dashboard"
check_port 8888 "Test Agent"
check_port 8771 "ProjectX"

# SUMMARY
print_header "SYSTEM SUMMARY"

echo -e "Overall status:"
if [ "$OVERALL_STATUS" = "HEALTHY" ]; then
    echo -e "  ${GREEN}✓ SYSTEM HEALTHY${NC}"
else
    echo -e "  ${RED}✗ SYSTEM UNHEALTHY${NC}"
fi

echo ""
echo -e "Components checked:"
echo "  ✓ Broker health, stats, and agents"
echo "  ✓ Dashboard health and API endpoints"
echo "  ✓ Test agent status"
echo "  ✓ ProjectX (if running)"
echo "  ✓ Process status"
echo "  ✓ Port availability"

if [ ${#ISSUES[@]} -eq 0 ]; then
    echo ""
    echo -e "${GREEN}No issues detected. All systems operational.${NC}"
else
    echo ""
    echo -e "${YELLOW}Issues detected (${#ISSUES[@]}):${NC}"
    for issue in "${ISSUES[@]}"; do
        echo -e "  ${YELLOW}• $issue${NC}"
    done
    
    echo ""
    echo -e "${CYAN}Recommended actions:${NC}"
    
    # Check for specific common issues
    if printf '%s\n' "${ISSUES[@]}" | grep -q "Dashboard cannot reach broker\|Dashboard data fetching issue\|Dashboard API agents invalid format\|Dashboard API count mismatch"; then
        echo "  1. Check dashboard server logs for connection errors"
        echo "  2. Verify dashboard can reach $BROKER_URL internally"
        echo "  3. Check if broker requires API key for dashboard access"
        echo "  4. Restart dashboard: cd $(pwd) && python3.10 dashboard/server.py"
        echo "  5. Verify dashboard API endpoint /api/agents returns {'agents': [...], 'count': N} format"
    fi
    
    if printf '%s\n' "${ISSUES[@]}" | grep -q "Broker not reachable\|Broker process not running"; then
        echo "  1. Start broker: cd $(pwd) && python3.10 -m simp.server.broker"
        echo "  2. Check broker logs for errors"
    fi
    
    if printf '%s\n' "${ISSUES[@]}" | grep -q "No agents registered"; then
        echo "  1. Register test agent: python3.10 test_agent.py --port 8888 --agent-id test_agent_1"
        echo "  2. Check agent registration endpoint"
    fi
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${CYAN}Usage notes:${NC}"
echo "  • Run continuously: watch -n 30 ./scripts/enhanced_watchtower.sh"
echo "  • Run once: ./scripts/enhanced_watchtower.sh"
echo "  • For detailed logs: check dashboard/server.py and broker logs"
echo "  • Install jq for better parsing: brew install jq"
echo -e "${BLUE}========================================${NC}"