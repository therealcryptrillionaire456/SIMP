# SIMP System - Production Deployment Checklist

## Overview
This checklist guides operators through deploying the enhanced SIMP system with persistence features to production. The system now includes:
- **AgentRegistry persistence** with JSONL event replay
- **OrchestrationManager full state persistence** with plan serialization
- **IntentLedger thread-safe persistence** with file locking
- **FinancialOps simulated ledger** with append-only logging

## Pre-Deployment Preparation

### ✅ Environment Verification
- [ ] **Python 3.10+** installed and available as `python3.10`
- [ ] **Required packages** installed: `pip install -r requirements.txt`
- [ ] **Data directory** exists: `data/` with proper permissions
- [ ] **Log directory** exists: `logs/` or configured location
- [ ] **Disk space** sufficient for JSONL growth (minimum 1GB free)
- [ ] **Memory** adequate for expected load (minimum 2GB RAM)

### ✅ Configuration Review
- [ ] **Broker configuration** reviewed in `config/config.py`
- [ ] **Persistence settings** verified:
  - `AgentRegistryConfig.persistence_enabled = True` (default)
  - `OrchestrationManagerConfig.persistence_enabled = True` (default)
  - `IntentLedger.file_path = "data/task_ledger.jsonl"` (default)
- [ ] **Security settings** confirmed:
  - `FINANCIAL_OPS_LIVE_ENABLED = False` (simulated mode)
  - API keys configured if required
  - Rate limits appropriate for production
- [ ] **Network configuration** set:
  - Host binding (default: 127.0.0.1 for local, 0.0.0.0 for external)
  - Port (default: 5555)
  - CORS settings if needed

### ✅ Data Migration (If Upgrading)
- [ ] **Backup existing data**: `cp -r data/ data_backup_$(date +%Y%m%d_%H%M%S)/`
- [ ] **Verify JSONL file integrity**: Run `python3.10 -m simp.tools.validate_jsonl data/`
- [ ] **Test data recovery**: Verify backup can be restored
- [ ] **Migration scripts** executed if needed (none required for current version)

## Deployment Steps

### ✅ Phase 1: Initial Deployment
- [ ] **Stop existing broker** if running:
  ```bash
  pkill -f "python.*start_server.py" || true
  pkill -f "gunicorn.*simp.server.http_server" || true
  ```
- [ ] **Clear PID file**: `rm -f data/broker.pid 2>/dev/null || true`
- [ ] **Verify clean state**: No processes listening on port 5555
- [ ] **Start broker in test mode**:
  ```bash
  python3.10 bin/start_server.py --debug
  ```
- [ ] **Verify startup**: Check logs for successful initialization
- [ ] **Test basic endpoints**:
  ```bash
  curl -s http://127.0.0.1:5555/health | jq .
  curl -s http://127.0.0.1:5555/agents | jq .
  ```
- [ ] **Stop test broker**: Ctrl+C

### ✅ Phase 2: Production Startup
- [ ] **Start production server**:
  ```bash
  # Option A: Using gunicorn (recommended for production)
  python3.10 bin/start_production.py --workers 4 --port 5555 --host 127.0.0.1
  
  # Option B: Using startup script
  bash bin/start_broker.sh
  ```
- [ ] **Verify persistence files created**:
  ```bash
  ls -la data/*.jsonl
  wc -l data/agent_registry.jsonl data/orchestration_plans.jsonl
  ```
- [ ] **Test persistence**:
  ```bash
  # Register test agent
  curl -X POST http://127.0.0.1:5555/agents/register \
    -H "Content-Type: application/json" \
    -d '{"agent_id": "test_prod_agent", "endpoint": "http://127.0.0.1:9999", "capabilities": ["ping"]}'
  
  # Verify agent appears in registry
  curl -s http://127.0.0.1:5555/agents | jq '. | has("test_prod_agent")'
  
  # Restart broker and verify agent persists
  pkill -f "python.*start_server.py"
  sleep 2
  bash bin/start_broker.sh
  sleep 3
  curl -s http://127.0.0.1:5555/agents | jq '. | has("test_prod_agent")'
  ```

### ✅ Phase 3: Integration Testing
- [ ] **Test agent registration/deregistration**:
  ```bash
  # Register multiple agents
  for i in {1..5}; do
    curl -X POST http://127.0.0.1:5555/agents/register \
      -H "Content-Type: application/json" \
      -d "{\"agent_id\": \"agent_$i\", \"endpoint\": \"http://127.0.0.1:999$i\", \"capabilities\": [\"ping\"]}"
  done
  
  # Verify all registered
  curl -s http://127.0.0.1:5555/agents | jq '. | length'
  
  # Deregister one
  curl -X POST http://127.0.0.1:5555/agents/deregister \
    -H "Content-Type: application/json" \
    -d '{"agent_id": "agent_3"}'
  
  # Verify removal
  curl -s http://127.0.0.1:5555/agents | jq '. | has("agent_3")'
  ```
- [ ] **Test intent routing with persistence**:
  ```bash
  # Send test intent
  curl -X POST http://127.0.0.1:5555/intents/route \
    -H "Content-Type: application/json" \
    -d '{"intent_type": "ping", "source_agent": "test_operator", "target_agent": "auto"}'
  
  # Verify intent recorded in ledger
  tail -5 data/task_ledger.jsonl | jq -s '.'
  ```
- [ ] **Test orchestration persistence**:
  ```bash
  # Create orchestration plan
  curl -X POST http://127.0.0.1:5555/orchestration/plan \
    -H "Content-Type: application/json" \
    -d '{"name": "test_prod_plan", "steps": [{"name": "step1", "intent_type": "ping"}]}'
  
  # Verify plan saved
  tail -5 data/orchestration_plans.jsonl | jq -s '.'
  ```

### ✅ Phase 4: Performance Verification
- [ ] **Monitor file sizes**:
  ```bash
  watch -n 5 'ls -lh data/*.jsonl'
  ```
- [ ] **Test concurrent operations** (run in parallel):
  ```bash
  # Concurrent agent registrations
  for i in {1..10}; do
    (curl -X POST http://127.0.0.1:5555/agents/register \
      -H "Content-Type: application/json" \
      -d "{\"agent_id\": \"concurrent_$i\", \"endpoint\": \"http://127.0.0.1:888$i\", \"capabilities\": [\"ping\"]}" &
    ) 2>/dev/null
  done
  wait
  
  # Verify no data corruption
  python3.10 -c "import json; data = [json.loads(line) for line in open('data/agent_registry.jsonl')]; print(f'Lines: {len(data)}')"
  ```
- [ ] **Check thread safety**: Verify no file corruption under load

## Post-Deployment Verification

### ✅ System Health Checks
- [ ] **Broker health endpoint**: Returns 200 OK
- [ ] **Agent registry**: Loads correctly on restart
- [ ] **Intent ledger**: Appends correctly under load
- [ ] **Orchestration plans**: Persist across restarts
- [ ] **Rate limiting**: Functions correctly (resets on restart)
- [ ] **Error handling**: Graceful degradation on disk full

### ✅ Monitoring Setup
- [ ] **Log monitoring** configured:
  ```bash
  # Monitor broker logs
  tail -f ~/bullbear/logs/simp_broker.log  # or configured log location
  
  # Monitor JSONL file growth
  watch -n 60 'wc -l data/*.jsonl'
  ```
- [ ] **Alerting configured** for:
  - Disk space below 10%
  - JSONL file corruption
  - Broker process down
  - High error rates
- [ ] **Metrics collection** enabled (if available)

### ✅ Backup Procedures
- [ ] **Regular backups scheduled**:
  ```bash
  # Daily backup script
  #!/bin/bash
  BACKUP_DIR="/backup/simp_$(date +%Y%m%d)"
  mkdir -p "$BACKUP_DIR"
  cp data/*.jsonl "$BACKUP_DIR/"
  cp data/broker.pid "$BACKUP_DIR/" 2>/dev/null || true
  echo "Backup completed: $BACKUP_DIR"
  ```
- [ ] **Backup verification** tested:
  ```bash
  # Verify backup integrity
  python3.10 -c "
  import json, sys, glob
  for f in glob.glob('/backup/simp_*/agent_registry.jsonl'):
      try:
          with open(f) as fp:
              for line in fp:
                  json.loads(line)
          print(f'✓ {f} valid')
      except Exception as e:
          print(f'✗ {f} invalid: {e}')
  "
  ```
- [ ] **Restore procedure** documented and tested

## Troubleshooting

### Common Issues

#### ❌ Broker fails to start
- **Check**: Port 5555 already in use
  ```bash
  lsof -i :5555
  ```
- **Fix**: Stop conflicting process or change port
- **Check**: Python 3.10 not available
  ```bash
  python3.10 --version
  ```
- **Fix**: Install Python 3.10 or update shebang

#### ❌ Persistence files not created
- **Check**: Data directory permissions
  ```bash
  ls -ld data/
  ```
- **Fix**: `chmod 755 data/`
- **Check**: Disk full
  ```bash
  df -h .
  ```
- **Fix**: Free disk space

#### ❌ JSONL file corruption
- **Symptoms**: Broker crashes on startup, JSON parse errors
- **Recovery**:
  ```bash
  # Backup corrupted file
  cp data/agent_registry.jsonl data/agent_registry.jsonl.corrupted
  
  # Try to repair (remove last incomplete line)
  head -n -1 data/agent_registry.jsonl.corrupted > data/agent_registry.jsonl
  
  # Or restore from backup
  cp /backup/simp_*/agent_registry.jsonl data/
  ```

#### ❌ High memory usage
- **Check**: IntentLedger growing too large
  ```bash
  wc -l data/task_ledger.jsonl
  ```
- **Mitigation**: Implement retention policy or file rotation

### Emergency Procedures

#### Immediate Shutdown
```bash
# Graceful shutdown
curl -X POST http://127.0.0.1:5555/control/shutdown 2>/dev/null || true

# Force shutdown
pkill -f "python.*start_server.py"
pkill -f "gunicorn.*simp.server.http_server"
rm -f data/broker.pid
```

#### Data Recovery
```bash
# Stop broker
pkill -f "python.*start_server.py"

# Restore from latest backup
LATEST_BACKUP=$(ls -td /backup/simp_* | head -1)
cp "$LATEST_BACKUP"/*.jsonl data/

# Start broker
bash bin/start_broker.sh
```

## Maintenance Schedule

### Daily
- [ ] Check disk space: `df -h .`
- [ ] Monitor JSONL file sizes: `wc -l data/*.jsonl`
- [ ] Verify backup completion
- [ ] Review error logs: `grep -i error ~/bullbear/logs/simp_broker.log | tail -20`

### Weekly
- [ ] Run validation: `python3.10 -m simp.tools.validate_jsonl data/`
- [ ] Test restore from backup
- [ ] Review performance metrics
- [ ] Rotate large JSONL files if needed

### Monthly
- [ ] Archive old JSONL files
- [ ] Update deployment documentation
- [ ] Review security settings
- [ ] Test disaster recovery procedure

## Appendices

### A. Configuration Reference

#### Broker Configuration (`config/config.py`)
```python
# Core settings
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 5555
DEBUG = False

# Persistence settings
AGENT_REGISTRY_PERSISTENCE_ENABLED = True
ORCHESTRATION_PERSISTENCE_ENABLED = True
INTENT_LEDGER_PATH = "data/task_ledger.jsonl"

# Security
FINANCIAL_OPS_LIVE_ENABLED = False  # MUST BE False for safety
REQUIRE_API_KEY = False  # Set to True for production
API_KEY = "your-secret-key-here"  # If REQUIRE_API_KEY = True

# Performance
MAX_INTENT_RECORDS = 10000  # In-memory cache size
INTENT_RECORD_TTL = 300  # Seconds
RATE_LIMIT_REQUESTS_PER_MINUTE = 60
```

#### Environment Variables
```bash
# Override configuration
export SIMP_BROKER_HOST="0.0.0.0"
export SIMP_BROKER_PORT="8080"
export SIMP_API_KEY="your-secret-key"
export SIMP_DEBUG="false"
export SIMP_LOG_LEVEL="info"
```

### B. File Locations
```
data/
├── agent_registry.jsonl      # Agent state (append-only events)
├── task_ledger.jsonl         # Intent delivery records
├── orchestration_plans.jsonl # Orchestration plan state
├── orchestration_log.jsonl   # Orchestration execution logs
├── financial_ops_proposals.jsonl  # Financial operation proposals
├── live_spend_ledger.jsonl   # Financial operations (if enabled)
├── rollback_log.jsonl        # Rollback operations
├── security_audit.jsonl      # Security audit trail
└── broker.pid               # Broker process ID
```

### C. Command Reference
```bash
# Start broker
bash bin/start_broker.sh
python3.10 bin/start_production.py --workers 4

# Check status
curl http://127.0.0.1:5555/health
curl http://127.0.0.1:5555/stats

# Monitor
tail -f ~/bullbear/logs/simp_broker.log
watch -n 5 'wc -l data/*.jsonl'

# Validate data
python3.10 -m simp.tools.validate_jsonl data/

# Backup
bash bin/backup_data.sh

# Restore
bash bin/restore_data.sh /backup/simp_20240414/
```

### D. Contact Information
- **Primary Operator**: [Name/Team]
- **Secondary Operator**: [Name/Team]
- **Emergency Contact**: [Phone/Email]
- **Documentation**: `docs/` directory
- **Issue Tracking**: [URL/System]

---

**Last Updated**: 2024-04-14  
**Version**: SIMP v0.7.0 with Enhanced Persistence  
**Deployment Environment**: Production  
**Persistence Status**: ✅ Enabled (AgentRegistry, OrchestrationManager, IntentLedger)