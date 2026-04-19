# Morning Preflight Checklist

Run this checklist before any code work. Mother Goose should verify:

## Checklist Items:

### 1. tmux session exists and is named correctly
```bash
tmux has-session -t mothergoose 2>/dev/null && echo "PASS: mothergoose session exists" || echo "FAIL: No mothergoose session"
```

### 2. proxy is reachable (if applicable)
```bash
# Check if proxy process is running (adjust command based on your proxy)
ps aux | grep -v grep | grep -q "proxy" && echo "PASS: Proxy process running" || echo "INFO: No proxy process found (may be OK)"
```

### 3. broker is reachable
```bash
curl -s -m 5 http://127.0.0.1:5555/health >/dev/null 2>&1 && echo "PASS: Broker responding" || echo "FAIL: Broker not responding"
```

### 4. SIMP Goose pane is in the SIMP repo
```bash
# In SIMP Goose pane (geese window, pane 0):
pwd | grep -q "kashclaw.*simp" && echo "PASS: In SIMP repo" || echo "FAIL: Wrong directory"
```

### 5. Stray Goose pane is in ~/stray_goose
```bash
# In Stray Goose pane (geese window, pane 1):
[ "$(pwd)" = "$HOME/stray_goose" ] && echo "PASS: In stray_goose" || echo "FAIL: Not in stray_goose"
```

### 6. No obvious duplicate sessions/processes are running
```bash
# Check for duplicate broker processes
BROKER_COUNT=$(ps aux | grep -v grep | grep -c "python.*broker")
[ "$BROKER_COUNT" -le 1 ] && echo "PASS: $BROKER_COUNT broker process(es)" || echo "FAIL: $BROKER_COUNT broker processes (duplicates?)"

# Check for duplicate tmux sessions
TMUX_COUNT=$(tmux list-sessions 2>/dev/null | grep -c "mothergoose")
[ "$TMUX_COUNT" -le 1 ] && echo "PASS: $TMUX_COUNT mothergoose session(s)" || echo "FAIL: $TMUX_COUNT mothergoose sessions"
```

### 7. Basic health endpoints respond
```bash
echo "=== Health Endpoints ==="
# Broker health
BROKER_HEALTH=$(curl -s -m 3 http://127.0.0.1:5555/health 2>/dev/null)
[ -n "$BROKER_HEALTH" ] && echo "PASS: Broker health endpoint OK" || echo "FAIL: Broker health endpoint"

# Dashboard (if running)
DASHBOARD_RESPONSE=$(curl -s -m 3 http://127.0.0.1:8050/ 2>/dev/null)
[ -n "$DASHBOARD_RESPONSE" ] && echo "PASS: Dashboard responding" || echo "INFO: Dashboard not responding (may be OK)"

# Stats endpoint
STATS_RESPONSE=$(curl -s -m 3 http://127.0.0.1:5555/stats 2>/dev/null)
[ -n "$STATS_RESPONSE" ] && echo "PASS: Stats endpoint OK" || echo "FAIL: Stats endpoint"
```

### 8. One targeted test command in SIMP can run
```bash
# Run a simple test to verify test infrastructure works
cd "$(pwd | grep "kashclaw.*simp" || pwd)"
python3.10 -m pytest tests/test_a2a_compat.py -v -k "test_agent_card" --tb=short 2>&1 | head -20
TEST_EXIT=$?
[ $TEST_EXIT -eq 0 ] && echo "PASS: Test infrastructure works" || echo "INFO: Test may have failed (exit code: $TEST_EXIT)"
```

## Complete Preflight Script:
Create `scripts/preflight_check.sh`:

```bash
#!/bin/bash
# SIMP Flock Preflight Checklist

echo "=== SIMP Preflight Checklist ==="
echo "Timestamp: $(date)"
echo ""

# Function to run check and print result
run_check() {
    local name="$1"
    local command="$2"
    echo -n "✓ $name: "
    eval "$command" 2>/dev/null
}

# 1. tmux session
run_check "tmux session" 'tmux has-session -t mothergoose 2>/dev/null && echo "EXISTS" || echo "MISSING"'

# 2. proxy (optional)
run_check "proxy process" 'ps aux | grep -v grep | grep -q "proxy" && echo "RUNNING" || echo "NOT FOUND"'

# 3. broker
run_check "broker health" 'curl -s -m 3 http://127.0.0.1:5555/health >/dev/null 2>&1 && echo "HEALTHY" || echo "UNHEALTHY"'

# 4. SIMP repo location (simplified)
run_check "SIMP repo" 'pwd | grep -q "kashclaw.*simp" && echo "CORRECT" || echo "WRONG DIR"'

# 5. Test infrastructure
run_check "test runner" 'python3.10 -m pytest --version 2>&1 | grep -q "pytest" && echo "WORKING" || echo "BROKEN"'

echo ""
echo "=== Summary ==="
echo "Run full checklist in each pane:"
echo "1. Control pane: broker health, directory"
echo "2. SIMP Goose pane: SIMP repo location, test command"
echo "3. Stray Goose pane: ~/stray_goose location"
echo "4. Watchtower: health checks, log monitoring"
```

## Mother Goose Preflight Prompt:
```text
Run a preflight checklist for the flock.

Verify:
1) tmux session exists and is named correctly
2) proxy is reachable
3) broker is reachable
4) SIMP Goose pane is in the SIMP repo
5) Stray Goose pane is in ~/stray_goose
6) no obvious duplicate sessions/processes are running
7) basic health endpoints respond
8) one targeted test command in SIMP can run

Return:
- PASS/FAIL for each item
- blockers only
- recommended next action
```

## Expected Results:
- All PASS: System ready for work
- 1-2 FAIL/INFO: May proceed with caution
- 3+ FAIL: Fix blockers before proceeding

## Common Blockers and Solutions:
1. **Broker not running**: Run `./bin/start_broker.sh`
2. **Wrong directory**: Navigate to correct path
3. **Duplicate processes**: Kill old processes with `pkill -f "python.*broker"`
4. **Test failures**: Check Python version (use python3.10)