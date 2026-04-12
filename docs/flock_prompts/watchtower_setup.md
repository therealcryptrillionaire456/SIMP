# Watchtower Setup

Set up a lightweight observability routine for today's session.

## Goal:
Prepare commands for one tmux observability window with:
- broker health checks
- stats checks
- proxy availability checks
- log tails if log files exist

## Requirements:
- Do not install new infrastructure
- Use curl and shell only
- Prefer repeatable commands or a small shell script
- Output only:
  - commands to run
  - optional script names to create
  - expected healthy signals

## Example observability routine:

### Health Check Commands:

**Broker Health**:
```bash
# Check if broker is responding
curl -s http://127.0.0.1:5555/health | jq -r '.status'
# Expected: "healthy" or "ok"

# Check broker stats
curl -s http://127.0.0.1:5555/stats | jq -r '.agents_count'
# Expected: number > 0
```

**Dashboard Health**:
```bash
# Check dashboard
curl -s http://127.0.0.1:8050/ | grep -q "SIMP Dashboard" && echo "Dashboard OK"
```

**ProjectX Health**:
```bash
# Check ProjectX
curl -s http://127.0.0.1:8771/health 2>/dev/null || echo "ProjectX not responding"
```

**TimesFM Health** (if available):
```bash
# Check TimesFM
curl -s http://127.0.0.1:8780/health 2>/dev/null || echo "TimesFM not responding"
```

### Log Monitoring:

**Broker Logs**:
```bash
# Tail broker logs if they exist
if [ -f "logs/broker.log" ]; then
    tail -f logs/broker.log | grep -E "(ERROR|WARN|intent)"
elif [ -f "simp/server/logs/broker.log" ]; then
    tail -f simp/server/logs/broker.log | grep -E "(ERROR|WARN|intent)"
else
    echo "No broker log file found"
fi
```

### Watchtower Script:

Create `scripts/watchtower.sh`:
```bash
#!/bin/bash
# Watchtower - SIMP flock observability

echo "=== SIMP Watchtower ==="
echo "Timestamp: $(date)"
echo ""

echo "1. Broker Health:"
curl -s http://127.0.0.1:5555/health | jq -r '.status,.message' 2>/dev/null || echo "Broker unreachable"

echo ""
echo "2. Agent Count:"
curl -s http://127.0.0.1:5555/stats | jq -r '.agents_count' 2>/dev/null || echo "Stats unavailable"

echo ""
echo "3. Dashboard:"
curl -s http://127.0.0.1:8050/ 2>/dev/null | grep -q "SIMP" && echo "Dashboard OK" || echo "Dashboard down"

echo ""
echo "4. ProjectX:"
curl -s http://127.0.0.1:8771/health 2>/dev/null && echo "ProjectX OK" || echo "ProjectX down"

echo ""
echo "=== End Report ==="
```

### Expected Healthy Signals:
1. Broker: Returns JSON with status "healthy" or "ok"
2. Stats: agents_count > 0
3. Dashboard: Returns HTML containing "SIMP"
4. ProjectX: Returns health status (optional)

### Continuous Monitoring Commands:
```bash
# Run health check every 30 seconds
watch -n 30 './scripts/watchtower.sh'

# Or tail logs in one pane, run checks in another
tail -f logs/broker.log  # Pane 1
while true; do ./scripts/watchtower.sh; sleep 30; done  # Pane 2
```

## Remember:
- Keep it lightweight
- No new installations
- Shell and curl only
- Focus on operational awareness