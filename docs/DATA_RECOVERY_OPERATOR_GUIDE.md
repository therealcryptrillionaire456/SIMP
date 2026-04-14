# SIMP Data Recovery Operator Guide

## Overview

This guide provides operators with procedures for recovering system state from append-only JSONL logs. All critical SIMP components use disk persistence that survives broker restarts.

## 1. Data Directory Structure

```
data/
├── agent_registry.jsonl          # Agent registration/deregistration events
├── intent_ledger.jsonl           # All routed intents (append-only)
├── security_audit.jsonl          # Security events (authentication, authorization)
├── financial_ops_proposals.jsonl # Financial operation proposals
├── live_spend_ledger.jsonl       # Live payment attempts (when enabled)
├── rollback_log.jsonl            # FinancialOps rollback state changes
├── gate_log.jsonl                # Gate condition and sign-off events
├── orchestration_log.jsonl       # Orchestration plan execution events
└── task_ledger.jsonl            # Task execution records
```

## 2. Recovery Principles

### 2.1 Append-Only Design
- **Never modify or delete** existing JSONL entries
- System state is reconstructed by **replaying events**
- Each line is a complete JSON record with timestamp
- Files can grow large but are safe to rotate/archive

### 2.2 Thread Safety
All JSONL writes use `threading.Lock()` to prevent corruption from concurrent writes.

### 2.3 Event Replay
To reconstruct current state:
1. Read all lines in chronological order
2. Apply each event to an in-memory state
3. Final state represents current system state

## 3. Agent Registry Recovery

### 3.1 File Format
Each line in `agent_registry.jsonl`:
```json
{
  "timestamp": "2024-04-14T15:30:00Z",
  "event": "registered|updated|deregistered",
  "agent_id": "quantumarb",
  "agent_data": {
    "endpoint": "http://localhost:8765",
    "capabilities": ["arbitrage_detection", "trade_execution"],
    "heartbeat": "2024-04-14T15:29:00Z"
  }
}
```

### 3.2 Manual Recovery Script
```python
#!/usr/bin/env python3
import json
from pathlib import Path

def reconstruct_agent_registry():
    """Reconstruct current agent state from event log."""
    agents = {}
    log_path = Path("data/agent_registry.jsonl")
    
    if not log_path.exists():
        return agents
    
    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            
            if event["event"] == "registered":
                agents[event["agent_id"]] = event["agent_data"]
            elif event["event"] == "updated":
                agents[event["agent_id"]] = event["agent_data"]
            elif event["event"] == "deregistered":
                agents.pop(event["agent_id"], None)
    
    return agents

if __name__ == "__main__":
    agents = reconstruct_agent_registry()
    print(f"Current agents ({len(agents)}):")
    for agent_id, data in agents.items():
        print(f"  - {agent_id}: {data.get('endpoint', 'no endpoint')}")
```

### 3.3 Common Recovery Scenarios

#### Scenario 1: Broker crash with agents still running
```bash
# 1. Reconstruct agent registry
python3 reconstruct_agents.py

# 2. Restart broker - it will load persisted agents
python3 -m simp.server.http_server

# 3. Verify agents are registered
curl -s http://localhost:5555/agents | jq .
```

#### Scenario 2: Corrupted agent registry file
```bash
# 1. Backup corrupted file
cp data/agent_registry.jsonl data/agent_registry.jsonl.bak

# 2. Recreate from last known good state
echo '{"timestamp":"...","event":"registered","agent_id":"quantumarb",...}' > data/agent_registry.jsonl

# 3. Agents will re-register on next heartbeat
```

## 4. Intent Ledger Recovery

### 4.1 File Format
Each line in `intent_ledger.jsonl`:
```json
{
  "timestamp": "2024-04-14T15:31:00Z",
  "intent_id": "intent_abc123",
  "source_agent": "dashboard",
  "target_agent": "quantumarb",
  "intent_type": "arbitrage_analysis",
  "status": "delivered|failed|routed",
  "delivery_attempts": 1,
  "error": null
}
```

### 4.2 Analysis Commands
```bash
# Count intents by type
cat data/intent_ledger.jsonl | jq -r '.intent_type' | sort | uniq -c

# Find failed intents
cat data/intent_ledger.jsonl | jq -c 'select(.status == "failed")'

# Get delivery statistics
cat data/intent_ledger.jsonl | jq -r '.status' | sort | uniq -c

# Recent intents (last 100)
tail -100 data/intent_ledger.jsonl | jq -c '.'

# Intent volume by hour
cat data/intent_ledger.jsonl | jq -r '.timestamp | .[0:13]' | sort | uniq -c
```

### 4.3 Recovery Script
```python
#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime

def analyze_intent_ledger():
    """Analyze intent ledger for operational insights."""
    stats = {
        "total": 0,
        "by_type": defaultdict(int),
        "by_status": defaultdict(int),
        "by_hour": defaultdict(int),
        "failed": []
    }
    
    with open("data/intent_ledger.jsonl", "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            intent = json.loads(line)
            stats["total"] += 1
            stats["by_type"][intent.get("intent_type", "unknown")] += 1
            stats["by_status"][intent.get("status", "unknown")] += 1
            
            # Extract hour from timestamp
            ts = intent.get("timestamp", "")
            if ts:
                hour = ts[0:13]  # YYYY-MM-DDTHH
                stats["by_hour"][hour] += 1
            
            if intent.get("status") == "failed":
                stats["failed"].append(intent)
    
    return stats

if __name__ == "__main__":
    stats = analyze_intent_ledger()
    print(f"Total intents: {stats['total']}")
    print("\nBy type:")
    for intent_type, count in sorted(stats["by_type"].items()):
        print(f"  {intent_type}: {count}")
    
    if stats["failed"]:
        print(f"\nFailed intents: {len(stats['failed'])}")
        for intent in stats["failed"][:5]:  # Show first 5
            print(f"  - {intent.get('intent_id')}: {intent.get('error')}")
```

## 5. Security Audit Recovery

### 5.1 File Format
Each line in `security_audit.jsonl`:
```json
{
  "timestamp": "2024-04-14T15:32:00Z",
  "event_type": "authentication_success|authentication_failure|authorization_granted|authorization_denied",
  "agent_id": "dashboard",
  "ip_address": "127.0.0.1",
  "user_agent": "Mozilla/5.0",
  "details": {
    "endpoint": "/agents",
    "method": "GET"
  }
}
```

### 5.2 Security Analysis
```bash
# Count authentication failures
cat data/security_audit.jsonl | jq -c 'select(.event_type == "authentication_failure")' | wc -l

# Recent security events
tail -50 data/security_audit.jsonl | jq -c '.'

# Failed logins by IP
cat data/security_audit.jsonl | jq -r 'select(.event_type == "authentication_failure") | .ip_address' | sort | uniq -c

# Authorization denials
cat data/security_audit.jsonl | jq -c 'select(.event_type == "authorization_denied")'
```

## 6. Financial Operations Recovery

### 6.1 Ledger Files
- `financial_ops_proposals.jsonl`: Payment proposal lifecycle
- `live_spend_ledger.jsonl`: Actual payment attempts (when live mode enabled)
- `rollback_log.jsonl`: Rollback state changes
- `gate_log.jsonl`: Gate condition tracking

### 6.2 Recovery Commands
```bash
# View recent proposals
tail -20 data/financial_ops_proposals.jsonl | jq -c '.'

# Check rollback status
tail -5 data/rollback_log.jsonl | jq -c '.'

# Gate progression
cat data/gate_log.jsonl | jq -c 'select(.event == "condition_met" or .event == "signed_off")'

# Budget analysis
cat data/live_spend_ledger.jsonl 2>/dev/null | jq -r '.amount' | awk '{sum+=$1} END {print "Total spent: $" sum}'
```

## 7. System Health Monitoring

### 7.1 Daily Health Check Script
```bash
#!/bin/bash
# daily_health_check.sh

echo "=== SIMP System Health Check ==="
echo "Date: $(date)"
echo

# Check all data files exist
echo "1. Data Files:"
for file in agent_registry.jsonl intent_ledger.jsonl security_audit.jsonl; do
    if [ -f "data/$file" ]; then
        count=$(wc -l < "data/$file" 2>/dev/null || echo "0")
        size=$(du -h "data/$file" 2>/dev/null | cut -f1)
        echo "  ✓ $file: $count lines, $size"
    else
        echo "  ✗ $file: MISSING"
    fi
done
echo

# Agent status
echo "2. Agent Registry:"
if [ -f "data/agent_registry.jsonl" ]; then
    agent_count=$(grep '"event":"registered"' data/agent_registry.jsonl | tail -1 | grep -o '"agent_id":"[^"]*"' | wc -l)
    echo "  Registered agents: $agent_count"
else
    echo "  No agent registry found"
fi
echo

# Intent volume last 24h
echo "3. Intent Volume (last 24h):"
if [ -f "data/intent_ledger.jsonl" ]; then
    yesterday=$(date -v-1d +%Y-%m-%dT)
    recent_count=$(grep -c "$yesterday" data/intent_ledger.jsonl 2>/dev/null || echo "0")
    echo "  Intents in last 24h: $recent_count"
else
    echo "  No intent ledger found"
fi
echo

# Security events
echo "4. Security Events:"
if [ -f "data/security_audit.jsonl" ]; then
    auth_failures=$(grep -c 'authentication_failure' data/security_audit.jsonl 2>/dev/null || echo "0")
    echo "  Authentication failures: $auth_failures"
else
    echo "  No security audit log found"
fi
```

### 7.2 Automated Monitoring
Add to crontab:
```bash
# Daily health check at 2 AM
0 2 * * * cd /path/to/simp && ./daily_health_check.sh >> /var/log/simp/health.log 2>&1

# Weekly data backup every Sunday at 3 AM
0 3 * * 0 cd /path/to/simp && tar -czf /backup/simp-data-$(date +\%Y\%m\%d).tar.gz data/
```

## 8. Emergency Procedures

### 8.1 Complete System Recovery
```bash
# 1. Stop all SIMP processes
pkill -f "simp.server.http_server"
pkill -f "python.*simp"

# 2. Backup current data
BACKUP_DIR="/backup/simp-recovery-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r data/* "$BACKUP_DIR/"

# 3. Verify data integrity
for file in data/*.jsonl; do
    echo "Checking $file..."
    if ! tail -1 "$file" | jq . >/dev/null 2>&1; then
        echo "  WARNING: $file may be corrupted"
        # Remove last line if corrupted
        head -n -1 "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
    fi
done

# 4. Restart broker
python3 -m simp.server.http_server &

# 5. Verify system
sleep 5
curl -s http://localhost:5555/health | jq .
```

### 8.2 Data File Rotation
```bash
# Rotate large JSONL files (run weekly)
for file in data/*.jsonl; do
    size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
    if [ "$size" -gt 100000000 ]; then  # 100MB
        echo "Rotating $file (size: $size bytes)"
        gzip "$file"
        echo '{"timestamp":"'$(date -Iseconds)'","event":"file_rotated","filename":"'$file'"}' > "$file"
    fi
done
```

## 9. Best Practices

### 9.1 Regular Maintenance
1. **Daily**: Check data file sizes and system health
2. **Weekly**: Backup data directory
3. **Monthly**: Review security audit logs
4. **Quarterly**: Test recovery procedures

### 9.2 Monitoring Alerts
Set up alerts for:
- Data file growth > 1GB
- Authentication failures > 10/hour
- Agent count dropping unexpectedly
- Intent delivery failure rate > 5%

### 9.3 Documentation
- Keep this guide updated with any new data files
- Document custom recovery scripts
- Maintain runbooks for common failure scenarios

## 10. Troubleshooting

### 10.1 Common Issues

#### Issue: Agent registry empty after restart
**Solution**: Check `data/agent_registry.jsonl` permissions and disk space. Agents will re-register on next heartbeat.

#### Issue: JSONL file corruption
**Solution**: Use `jq .` to validate each line. Remove corrupted lines at end of file.

#### Issue: High disk usage
**Solution**: Implement log rotation for JSONL files > 100MB.

#### Issue: Missing data files
**Solution**: System will create missing files on first write. Check directory permissions.

### 10.2 Support
For additional support:
1. Check `docs/` directory for component-specific documentation
2. Review test files for expected behavior
3. Examine source code for persistence implementation details
4. Contact system administrator for critical issues