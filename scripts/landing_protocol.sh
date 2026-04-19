#!/bin/bash
# SIMP Flock Landing Protocol
# Run at end of each session to capture state and plan next session

echo "=== SIMP Landing Protocol ==="
echo "Timestamp: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}1. Final System Health Check:${NC}"
echo "------------------------------"
# Run watchtower but capture output
WT_OUTPUT=$(./scripts/watchtower.sh 2>/dev/null)
echo "$WT_OUTPUT" | tail -20

echo ""
echo -e "${BLUE}2. Git Status Assessment:${NC}"
echo "---------------------------"
echo "Current branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
echo ""
echo "Uncommitted changes:"
git status --short 2>/dev/null || echo "  (not in git repo or git not available)"
echo ""
echo "Recent commits (last 5):"
git log --oneline -5 2>/dev/null || echo "  (git log not available)"

echo ""
echo -e "${BLUE}3. Process Inventory:${NC}"
echo "----------------------"
BROKER_PROCS=$(ps aux | grep -v grep | grep -c "python.*broker")
DASHBOARD_PROCS=$(ps aux | grep -v grep | grep -c "python.*dashboard")
ALL_SIMP_PROCS=$(ps aux | grep -v grep | grep python | grep -c simp)

echo "Broker processes: $BROKER_PROCS"
echo "Dashboard processes: $DASHBOARD_PROCS"
echo "Total SIMP-related Python processes: $ALL_SIMP_PROCS"

if [ "$BROKER_PROCS" -gt 1 ]; then
    echo -e "  ${YELLOW}Note: Multiple broker processes detected${NC}"
fi

echo ""
echo -e "${BLUE}4. Resource Status:${NC}"
echo "---------------------"
# Disk space in current directory
DISK_INFO=$(df -h . 2>/dev/null | awk 'NR==2 {print "Usage: " $5 ", Available: " $4}')
if [ -n "$DISK_INFO" ]; then
    echo "Disk: $DISK_INFO"
else
    echo "Disk: (check unavailable)"
fi

# Check for large log files
LOG_DIR="$HOME/bullbear/logs"
if [ -d "$LOG_DIR" ]; then
    LOG_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
    echo "Log directory size: $LOG_SIZE"
fi

echo ""
echo -e "${BLUE}5. Today's Work Summary (Manual Input Required):${NC}"
echo "------------------------------------------------------"
echo "Please fill in based on goose reports:"
echo ""
echo "SIMP Goose completed tasks:"
echo "1. [Task ID]: [Description]"
echo "   - Files changed:"
echo "   - Tests run/results:"
echo ""
echo "Stray Goose analyses:"
echo "1. [Analysis topic]: [Key findings]"
echo "   - Recommendations:"
echo "   - Artifacts created:"
echo ""
echo "Watchtower monitoring:"
echo "- Alerts handled:"
echo "- Issues identified:"
echo "- System uptime:"

echo ""
echo -e "${BLUE}6. Blockers & Issues:${NC}"
echo "-----------------------"
echo "Unresolved blockers:"
echo "1. [Blocker]: [Impact]"
echo ""
echo "New issues discovered:"
echo "1. [Issue]: [Severity: High/Medium/Low]"

echo ""
echo -e "${BLUE}7. Next Session Planning:${NC}"
echo "------------------------------"
echo "Recommended first task for next session:"
echo "Task: [Task ID or description]"
echo "Owner: [SIMP Goose/Stray Goose/Watchtower]"
echo "Priority: P[1-4] (1=revenue, 2=analytical, 3=showcase, 4=infrastructure)"
echo "Rationale: [Why this task first]"
echo ""
echo "Preparation needed before next session:"
echo "1. [Action item]"
echo "2. [Action item]"

echo ""
echo -e "${BLUE}8. System Readiness Assessment:${NC}"
echo "-------------------------------------"
# Check if broker is healthy
if curl -s -m 3 http://127.0.0.1:5555/health >/dev/null 2>&1; then
    echo -e "Broker status: ${GREEN}HEALTHY${NC}"
    READINESS="READY"
else
    echo -e "Broker status: ${RED}NOT RESPONDING${NC}"
    READINESS="NOT READY"
fi

# Check dashboard
DASH_CHECK=$(curl -s -m 3 http://127.0.0.1:8050/ 2>/dev/null | grep -c "SIMP" || echo "0")
if [ "$DASH_CHECK" -gt 0 ]; then
    echo -e "Dashboard: ${GREEN}OK${NC}"
else
    echo -e "Dashboard: ${YELLOW}CHECK NEEDED${NC}"
    READINESS="NEEDS CHECK"
fi

echo ""
echo -e "${BLUE}=== Landing Protocol Complete ===${NC}"
echo ""
echo "Overall system readiness: $READINESS"
echo ""
echo "Next steps:"
echo "1. Save this report to logs/landing_report_$(date +%Y-%m-%d).md"
echo "2. Choose shutdown option:"
echo "   A) Continue later: Ctrl-b d (detach tmux)"
echo "   B) Graceful shutdown: Stop broker/dashboard, then detach"
echo "   C) Emergency stop: Only if system unstable"
echo ""
echo "To re-attach later: tmux attach -t mothergoose"
echo "To start fresh tomorrow: ./scripts/start_mother_goose_tmux.sh"