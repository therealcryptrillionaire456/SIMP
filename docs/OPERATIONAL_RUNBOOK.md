# SIMP System - Operational Runbook

## Overview
This runbook provides operational procedures for the SIMP system with enhanced persistence features. It covers daily operations, monitoring, troubleshooting, and emergency procedures.

## System Architecture

### Core Components
1. **SIMP Broker** (port 5555) - Central message router with persistence
2. **AgentRegistry** - Persistent agent state with JSONL event replay
3. **OrchestrationManager** - Full state persistence for orchestration plans
4. **IntentLedger** - Thread-safe intent delivery logging
5. **Dashboard** (port 8050) - Operator console with broker integration

### Persistence Files
```
data/
├── agent_registry.jsonl      # Agent registration events (append-only)
├── task_ledger.jsonl         # Intent delivery records (append-only)
├── orchestration_plans.jsonl # Orchestration plan state
├── orchestration_log.jsonl   # Orchestration execution logs
├── financial_ops_proposals.jsonl  # Financial operation proposals
├── security_audit.jsonl      # Security audit trail
└── broker.pid               # Broker process ID
```

## Daily Operations

### Startup Procedure
```bash
# 1. Check system prerequisites
python3.10 --version
df -h .  # Check disk space

# 2. Start broker
bash bin/start_broker.sh

# 3. Verify startup
curl -s http://127.0.0.1:5555/health | jq .
curl -s http://127.0.0.1:5555/agents | jq '. | length'

# 4. Start dashboard (optional)
cd dashboard && python3.10 server.py &
```

### Daily Health Check
```bash
#!/bin/bash
# daily_health_check.sh

echo "=== SIMP System Daily Health Check ==="
echo "Timestamp: $(date)"

# 1. Broker health
echo -n "Broker health: "
if curl -sf http://127.0.0.1:5555/health > /dev/null; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

# 2. File sizes
echo -e "\nFile sizes:"
wc -l data/*.jsonl | sort -rn

# 3. Disk space
echo -e "\nDisk space:"
df -h .

# 4. Memory usage
echo -e "\nMemory usage:"
ps aux | grep -E "(python.*start_server|gunicorn)" | grep -v grep | awk '{print $6/1024 " MB"}'

# 5. Recent errors
echo -e "\nRecent errors (last 24h):"
grep -i error ~/bullbear/logs/simp_broker.log 2>/dev/null | tail -5 || echo "No error log found"

echo -e "\n=== Health check complete ==="
```

### Monitoring Commands

#### Real-time Monitoring
```bash
# Monitor broker logs
tail -f ~/bullbear/logs/simp_broker.log

# Monitor file growth
watch -n 60 'wc -l data/*.jsonl'

# Monitor system resources
htop  # or top/glances
```

#### Periodic Checks
```bash
# Every hour: Check file sizes
wc -l data/*.jsonl

# Every 4 hours: Check disk space
df -h .

# Daily: Validate JSONL integrity
python3.10 tools/persistence_monitor.py --check

# Weekly: Run performance benchmark
python3.10 tools/persistence_monitor.py --benchmark --iterations 1000
```

## Performance Monitoring

### Key Metrics to Track
1. **File Growth Rate** - MB/day for each JSONL file
2. **Operation Latency** - Average persistence operation time
3. **Success Rate** - Percentage of successful persistence operations
4. **Memory Usage** - Broker process memory consumption
5. **Disk I/O** - Read/write operations per second

### Monitoring Scripts

#### File Growth Monitor
```bash
#!/bin/bash
# monitor_file_growth.sh

DATA_DIR="data"
LOG_FILE="logs/file_growth.log"

# Record current sizes
for file in $DATA_DIR/*.jsonl; do
    if [ -f "$file" ]; then
        size=$(stat -f%z "$file")
        lines=$(wc -l < "$file")
        echo "$(date),$file,$size,$lines" >> "$LOG_FILE"
    fi
done

# Calculate daily growth
if [ -f "$LOG_FILE" ]; then
    echo -e "\nDaily growth summary:"
    tail -100 "$LOG_FILE" | awk -F, '
    BEGIN { OFS="," }
    {
        file=$2; size=$3; lines=$4;
        if (first[file]=="") { first[file]=size; first_time[file]=$1; }
        last[file]=size; last_time[file]=$1;
    }
    END {
        for (file in first) {
            growth=last[file]-first[file];
            days=(mktime(gensub(/[-:]/, " ", "g", last_time[file])) - 
                  mktime(gensub(/[-:]/, " ", "g", first_time[file]))) / 86400;
            if (days > 0) {
                daily_growth=growth/days;
                printf "%s: %.1f MB/day\n", file, daily_growth/1048576;
            }
        }
    }'
fi
```

#### Performance Monitor
```python
#!/usr/bin/env python3
# quick_perf_check.py

import json
import time
from pathlib import Path

def check_persistence_performance():
    """Quick performance check of persistence operations"""
    data_dir = Path("data")
    
    print("Persistence Performance Check")
    print("=" * 60)
    
    # Check file access times
    for jsonl_file in data_dir.glob("*.jsonl"):
        if jsonl_file.exists():
            start = time.time()
            with open(jsonl_file, 'r') as f:
                lines = f.readlines()[-100:]  # Read last 100 lines
            read_time = (time.time() - start) * 1000
            
            start = time.time()
            # Test write performance
            test_line = json.dumps({"test": time.time(), "operation": "perf_check"})
            with open(jsonl_file, 'a') as f:
                f.write(test_line + "\n")
            write_time = (time.time() - start) * 1000
            
            print(f"{jsonl_file.name}:")
            print(f"  Read (100 lines): {read_time:.1f} ms")
            print(f"  Write (1 line):   {write_time:.1f} ms")
            print(f"  Size: {jsonl_file.stat().st_size / 1048576:.1f} MB")
    
if __name__ == "__main__":
    check_persistence_performance()
```

## Troubleshooting Guide

### Common Issues and Solutions

#### ❌ Broker Won't Start
**Symptoms**: 
- Port 5555 already in use
- Python 3.10 not found
- Permission denied on data directory

**Solutions**:
```bash
# Check port usage
lsof -i :5555

# Kill conflicting process
pkill -f "python.*start_server.py"
pkill -f "gunicorn.*simp.server.http_server"

# Check Python version
python3.10 --version

# Fix permissions
chmod 755 data/
chmod 644 data/*.jsonl
```

#### ❌ JSONL File Corruption
**Symptoms**:
- Broker crashes on startup with JSON decode error
- "Malformed JSON" in logs
- File size doesn't match line count

**Recovery Procedure**:
```bash
# 1. Stop broker
pkill -f "python.*start_server.py"

# 2. Backup corrupted file
cp data/agent_registry.jsonl data/agent_registry.jsonl.backup.$(date +%Y%m%d_%H%M%S)

# 3. Attempt repair (remove last incomplete line)
head -n -1 data/agent_registry.jsonl.backup > data/agent_registry.jsonl

# 4. Validate repair
python3.10 -c "
import json
with open('data/agent_registry.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f'Line {i}: {e}')
            break
else:
    print('File is valid JSONL')
"

# 5. Restart broker
bash bin/start_broker.sh
```

#### ❌ High Memory Usage
**Symptoms**:
- Broker process using >1GB RAM
- System slowdown
- Out of memory errors

**Mitigation**:
```bash
# 1. Check which component is using memory
ps aux | grep python | grep simp

# 2. Check IntentLedger size (common culprit)
wc -l data/task_ledger.jsonl

# 3. Implement retention policy
python3.10 tools/jsonl_rotator.py --rotate task_ledger.jsonl --max-size 500

# 4. Restart broker with memory limits
# Edit bin/start_broker.sh to add ulimit or use systemd limits
```

#### ❌ Slow Persistence Operations
**Symptoms**:
- High latency on agent registration (>100ms)
- Intent delivery delays
- Timeout errors

**Diagnosis and Fix**:
```bash
# 1. Run performance benchmark
python3.10 tools/persistence_monitor.py --benchmark

# 2. Check disk I/O
iostat -dx 5  # Linux
iotop         # Linux with iotop installed

# 3. Check for locking contention
# Monitor with strace or lsof
lsof data/*.jsonl

# 4. Consider moving to faster storage
# SSD vs HDI, local vs network storage
```

### Emergency Procedures

#### Immediate Shutdown
```bash
#!/bin/bash
# emergency_shutdown.sh

echo "=== EMERGENCY SHUTDOWN ==="
echo "Timestamp: $(date)"

# 1. Graceful shutdown attempt
curl -X POST http://127.0.0.1:5555/control/shutdown 2>/dev/null || true
sleep 5

# 2. Force kill if still running
pkill -9 -f "python.*start_server.py"
pkill -9 -f "gunicorn.*simp.server.http_server"

# 3. Remove PID file
rm -f data/broker.pid 2>/dev/null || true

# 4. Verify shutdown
if pgrep -f "python.*simp" > /dev/null; then
    echo "WARNING: Some processes still running"
    pgrep -fl "python.*simp"
else
    echo "✓ All SIMP processes stopped"
fi

echo "=== Shutdown complete ==="
```

#### Data Recovery
```bash
#!/bin/bash
# data_recovery.sh

echo "=== DATA RECOVERY PROCEDURE ==="
echo "Timestamp: $(date)"

# 1. Stop all processes
bash emergency_shutdown.sh

# 2. Identify latest valid backup
LATEST_BACKUP=$(ls -td /backup/simp_* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "ERROR: No backups found"
    exit 1
fi

echo "Using backup: $LATEST_BACKUP"

# 3. Backup current data (in case we need to revert)
RECOVERY_BACKUP="data/recovery_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RECOVERY_BACKUP"
cp data/*.jsonl "$RECOVERY_BACKUP/" 2>/dev/null || true
echo "Current data backed up to: $RECOVERY_BACKUP"

# 4. Restore from backup
cp "$LATEST_BACKUP"/*.jsonl data/ 2>/dev/null || true

# 5. Validate restored data
echo -e "\nValidating restored data:"
for file in data/*.jsonl; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file" 2>/dev/null || echo "0")
        echo "  $(basename "$file"): $lines lines"
    fi
done

# 6. Start broker
echo -e "\nStarting broker..."
bash bin/start_broker.sh
sleep 3

# 7. Verify recovery
if curl -sf http://127.0.0.1:5555/health > /dev/null; then
    echo "✓ Recovery successful"
    AGENT_COUNT=$(curl -s http://127.0.0.1:5555/agents | jq '. | length')
    echo "  Agents registered: $AGENT_COUNT"
else
    echo "✗ Recovery failed"
    echo "Check logs and consider restoring from recovery_backup"
fi

echo "=== Recovery complete ==="
```

#### Rollback Procedure
```bash
#!/bin/bash
# rollback_procedure.sh

echo "=== ROLLBACK PROCEDURE ==="
echo "Use this if a deployment causes issues"

# 1. Stop broker
bash emergency_shutdown.sh

# 2. Restore previous version
# Assuming you use git for version control
git log --oneline -5
read -p "Enter commit hash to rollback to: " COMMIT_HASH

git checkout $COMMIT_HASH

# 3. Restore data from before deployment
# This assumes you backed up data before deployment
PRE_DEPLOYMENT_BACKUP="/backup/simp_before_deployment_$(date +%Y%m%d)"
if [ -d "$PRE_DEPLOYMENT_BACKUP" ]; then
    cp "$PRE_DEPLOYMENT_BACKUP"/*.jsonl data/
    echo "Restored data from: $PRE_DEPLOYMENT_BACKUP"
fi

# 4. Start broker
bash bin/start_broker.sh

echo "=== Rollback complete ==="
```

## Maintenance Procedures

### Regular Maintenance Tasks

#### Weekly Maintenance
```bash
#!/bin/bash
# weekly_maintenance.sh

echo "=== Weekly Maintenance ==="
echo "Timestamp: $(date)"

# 1. Rotate large files
python3.10 tools/jsonl_rotator.py --rotate-all --max-size 500

# 2. Clean up old rotated files
python3.10 tools/jsonl_rotator.py --cleanup --keep-days 30

# 3. Validate data integrity
python3.10 -c "
import json, glob
for f in glob.glob('data/*.jsonl'):
    try:
        with open(f) as fp:
            for line in fp:
                json.loads(line)
        print(f'✓ {f} valid')
    except Exception as e:
        print(f'✗ {f}: {e}')
"

# 4. Backup
BACKUP_DIR="/backup/simp_weekly_$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
cp data/*.jsonl "$BACKUP_DIR/"
echo "Backup created: $BACKUP_DIR"

echo "=== Weekly maintenance complete ==="
```

#### Monthly Maintenance
```bash
#!/bin/bash
# monthly_maintenance.sh

echo "=== Monthly Maintenance ==="
echo "Timestamp: $(date)"

# 1. Comprehensive performance test
python3.10 tools/persistence_load_test.py --scenario production --duration 300

# 2. Archive old data
ARCHIVE_DIR="/archive/simp_$(date +%Y%m)"
mkdir -p "$ARCHIVE_DIR"

# Archive files older than 90 days
find data -name "*.jsonl.*" -mtime +90 -exec mv {} "$ARCHIVE_DIR/" \;

# 3. Update documentation
# Check for outdated procedures
# Update runbook based on recent issues

# 4. Review security settings
# Check API keys, permissions, audit logs

echo "=== Monthly maintenance complete ==="
```

### File Rotation Management

#### Manual Rotation
```bash
# Check which files need rotation
python3.10 tools/jsonl_rotator.py --check

# Rotate specific file
python3.10 tools/jsonl_rotator.py --rotate task_ledger.jsonl --max-size 1000

# Rotate all files needing rotation
python3.10 tools/jsonl_rotator.py --rotate-all

# Clean up old files
python3.10 tools/jsonl_rotator.py --cleanup --keep-days 30
```

#### Automated Rotation (Cron)
```bash
# Add to crontab (crontab -e)
# Daily at 2 AM: Check and rotate if needed
0 2 * * * cd /path/to/simp && python3.10 tools/jsonl_rotator.py --rotate-all --max-size 500 >> logs/rotation.log 2>&1

# Weekly at 3 AM Sunday: Cleanup old files
0 3 * * 0 cd /path/to/simp && python3.10 tools/jsonl_rotator.py --cleanup --keep-days 30 >> logs/cleanup.log 2>&1
```

## Monitoring and Alerting

### Key Performance Indicators (KPIs)

#### Must Alert (Critical)
1. **Broker down** - Health endpoint returns non-200
2. **Disk >90% full** - Risk of data loss
3. **JSONL corruption** - Malformed JSON in log files
4. **Memory >80%** - Risk of OOM kill

#### Should Alert (Warning)
1. **File growth >1GB/day** - Unusual activity
2. **Success rate <95%** - Persistence issues
3. **Latency >500ms** - Performance degradation
4. **Agent count drop >50%** - Possible data loss

#### Nice to Monitor (Informational)
1. **Daily operation count** - Usage trends
2. **File rotation frequency** - Growth patterns
3. **Backup success** - Data protection
4. **Test suite results** - System health

### Alert Configuration Examples

#### Nagios/Icinga
```bash
# check_simp_health.sh
#!/bin/bash

HEALTH=$(curl -sf http://localhost:5555/health)
if [ $? -ne 0 ]; then
    echo "CRITICAL: SIMP broker not responding"
    exit 2
fi

STATUS=$(echo "$HEALTH" | jq -r '.status')
if [ "$STATUS" != "healthy" ]; then
    echo "WARNING: SIMP broker status: $STATUS"
    exit 1
fi

echo "OK: SIMP broker healthy"
exit 0
```

#### Prometheus Metrics
```python
# prometheus_exporter.py
from prometheus_client import start_http_server, Gauge, Counter
import time
import json
from pathlib import Path

# Metrics
simp_health = Gauge('simp_health', 'SIMP broker health (1=healthy, 0=unhealthy)')
simp_agents = Gauge('simp_agents', 'Number of registered agents')
simp_file_size = Gauge('simp_file_size_bytes', 'Size of JSONL files', ['file'])
simp_operations = Counter('simp_operations_total', 'Total operations', ['type'])

def collect_metrics():
    # Collect health
    try:
        import requests
        health = requests.get('http://localhost:5555/health').json()
        simp_health.set(1 if health.get('status') == 'healthy' else 0)
        
        agents = requests.get('http://localhost:5555/agents').json()
        simp_agents.set(len(agents))
    except:
        simp_health.set(0)
    
    # Collect file sizes
    data_dir = Path('data')
    for jsonl_file in data_dir.glob('*.jsonl'):
        if jsonl_file.exists():
            simp_file_size.labels(file=jsonl_file.name).set(jsonl_file.stat().st_size)

if __name__ == '__main__':
    start_http_server(8000)
    while True:
        collect_metrics()
        time.sleep(30)
```

## Disaster Recovery

### Recovery Time Objective (RTO)
- **Critical**: 15 minutes (broker outage)
- **Important**: 1 hour (data corruption)
- **Standard**: 4 hours (full system recovery)

### Recovery Point Objective (RPO)
- **Critical**: 5 minutes (near-zero data loss)
- **Important**: 1 hour (minimal data loss)
- **Standard**: 24 hours (acceptable data loss)

### Recovery Procedures

#### Scenario 1: Broker Process Crash
```bash
# Automatic recovery (use process manager like systemd or supervisord)
# systemd service file ensures auto-restart

# Manual recovery
bash emergency_shutdown.sh
bash bin/start_broker.sh
```

#### Scenario 2: Data Corruption
```bash
# Follow data_recovery.sh procedure
bash data_recovery.sh
```

#### Scenario 3: Full System Failure
```bash
# 1. Restore from backup
scp backup_server:/backup/simp_latest.tar.gz .
tar xzf simp_latest.tar.gz

# 2. Restore configuration
cp backup_config/* config/

# 3. Start services
bash bin/start_broker.sh

# 4. Verify recovery
bash daily_health_check.sh
```

### Backup Strategy

#### Automated Backups
```bash
#!/bin/bash
# automated_backup.sh

BACKUP_DIR="/backup/simp_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup data files
cp -r data/*.jsonl "$BACKUP_DIR/"

# Backup configuration
cp -r config/ "$BACKUP_DIR/config/"

# Backup scripts
cp -r bin/ "$BACKUP_DIR/bin/"

# Create restore script
cat > "$BACKUP_DIR/restore.sh" << 'EOF'
#!/bin/bash
echo "Restoring SIMP system from backup..."
cp *.jsonl ../../data/
echo "Restore complete"
EOF
chmod +x "$BACKUP_DIR/restore.sh"

# Rotate old backups (keep 30 days)
find /backup -name "simp_*" -type d -mtime +30 -exec rm -rf {} \;

echo "Backup created: $BACKUP_DIR"
```

#### Backup Verification
```bash
#!/bin/bash
# verify_backup.sh

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory>"
    exit 1
fi

echo "Verifying backup: $BACKUP_DIR"

# Check required files
REQUIRED_FILES=("agent_registry.jsonl" "task_ledger.jsonl")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$BACKUP_DIR/$file" ]; then
        echo "✗ Missing required file: $file"
        exit 1
    fi
done

# Validate JSONL format
for jsonl_file in "$BACKUP_DIR"/*.jsonl; do
    echo -n "Validating $(basename "$jsonl_file")... "
    if python3.10 -c "
import json, sys
with open('$jsonl_file') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError:
            print(f'Invalid JSON at line {i}')
            sys.exit(1)
    print('OK')
" > /dev/null 2>&1; then
        echo "✓"
    else
        echo "✗"
        exit 1
    fi
done

echo "✓ Backup verification successful"
```

## Appendix

### Command Reference

#### Broker Management
```bash
# Start broker
bash bin/start_broker.sh
python3.10 bin/start_production.py --workers 4

# Stop broker
curl -X POST http://127.0.0.1:5555/control/shutdown
pkill -f "python.*start_server.py"

# Check status
curl http://127.0.0.1:5555/health
curl http://127.0.0.1:5555/stats
curl http://127.0.0.1:5555/agents
```

#### Persistence Management
```bash
# Monitor persistence
python3.10 tools/persistence_monitor.py --monitor --interval 60
python3.10 tools/persistence_monitor.py --check

# Rotate files
python3.10 tools/jsonl_rotator.py --check
python3.10 tools/jsonl_rotator.py --rotate-all

# Load test
python3.10 tools/persistence_load_test.py --scenario production --duration 300
```

#### Data Management
```bash
# Backup
bash tools/automated_backup.sh

# Restore
bash data_recovery.sh

# Validate
python3.10 -c "import json; [json.loads(line) for line in open('data/agent_registry.jsonl')]"
```

### Contact Information

#### Primary Contacts
- **System Administrator**: [Name] - [Phone] - [Email]
- **Database Administrator**: [Name] - [Phone] - [Email]
- **Development Team**: [Team Email]

#### Escalation Path
1. **Level 1**: System Operator (24/7)
2. **Level 2**: Senior Administrator (Business Hours)
3. **Level 3**: Development Team (Critical Issues)
4. **Level 4**: Vendor Support (If applicable)

#### Communication Channels
- **Primary**: Slack/Teams Channel #simp-operations
- **Secondary**: Email: simp-ops@company.com
- **Emergency**: PagerDuty/SMS alerts

### Change Log

#### Version 1.0 (2024-04-14)
- Initial operational runbook
- Enhanced persistence procedures
- Disaster recovery procedures
- Monitoring and alerting guidelines

#### Planned Updates
- Add Kubernetes deployment procedures
- Add cloud-specific monitoring
- Add advanced troubleshooting scenarios
- Add performance tuning guide

---

**Document Status**: Approved  
**Last Reviewed**: 2024-04-14  
**Next Review**: 2024-05-14  
**Owner**: SIMP Operations Team