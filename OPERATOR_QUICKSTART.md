# SIMP Profit System - Operator Quick Start

## 🚀 5-Minute Setup

### 1. Start the System:
```bash
# Navigate to SIMP directory
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp

# Start the profit system
python3.10 execute_profit_system.py
```

### 2. Access Dashboard:
Open your browser to: http://127.0.0.1:8050

### 3. Monitor System Health:
```bash
# Check broker health
curl http://127.0.0.1:5555/health

# List active agents
curl http://127.0.0.1:5555/agents
```

## 📊 Dashboard Overview

### Main Panels:
1. **System Health**: Green = operational, Red = issues
2. **Active Agents**: Shows all registered agents
3. **Trade Activity**: Real-time trade execution
4. **P&L Summary**: Profit/loss tracking
5. **Safety Status**: Safety mechanism status

### Key Metrics to Monitor:
- **Agent Count**: Should show 5+ agents
- **Trade Volume**: Number of trades executed
- **Net P&L**: Cumulative profit/loss
- **Safety Status**: All checks should be green

## ⚡ Quick Commands

### System Control:
```bash
# Start profit system
python3.10 execute_profit_system.py

# Run trade tests
python3.10 test_trade_execution.py

# Check system status
python3.10 -c "import requests; print(requests.get('http://127.0.0.1:5555/health').json())"
```

### Emergency Procedures:
```bash
# Emergency stop (Ctrl+C in running script)
# OR kill processes:
pkill -f "python.*execute_profit_system"
pkill -f "python.*dashboard"
```

## 🎯 Daily Operations

### Morning Checklist:
1. ✅ Start system: `python3.10 execute_profit_system.py`
2. ✅ Verify dashboard: http://127.0.0.1:8050
3. ✅ Check agent status: All 5 agents should be online
4. ✅ Review overnight trades in P&L ledger

### During Day:
1. Monitor dashboard for trade activity
2. Check system logs for any errors
3. Verify safety mechanisms are active
4. Review P&L performance

### Evening Checklist:
1. Review daily P&L report
2. Check system logs for issues
3. Ensure all safety checks passed
4. Document any system changes

## 🔍 Troubleshooting

### Common Issues & Solutions:

#### 1. Dashboard Not Loading
```bash
# Check if dashboard is running
curl -I http://127.0.0.1:8050

# Restart dashboard
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
python3.10 -m dashboard.server &
```

#### 2. Broker Not Responding
```bash
# Check broker health
curl http://127.0.0.1:5555/health

# Restart broker
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
python3.10 -m simp.server.broker &
```

#### 3. No Trade Activity
```bash
# Check QuantumArb agent
curl http://127.0.0.1:5555/agents | grep quantumarb

# Test trade execution
python3.10 test_trade_execution.py
```

#### 4. P&L Not Updating
```bash
# Check ledger files
ls -la data/*.jsonl

# Verify file permissions
chmod 644 data/*.jsonl
```

## 📈 Performance Monitoring

### Key Performance Indicators:
1. **Trade Execution Speed**: < 5 seconds per trade
2. **System Uptime**: > 99% target
3. **P&L Accuracy**: 100% reconciliation
4. **Safety Compliance**: 100% checks passing

### Monitoring Locations:
- **Real-time**: Dashboard at http://127.0.0.1:8050
- **Historical**: `data/system_status_report.json`
- **Trade Logs**: `data/live_spend_ledger.jsonl`
- **System Logs**: Console output and log files

## 🛡️ Safety First

### Safety Features:
1. **Dry-Run Mode**: Default for all new deployments
2. **Position Limits**: Prevents overexposure
3. **Emergency Stop**: Ctrl+C or kill command
4. **Audit Trail**: All actions logged for review

### Safety Checklist:
- [ ] Dry-run mode enabled for initial testing
- [ ] Position limits configured appropriately
- [ ] Emergency stop procedures documented
- [ ] Regular backup of ledger files

## 📞 Support

### Immediate Issues:
1. Check this quickstart guide
2. Review system logs in console
3. Check dashboard for error indicators

### Documentation:
- Full documentation: `PROFIT_SYSTEM_READY.md`
- System architecture: Various README files
- API documentation: Broker endpoints

### Contact:
- System logs contain detailed error information
- Dashboard shows real-time status
- Ledger files contain complete audit trail

---

**Remember**: The system is designed for safety first. All trades start in sandbox mode, and safety mechanisms prevent excessive risk. Monitor the dashboard regularly and review P&L reports daily.