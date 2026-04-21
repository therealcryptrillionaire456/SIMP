# SIMP System - Persistence Troubleshooting Guide

## Overview
This guide provides troubleshooting procedures for persistence-related issues in the SIMP system. It covers common problems, diagnostic steps, and recovery procedures for JSONL persistence components.

## Quick Reference

### Emergency Procedures
- **Broker won't start**: Check port 5555, Python version, file permissions
- **JSONL corruption**: Use `head -n -1` to remove last incomplete line
- **Disk full**: Rotate or delete old JSONL files
- **High memory**: Check IntentLedger size, implement retention

### Diagnostic Commands
```bash
# Check broker health
curl -s http://127.0.0.1:5555/health | jq .

# Check file sizes
wc -l data/*.jsonl | sort -rn

# Validate JSONL files
python3.10 -c "import json; [json.loads(line) for line in open('data/agent_registry.jsonl')]"

# Monitor file growth
watch -n 60 'wc -l data/*.jsonl'
```

## Common Issues and Solutions

### Issue 1: Broker Fails to Start with JSON Decode Error

#### Symptoms
```
Error starting broker: JSONDecodeError: Expecting value: line 1 column 1 (char 0)
File: data/agent_registry.jsonl
```

#### Root Causes
1. **Empty or incomplete JSONL file** - File exists but is empty or has incomplete JSON
2. **Malformed JSON** - Invalid JSON syntax in one or more lines
3. **Encoding issues** - Non-UTF8 characters in file
4. **File corruption** - Disk error or interrupted write

#### Diagnostic Steps
```bash
# 1. Check file size and line count
ls -lh data/agent_registry.jsonl
wc -l data/agent_registry.jsonl

# 2. Check last few lines
tail -5 data/agent_registry.jsonl

# 3. Validate JSONL format
python3.10 -c "
import json, sys
with open('data/agent_registry.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f'Line {i}: {e}')
            print(f'Content: {line[:100]}...')
            sys.exit(1)
print('File is valid JSONL')
"

# 4. Check for empty lines
grep -n '^$' data/agent_registry.jsonl
```

#### Solutions

**Solution A: Remove Last Incomplete Line (Most Common)**
```bash
# Backup original file
cp data/agent_registry.jsonl data/agent_registry.jsonl.backup.$(date +%Y%m%d_%H%M%S)

# Remove last line (assuming it's incomplete)
head -n -1 data/agent_registry.jsonl.backup > data/agent_registry.jsonl

# Validate
python3.10 -c "import json; [json.loads(line) for line in open('data/agent_registry.jsonl')]"
```

**Solution B: Repair Malformed JSON**
```bash
# Find and fix specific malformed lines
python3.10 -c "
import json, sys
with open('data/agent_registry.jsonl.backup', 'r') as infile, \
     open('data/agent_registry.jsonl', 'w') as outfile:
    for i, line in enumerate(infile, 1):
        line = line.strip()
        if not line:
            continue  # Skip empty lines
        try:
            # Try to parse
            json.loads(line)
            outfile.write(line + '\\n')
        except json.JSONDecodeError as e:
            print(f'Repairing line {i}: {e}')
            # Attempt to fix common issues
            if line.endswith(',') or line.endswith(':'):
                # Remove trailing comma or colon
                line = line.rstrip(',:')
            if not line.endswith('}'):
                # Add missing closing brace
                line = line + '}'
            try:
                json.loads(line)
                outfile.write(line + '\\n')
                print(f'  Fixed line {i}')
            except:
                print(f'  Could not fix line {i}, skipping')
"
```

**Solution C: Restore from Backup**
```bash
# Find latest backup
LATEST_BACKUP=$(ls -td /backup/simp_* 2>/dev/null | head -1)

if [ -n "$LATEST_BACKUP" ]; then
    cp "$LATEST_BACKUP/agent_registry.jsonl" data/
    echo "Restored from backup: $LATEST_BACKUP"
else
    echo "No backup found, creating empty file"
    echo "" > data/agent_registry.jsonl
fi
```

**Solution D: Create Fresh File (Last Resort)**
```bash
# Backup corrupted file
mv data/agent_registry.jsonl data/agent_registry.jsonl.corrupted.$(date +%Y%m%d_%H%M%S)

# Create fresh file
echo "" > data/agent_registry.jsonl

# Note: This will lose all agent registrations
# Agents will need to re-register
```

#### Prevention
- **Regular backups**: Implement automated daily backups
- **File rotation**: Use `tools/jsonl_rotator.py` to prevent unbounded growth
- **Validation**: Run periodic JSONL validation checks
- **Graceful shutdown**: Ensure broker stops cleanly

### Issue 2: Slow Persistence Operations

#### Symptoms
- Agent registration takes >100ms
- Intent delivery delays
- High CPU usage during file writes
- Timeout errors in logs

#### Root Causes
1. **Large JSONL files** - Files >100MB cause slow reads/writes
2. **Disk I/O bottlenecks** - Slow disk or high contention
3. **Lock contention** - Multiple threads waiting for file locks
4. **Memory pressure** - System swapping due to low memory

#### Diagnostic Steps
```bash
# 1. Check file sizes
ls -lh data/*.jsonl

# 2. Check disk I/O
iostat -dx 5  # Linux
iotop         # Linux with iotop installed

# 3. Check for lock contention
# Monitor with lsof during operations
lsof data/*.jsonl

# 4. Check system resources
top
free -h
df -h .

# 5. Run performance benchmark
python3.10 tools/persistence_monitor.py --benchmark --iterations 1000
```

#### Solutions

**Solution A: Implement File Rotation**
```bash
# Rotate large files
python3.10 tools/jsonl_rotator.py --rotate-all --max-size 100

# Set up automated rotation (cron)
# 0 2 * * * cd /path/to/simp && python3.10 tools/jsonl_rotator.py --rotate-all --max-size 100
```

**Solution B: Optimize Disk Configuration**
```bash
# 1. Move to faster storage (SSD vs HDD)
# 2. Ensure adequate disk space (>20% free)
# 3. Consider separate disk for data directory
# 4. Use noatime mount option for performance
```

**Solution C: Tune Persistence Configuration**
```python
# In config/config.py or broker configuration:
# Reduce IntentLedger retention
MAX_INTENT_RECORDS = 5000  # Instead of 10000
INTENT_RECORD_TTL = 180    # 3 minutes instead of 5

# Consider disabling non-critical persistence
# AGENT_REGISTRY_PERSISTENCE_ENABLED = False  # If acceptable
```

**Solution D: Implement Caching**
```python
# For frequently accessed data, implement in-memory cache
# Example: Cache last 1000 agent lookups
import functools
from typing import Dict, Any

class CachedAgentRegistry:
    def __init__(self, registry):
        self.registry = registry
        self._cache: Dict[str, Any] = {}
        self._cache_size = 1000
    
    @functools.lru_cache(maxsize=1000)
    def get_agent(self, agent_id: str):
        return self.registry.get_agent(agent_id)
```

#### Prevention
- **Regular rotation**: Implement automated file rotation
- **Monitoring**: Set up alerts for file growth >1GB/day
- **Performance testing**: Run load tests before deployment
- **Capacity planning**: Monitor disk space and I/O metrics

### Issue 3: High Memory Usage

#### Symptoms
- Broker process using >1GB RAM
- System slowdown or swapping
- Out of memory errors in logs
- High resident set size (RSS)

#### Root Causes
1. **Large in-memory caches** - IntentLedger caching too many records
2. **Memory leaks** - Objects not being garbage collected
3. **Large file reads** - Loading entire JSONL files into memory
4. **Thread proliferation** - Too many concurrent threads

#### Diagnostic Steps
```bash
# 1. Check memory usage
ps aux | grep -E "(python.*start_server|gunicorn)" | grep -v grep

# 2. Check specific process
pmap -x $(pgrep -f "python.*start_server") | tail -20

# 3. Check for memory leaks over time
watch -n 60 'ps -o pid,user,%mem,command ax | grep start_server'

# 4. Check IntentLedger size
wc -l data/task_ledger.jsonl

# 5. Use memory profiler (if available)
python3.10 -m memory_profiler simp/server/broker.py
```

#### Solutions

**Solution A: Reduce Cache Sizes**
```python
# In broker configuration:
# Reduce IntentLedger cache size
MAX_INTENT_RECORDS = 1000  # Default is 10000
INTENT_RECORD_TTL = 60     # Default is 300

# In AgentRegistry:
# Consider reducing event cache if implemented
```

**Solution B: Implement Memory Limits**
```bash
# Use ulimit or container limits
ulimit -v 1000000  # 1GB virtual memory limit

# Or in systemd service file:
# MemoryMax=1G
# MemoryHigh=800M
```

**Solution C: Optimize File Reading**
```python
# Instead of reading entire file:
# with open(file) as f:
#     data = f.readlines()  # BAD: loads entire file

# Use streaming approach:
def read_latest_events(file_path, max_lines=1000):
    """Read only latest N lines without loading entire file"""
    with open(file_path, 'r') as f:
        # Seek to end and read backwards
        f.seek(0, 2)
        file_size = f.tell()
        
        lines = []
        buffer = ''
        position = file_size
        
        while position > 0 and len(lines) < max_lines:
            position = max(0, position - 8192)  # 8KB chunks
            f.seek(position)
            chunk = f.read(file_size - position)
            file_size = position
            
            # Process chunk
            buffer = chunk + buffer
            while '\n' in buffer:
                line, buffer = buffer.rsplit('\n', 1)
                if line:
                    lines.append(line)
                    if len(lines) >= max_lines:
                        break
        
        return list(reversed(lines))
```

**Solution D: Force Garbage Collection**
```python
import gc
import threading

class MemoryManager:
    def __init__(self, threshold_mb=500):
        self.threshold = threshold_mb * 1024 * 1024
        self.timer = threading.Timer(300, self._check_memory)  # Every 5 minutes
        self.timer.start()
    
    def _check_memory(self):
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        
        if memory_mb > self.threshold:
            print(f"High memory usage ({memory_mb:.1f}MB), forcing GC")
            gc.collect()
        
        # Restart timer
        self.timer = threading.Timer(300, self._check_memory)
        self.timer.start()
```

#### Prevention
- **Memory monitoring**: Set up alerts for memory >80%
- **Regular cleanup**: Implement periodic cache eviction
- **Load testing**: Test memory usage under production load
- **Code reviews**: Check for memory leaks in persistence code

### Issue 4: Concurrent Write Conflicts

#### Symptoms
- "File already open" errors
- Data corruption or missing entries
- Inconsistent agent counts
- Thread deadlocks or timeouts

#### Root Causes
1. **Missing or incorrect locking** - Multiple threads writing simultaneously
2. **File handle leaks** - Files not being closed properly
3. **Race conditions** - Operations not atomic
4. **Network file systems** - NFS/CIFS with poor locking support

#### Diagnostic Steps
```bash
# 1. Check for open file handles
lsof data/*.jsonl

# 2. Check lock contention in logs
grep -i "lock\|wait\|timeout" ~/bullbear/logs/simp_broker.log

# 3. Test concurrent operations
python3.10 tools/persistence_load_test.py --scenario agent_registry --agents 100 --threads 20

# 4. Check thread counts
ps -eLf | grep python | wc -l
```

#### Solutions

**Solution A: Verify Locking Implementation**
```python
# Ensure all persistence classes use proper locking
import threading
from pathlib import Path

class ThreadSafeJSONLWriter:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = threading.Lock()
    
    def append(self, record: dict):
        with self._lock:  # CRITICAL: Use lock for all file operations
            with open(self.file_path, 'a') as f:
                f.write(json.dumps(record) + '\n')
    
    def read_all(self):
        with self._lock:  # Also lock reads during writes
            if not self.file_path.exists():
                return []
            with open(self.file_path, 'r') as f:
                return [json.loads(line) for line in f]
```

**Solution B: Implement File Locking (fcntl/flock)**
```python
import fcntl
import os

class FileLock:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.lock_file = file_path + '.lock'
    
    def __enter__(self):
        self.fd = open(self.lock_file, 'w')
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.fd.close()
        os.unlink(self.lock_file)

# Usage:
with FileLock('data/agent_registry.jsonl'):
    # Perform file operations
    pass
```

**Solution C: Use Queue for Serialized Writes**
```python
import queue
import threading

class WriteQueue:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.queue = queue.Queue()
        self.writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self.writer_thread.start()
    
    def _writer_loop(self):
        while True:
            record = self.queue.get()
            if record is None:  # Poison pill
                break
            with open(self.file_path, 'a') as f:
                f.write(json.dumps(record) + '\n')
            self.queue.task_done()
    
    def append(self, record: dict):
        self.queue.put(record)
    
    def shutdown(self):
        self.queue.put(None)
        self.writer_thread.join()
```

**Solution D: Avoid Network File Systems**
```bash
# If using NFS/CIFS, consider:
# 1. Moving to local storage
# 2. Using distributed lock manager (DLM)
# 3. Implementing application-level coordination

# Check if filesystem is network-based
df -T data/ | grep -E "(nfs|cifs|gluster)"
```

#### Prevention
- **Thorough testing**: Test concurrent operations during development
- **Code reviews**: Verify locking in all persistence operations
- **Monitoring**: Alert on lock wait times >1s
- **Documentation**: Document thread safety guarantees

### Issue 5: Disk Space Exhaustion

#### Symptoms
- "No space left on device" errors
- Broker crashes during write operations
- Failed backups
- High disk usage (>90%)

#### Root Causes
1. **Unbounded JSONL growth** - No file rotation implemented
2. **Large log files** - Application logs consuming space
3. **Backup accumulation** - Old backups not being cleaned up
4. **Other processes** - Unrelated files consuming space

#### Diagnostic Steps
```bash
# 1. Check disk usage
df -h .

# 2. Check largest files
du -sh data/* | sort -rh
du -sh /backup/simp_* 2>/dev/null | sort -rh

# 3. Check file growth rate
wc -l data/*.jsonl
# Compare with yesterday's counts

# 4. Check for large rotated files
find data -name "*.jsonl.*" -size +100M -exec ls -lh {} \;
```

#### Solutions

**Solution A: Emergency Cleanup**
```bash
# 1. Rotate large files immediately
python3.10 tools/jsonl_rotator.py --rotate-all --max-size 10

# 2. Clean up old rotated files
python3.10 tools/jsonl_rotator.py --cleanup --keep-days 7

# 3. Remove old backups
find /backup -name "simp_*" -type d -mtime +30 -exec rm -rf {} \;

# 4. Clear application logs (if safe)
truncate -s 0 ~/bullbear/logs/simp_broker.log
```

**Solution B: Implement Disk Space Monitoring**
```python
#!/usr/bin/env python3
# disk_space_monitor.py

import shutil
import logging
from pathlib import Path

def check_disk_space(threshold_percent=90):
    """Check disk space and alert if above threshold"""
    usage = shutil.disk_usage('.')
    percent_used = (usage.used / usage.total) * 100
    
    if percent_used > threshold_percent:
        logging.warning(
            f"Disk space critical: {percent_used:.1f}% used "
            f"({usage.used / (1024**3):.1f}GB of {usage.total / (1024**3):.1f}GB)"
        )
        
        # Take automatic action if >95%
        if percent_used > 95:
            logging.error("Disk space >95%, performing emergency cleanup")
            # Call rotation script
            import subprocess
            subprocess.run(['python3.10', 'tools/jsonl_rotator.py', '--rotate-all', '--max-size', '10'])
    
    return percent_used

# Run as cron job every 5 minutes
if __name__ == '__main__':
    check_disk_space()
```

**Solution C: Implement Quotas**
```bash
# Set filesystem quotas
# For ext4:
sudo quotacheck -cug /path/to/data
sudo edquota -u simp_user

# Or use directory quotas (project quotas)
sudo quotaon -p /path/to/data
```

**Solution D: Archive Old Data**
```bash
# Archive instead of delete
ARCHIVE_DIR="/archive/simp_$(date +%Y%m)"
mkdir -p "$ARCHIVE_DIR"

# Move old rotated files to archive
find data -name "*.jsonl.*" -mtime +90 -exec mv {} "$ARCHIVE_DIR/" \;

# Compress archive
tar czf "$ARCHIVE_DIR.tar.gz" "$ARCHIVE_DIR"
rm -rf "$ARCHIVE_DIR"
```

#### Prevention
- **Proactive monitoring**: Alert on disk >80%
- **Regular cleanup**: Schedule daily/weekly cleanup jobs
- **Capacity planning**: Monitor growth trends, plan for expansion
- **Retention policies**: Define and enforce data retention rules

## Advanced Troubleshooting

### Issue 6: Performance Degradation Over Time

#### Symptoms
- Operations get slower as system runs longer
- Increasing latency not explained by load
- Periodic spikes in response time
- Garbage collection pauses

#### Diagnostic Steps
```bash
# 1. Monitor performance over time
python3.10 tools/persistence_monitor.py --monitor --interval 300

# 2. Check for memory fragmentation
cat /proc/$(pgrep -f "python.*start_server")/smaps

# 3. Profile CPU usage
python3.10 -m cProfile -o broker.prof simp/server/broker.py

# 4. Check for resource leaks
valgrind --leak-check=full python3.10 simp/server/broker.py
```

#### Solutions
- **Regular restarts**: Schedule weekly broker restarts
- **Memory profiling**: Use memory_profiler to identify leaks
- **Connection pooling**: Ensure HTTP clients use connection pools
- **Query optimization**: Review database/file access patterns

### Issue 7: Data Inconsistency

#### Symptoms
- Agent count mismatch between memory and disk
- Missing orchestration plans after restart
- Intent delivery records missing
- Audit log gaps

#### Diagnostic Steps
```bash
# 1. Compare memory vs disk state
curl -s http://127.0.0.1:5555/agents | jq '. | length'
wc -l data/agent_registry.jsonl

# 2. Check for write failures
grep -i "error\|fail\|exception" ~/bullbear/logs/simp_broker.log | grep -i "write\|save\|persist"

# 3. Validate event replay
python3.10 -c "
import json
events = []
with open('data/agent_registry.jsonl') as f:
    for line in f:
        events.append(json.loads(line))

# Simulate replay
agents = {}
for event in events:
    if event['event'] == 'registered':
        agents[event['agent_id']] = event
    elif event['event'] == 'deregistered':
        agents.pop(event['agent_id'], None)

print(f'Events: {len(events)}, Active agents: {len(agents)}')
"
```

#### Solutions
- **Implement write verification**: Verify writes succeed
- **Add checksums**: Include checksums in JSONL records
- **Regular consistency checks**: Run validation scripts periodically
- **Transaction logging**: Log all persistence operations

## Recovery Procedures

### Full System Recovery

#### Step 1: Assess Damage
```bash
# Check what's working
curl -s http://127.0.0.1:5555/health || echo "Broker down"

# Check file integrity
for file in data/*.jsonl; do
    echo -n "$file: "
    python3.10 -c "
import json, sys
try:
    with open('$file') as f:
        for line in f:
            json.loads(line)
    print('✓')
except:
    print('✗')
"
done
```

#### Step 2: Stop All Processes
```bash
bash emergency_shutdown.sh
```

#### Step 3: Restore from Backup
```bash
# Find latest valid backup
LATEST_VALID=$(find /backup -name "simp_*" -type d | sort -r | while read dir; do
    if python3.10 -c "
import json, glob, sys
for f in glob.glob('$dir/*.jsonl'):
    try:
        with open(f) as fp:
            for line in fp:
                json.loads(line)
    except:
        sys.exit(1)
    " 2>/dev/null; then
        echo "$dir"
        break
    fi
done)

if [ -n "$LATEST_VALID" ]; then
    echo "Restoring from: $LATEST_VALID"
    cp "$LATEST_VALID"/*.jsonl data/
else
    echo "No valid backup found, starting fresh"
    rm -f data/*.jsonl
    touch data/agent_registry.jsonl data/task_ledger.jsonl
fi
```

#### Step 4: Start Broker
```bash
bash bin/start_broker.sh
```

#### Step 5: Verify Recovery
```bash
sleep 5
curl -s http://127.0.0.1:5555/health | jq .
curl -s http://127.0.0.1:5555/agents | jq '. | length'
```

### Partial Data Recovery

#### Agent Registry Recovery
```bash
# Reconstruct agent registry from intent ledger
python3.10 -c "
import json, collections

# Extract agent registrations from intent ledger
agents = set()
with open('data/task_ledger.jsonl') as f:
    for line in f:
        record = json.loads(line)
        if 'source_agent' in record:
            agents.add(record['source_agent'])
        if 'target_agent' in record and record['target_agent'] != 'auto':
            agents.add(record['target_agent'])

# Create new agent registry
with open('data/agent_registry.jsonl.new', 'w') as f:
    for agent in agents:
        event = {
            'timestamp': '2024-01-01T00:00:00Z',  # Placeholder
            'event': 'registered',
            'agent_id': agent,
            'endpoint': f'http://127.0.0.1:9999',  # Placeholder
            'capabilities': ['ping']
        }
        f.write(json.dumps(event) + '\\n')

print(f'Recovered {len(agents)} agents')
"
```

## Prevention Best Practices

### 1. Regular Maintenance
```bash
# Daily: Check disk space and file sizes
# Weekly: Rotate files and clean up old data
# Monthly: Run comprehensive validation
# Quarterly: Review and update retention policies
```

### 2. Monitoring and Alerting
- **Disk space**: Alert at 80%, critical at 90%
- **File growth**: Alert if >1GB/day growth
- **Error rates**: Alert if persistence errors >1%
- **Latency**: Alert if average >100ms, critical >500ms

### 3. Testing and Validation
- **Load testing**: Before deployment and after major changes
- **Failure testing**: Simulate disk full, corruption, network issues
- **Recovery testing**: Test backup/restore procedures quarterly
- **Integration testing**: Test with all components together

### 4. Documentation and Training
- **Runbooks**: Keep operational procedures up to date
- **Training**: Train operators on troubleshooting procedures
- **Knowledge base**: Document all incidents and solutions
- **Post-mortems**: Analyze all failures and implement fixes

## Tools Reference

### Built-in Tools
```bash
# Persistence monitor
python3.10 tools/persistence_monitor.py --check
python3.10 tools/persistence_monitor.py --benchmark
python3.10 tools/persistence_monitor.py --monitor --interval 60

# JSONL rotator
python3.10 tools/jsonl_rotator.py --check
python3.10 tools/jsonl_rotator.py --rotate-all
python3.10 tools/jsonl_rotator.py --cleanup --keep-days 30

# Load tester
python3.10 tools/persistence_load_test.py --scenario production --duration 300
```

### External Tools
```bash
# JSON validation
jq . < file.jsonl  # Validate each line
python3.10 -m json.tool < file.json

# File monitoring
inotifywait -m data/  # Monitor file changes
watch -n 1 'ls -lh data/*.jsonl'

# Performance analysis
strace -p $(pgrep -f python)  # System calls
perf record -p $(pgrep -f python)  # CPU profiling
```

## Support Contacts

### Primary Support
- **Operations Team**: simp-ops@company.com
- **On-call Rotation**: PagerDuty schedule "SIMP-Ops"
- **Slack Channel**: #simp-operations

### Escalation Path
1. **Level 1**: Operations Team (24/7)
2. **Level 2**: Senior SRE (Business Hours)
3. **Level 3**: Development Team (Critical Issues)
4. **Level 4**: Vendor Support (If applicable)

### Documentation
- **Runbook**: docs/OPERATIONAL_RUNBOOK.md
- **Deployment Guide**: docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md
- **Architecture**: docs/SYSTEM_OVERVIEW.md
- **API Documentation**: docs/API_REFERENCE.md

---

**Document Status**: Approved  
**Last Updated**: 2024-04-15  
**Next Review**: 2024-05-15  
**Owner**: SIMP Operations Team