#!/bin/bash
# SIMP Flock Maintenance Check
# Run every 30-60 minutes during flight operations

echo "=== SIMP Maintenance Check ==="
echo "Timestamp: $(date)"
echo "Check interval: Every 30-60 minutes"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check status
check_status() {
    local name="$1"
    local command="$2"
    local good_pattern="$3"
    
    echo -n "• $name: "
    OUTPUT=$(eval "$command" 2>/dev/null)
    
    if [ -n "$good_pattern" ]; then
        if echo "$OUTPUT" | grep -q "$good_pattern"; then
            echo -e "${GREEN}OK${NC}"
            return 0
        else
            echo -e "${YELLOW}CHECK${NC}"
            return 1
        fi
    else
        if [ -n "$OUTPUT" ]; then
            echo -e "${GREEN}OK${NC}"
            return 0
        else
            echo -e "${YELLOW}CHECK${NC}"
            return 1
        fi
    fi
}

echo "1. System Health Summary:"
echo "-----------------------"

# Quick health check
BROKER_HEALTH=$(curl -s -m 3 http://127.0.0.1:5555/health 2>/dev/null)
if [ -n "$BROKER_HEALTH" ]; then
    echo -e "• Broker: ${GREEN}HEALTHY${NC}"
    # Extract status if possible
    STATUS=$(echo "$BROKER_HEALTH" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    echo "  Status: $STATUS"
else
    echo -e "• Broker: ${RED}UNHEALTHY${NC}"
fi

# Agent count
AGENT_COUNT=$(curl -s -m 3 http://127.0.0.1:5555/stats 2>/dev/null | grep -o '"agents_count":[0-9]*' | cut -d: -f2 || echo "0")
echo "  Registered agents: $AGENT_COUNT"

# Dashboard check
DASHBOARD_CHECK=$(curl -s -m 3 http://127.0.0.1:8050/ 2>/dev/null | grep -c "SIMP" || echo "0")
if [ "$DASHBOARD_CHECK" -gt 0 ]; then
    echo -e "• Dashboard: ${GREEN}OK${NC}"
else
    echo -e "• Dashboard: ${YELLOW}CHECK${NC}"
fi

echo ""
echo "2. Process Status:"
echo "-----------------"

# Count processes
BROKER_PROCS=$(ps aux | grep -v grep | grep -c "python.*broker")
DASHBOARD_PROCS=$(ps aux | grep -v grep | grep -c "python.*dashboard")
PYTHON_SIMP_PROCS=$(ps aux | grep -v grep | grep python | grep -c simp)

echo "Broker processes: $BROKER_PROCS"
echo "Dashboard processes: $DASHBOARD_PROCS"
echo "Total SIMP Python processes: $PYTHON_SIMP_PROCS"

# Check for duplicates
if [ "$BROKER_PROCS" -gt 1 ]; then
    echo -e "  ${YELLOW}WARNING: Multiple broker processes${NC}"
fi

echo ""
echo "3. Resource Check:"
echo "-----------------"

# Check disk space
DISK_SPACE=$(df -h . | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_SPACE" -lt 80 ]; then
    echo -e "• Disk space: ${GREEN}OK${NC} ($DISK_SPACE% used)"
elif [ "$DISK_SPACE" -lt 95 ]; then
    echo -e "• Disk space: ${YELLOW}WATCH${NC} ($DISK_SPACE% used)"
else
    echo -e "• Disk space: ${RED}CRITICAL${NC} ($DISK_SPACE% used)"
fi

# Check memory (simplified)
MEM_FREE=$(vm_stat 2>/dev/null | grep "Pages free" | awk '{print $3}' | tr -d '.')
if [ -n "$MEM_FREE" ] && [ "$MEM_FREE" -gt 1000 ]; then
    echo -e "• Memory: ${GREEN}OK${NC}"
else
    echo -e "• Memory: ${YELLOW}CHECK${NC}"
fi

echo ""
echo "4. Log Check (last 5 minutes):"
echo "------------------------------"

# Check for recent errors in broker log
LOG_FILE="$HOME/bullbear/logs/simp_broker.log"
if [ -f "$LOG_FILE" ]; then
    RECENT_ERRORS=$(grep -i "error\|exception\|traceback" "$LOG_FILE" | tail -5)
    if [ -n "$RECENT_ERRORS" ]; then
        echo -e "${YELLOW}Recent log errors:${NC}"
        echo "$RECENT_ERRORS" | while read line; do
            echo "  - $line"
        done
    else
        echo -e "${GREEN}No recent errors in logs${NC}"
    fi
else
    echo "No broker log file found at $LOG_FILE"
fi

echo ""
echo "=== Maintenance Actions ==="
echo ""
echo "If system unhealthy:"
echo "1. Check logs: tail -100 $LOG_FILE"
echo "2. Restart broker: ./bin/restart_all.sh"
echo "3. Verify: ./scripts/watchtower.sh"
echo ""
echo "If processes duplicated:"
echo "1. Kill duplicates: pkill -f 'python.*broker' (then restart)"
echo ""
echo "If resources low:"
echo "1. Clean temp files: rm -rf data/tmp/*"
echo "2. Clear Python cache: find . -name '__pycache__' -type d -exec rm -rf {} +"
echo ""
echo "=== Next Steps ==="
echo "1. Check goose status (ask each goose)"
echo "2. Verify scope containment"
echo "3. Review task progress"
echo "4. Schedule next check in 30-60 minutes"
echo ""
echo "Overall status:"
if [ -n "$BROKER_HEALTH" ] && [ "$BROKER_PROCS" -eq 1 ] && [ "$DASHBOARD_CHECK" -gt 0 ]; then
    echo -e "${GREEN}GREEN - System stable${NC}"
elif [ -n "$BROKER_HEALTH" ]; then
    echo -e "${YELLOW}YELLOW - Monitor${NC}"
else
    echo -e "${RED}RED - Intervention needed${NC}"
fi