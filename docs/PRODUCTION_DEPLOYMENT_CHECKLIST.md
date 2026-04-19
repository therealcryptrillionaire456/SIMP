# SIMP System Production Deployment Checklist

## Overview
This checklist provides a comprehensive guide for deploying the SIMP system to production environments. The checklist covers deployment procedures, performance optimization, and operational monitoring.

## Pre-Deployment Requirements

### System Requirements
- [ ] **Python 3.10+** installed and verified
- [ ] **Minimum 4GB RAM** (8GB recommended for production)
- [ ] **Minimum 10GB disk space** (SSD recommended)
- [ ] **Network access** to required services (Ollama, databases, etc.)
- [ ] **Port availability**: 5555 (broker), 8050 (dashboard), 8771 (ProjectX)

### Dependencies Verification
- [ ] **Flask** installed (`pip install flask`)
- [ ] **requests** installed (`pip install requests`)
- [ ] **threading** and **json** modules available (stdlib)
- [ ] **pathlib** and **dataclasses** available (stdlib)

### Configuration Files
- [ ] **Environment variables** set:
  - `SIMP_API_KEY` (if using authentication)
  - `SIMP_REQUIRE_API_KEY` (true/false)
  - `FINANCIAL_OPS_LIVE_ENABLED` (false for production)
- [ ] **Configuration files** present:
  - `docs/routing_policy.json`
  - `data/` directory exists and is writable

## Deployment Procedures

### Step 1: Environment Setup
- [ ] Create production data directory: `mkdir -p /path/to/simp/data`
- [ ] Set proper permissions: `chmod 755 /path/to/simp/data`
- [ ] Backup existing data if present
- [ ] Verify directory structure:
  ```
  /path/to/simp/
  ├── data/
  │   ├── task_ledger.jsonl
  │   ├── agent_registry.jsonl
  │   ├── orchestration_plans.jsonl
  │   ├── financial_ops_proposals.jsonl
  │   └── ...
  ├── simp/
  │   ├── server/
  │   ├── orchestration/
  │   └── ...
  └── docs/
  ```

### Step 2: Service Installation
- [ ] Install SIMP system files to production location
- [ ] Create systemd service file for broker:
  ```ini
  [Unit]
  Description=SIMP Broker Service
  After=network.target

  [Service]
  WorkingDirectory=/path/to/simp
  ExecStart=/usr/bin/python3.10 -m simp.server.http_server
  Restart=always
  RestartSec=10
  User=simp-user
  Group=simp-user

  [Install]
  WantedBy=multi-user.target
  ```
- [ ] Create systemd service file for dashboard:
  ```ini
  [Unit]
  Description=SIMP Dashboard Service
  After=network.target

  [Service]
  WorkingDirectory=/path/to/simp/dashboard
  ExecStart=/usr/bin/python3.10 -m uvicorn server:app --host 0.0.0.0 --port 8050
  Restart=always
  RestartSec=10
  User=simp-user
  Group=simp-user

  [Install]
  WantedBy=multi-user.target
  ```

### Step 3: Configuration Setup
- [ ] Configure broker settings in `simp/server/http_server.py`:
  - Set `host` to appropriate bind address
  - Set `port` to 5555
  - Configure API key requirements
- [ ] Configure dashboard settings in `dashboard/server.py`:
  - Set `host` to appropriate bind address
  - Set `port` to 8050
- [ ] Configure ProjectX settings:
  - Verify port 8771 is accessible
  - Configure security settings

### Step 4: Data Migration
- [ ] Backup existing data directories
- [ ] Copy data files to production location:
  ```bash
  cp -r data/ /path/to/simp/data/
  ```
- [ ] Verify file permissions:
  ```bash
  chmod 644 /path/to/simp/data/*.jsonl
  chown simp-user:simp-user /path/to/simp/data/*.jsonl
  ```
- [ ] Test data integrity:
  ```bash
  python3.10 -c "
  from pathlib import Path
  data_dir = Path('data')
  for file in data_dir.glob('*.jsonl'):
      with open(file, 'r') as f:
          lines = sum(1 for _ in f)
      print(f'{file.name}: {lines} lines')
  ```

## Post-Deployment Verification

### Service Health Checks
- [ ] **Broker Health**: `curl -s http://localhost:5555/health`
  - Expected: `{"status": "healthy", "timestamp": "..."}`
- [ ] **Dashboard Health**: `curl -s http://localhost:8050/`
  - Expected: HTML response with dashboard
- [ ] **ProjectX Health**: `curl -s http://localhost:8771/health`
  - Expected: Health check response
- [ ] **Agent Registry**: `curl -s http://localhost:5555/agents`
  - Expected: List of registered agents

### Persistence Verification
- [ ] **File Persistence**: Run persistence monitor:
  ```bash
  python3.10 tools/persistence_monitor.py --status
  ```
- [ ] **Orchestration Persistence**: Verify plans survive restart:
  ```bash
  python3.10 -c "
  from simp.orchestration.orchestration_manager import OrchestrationManager
  om = OrchestrationManager()
  plans = om.list_plans()
  print(f'Plans loaded: {len(plans)}')
  "
  ```
- [ ] **Agent Registry Persistence**: Verify agents survive restart:
  ```bash
  python3.10 -c "
  from simp.server.agent_registry import AgentRegistry
  ar = AgentRegistry()
  agents = ar.list_agents()
  print(f'Agents loaded: {len(agents)}')
  ```

### Performance Baseline
- [ ] **Response Time**: Measure broker response time:
  ```bash
  time curl -s http://localhost:5555/health
  ```
- [ ] **File Operations**: Test persistence performance:
  ```bash
  python3.10 tools/persistence_monitor.py --benchmark --iterations 100
  ```
- [ ] **Memory Usage**: Monitor memory consumption:
  ```bash
  ps aux | grep python3.10 | grep simp
  ```

## Monitoring and Alerting

### System Monitoring
- [ ] **File Growth Monitoring**: Set up cron job:
  ```bash
  */30 * * * * /usr/bin/python3.10 /path/to/simp/tools/persistence_monitor.py --status >> /var/log/simp-monitor.log 2>&1
  ```
- [ ] **Service Monitoring**: Set up systemd service monitoring
- [ ] **Log Rotation**: Configure logrotate for SIMP logs

### Alert Thresholds
- [ ] **File Size**: Alert when any JSONL file exceeds 100MB
- [ ] **Response Time**: Alert when broker response > 1000ms
- [ ] **Error Rate**: Alert when error rate > 5%
- [ ] **Memory Usage**: Alert when memory usage > 80%

## Maintenance Procedures

### Regular Maintenance
- [ ] **Daily**: Check service health and file growth
- [ ] **Weekly**: Review performance metrics and rotate logs
- [ ] **Monthly**: Archive old data files and test recovery
- [ ] **Quarterly**: Review security updates and test disaster recovery

### Disaster Recovery
- [ ] **Backup Strategy**: Daily backups of data directory
- [ ] **Recovery Procedure**: Step-by-step recovery process
- [ ] **Test Recovery**: Regular recovery testing

## Troubleshooting

### Common Issues
- [ ] **Service Won't Start**: Check port availability and permissions
- [ ] **File Permission Errors**: Verify data directory permissions
- [ ] **Memory Issues**: Monitor memory usage and optimize
- [ ] **Performance Degradation**: Check file sizes and implement rotation

### Debug Commands
- [ ] **Broker Debug**: `python3.10 -m simp.server.http_server --debug`
- [ ] **Dashboard Debug**: `python3.10 -m uvicorn server:app --reload --debug`
- [ ] **Persistence Debug**: `python3.10 tools/persistence_monitor.py --monitor --interval 10`

## Deployment Checklist Completion

### Final Verification
- [ ] All services are running and healthy
- [ ] All persistence operations are working correctly
- [ ] Performance metrics are within acceptable ranges
- [ ] Monitoring and alerting are configured
- [ ] Documentation is updated

### Go/No-Go Decision
- [ ] **GO**: All checks passed, system is ready for production
- [ ] **NO-GO**: Issues found, resolve before deployment

---

**Last Updated**: 2025-06-20
**Version**: 1.0
**Maintainer**: SIMP System Team