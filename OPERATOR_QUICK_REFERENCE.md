# OPERATOR QUICK REFERENCE
## SIMP Live Trading System with BRP Protection

## 🚀 QUICK START

### System URLs:
- **Dashboard**: http://127.0.0.1:5555/dashboard/ui
- **Read-Only Dashboard API**: http://127.0.0.1:8050
- **Broker API**: http://127.0.0.1:5555
- **Health Check**: http://127.0.0.1:5555/health

### Key Processes:
- **Enhanced QuantumArb Agent**: PID `53461` (check with `ps aux | grep quantumarb_enhanced`)
- **SIMP Broker**: Running on port 5555

## 📊 SYSTEM STATUS COMMANDS

### Check System Health:
```bash
# Broker health
curl http://127.0.0.1:5555/health

# List all agents
curl http://127.0.0.1:5555/agents

# System stats
curl http://127.0.0.1:5555/stats
```

### Check Agent Status:
```bash
# Check if agent is running
ps aux | grep quantumarb_enhanced

# View agent logs
tail -f logs/quantumarb/agent_console.log

# Check BRP evaluations
tail -f logs/quantumarb/brp/evaluations.jsonl
```

## 🛡️ BRP PROTECTION

### BRP Modes:
- **ENFORCED**: Can block trades (current mode)
- **ADVISORY**: Warns but doesn't block
- **SHADOW**: Logs only, no blocking
- **DISABLED**: No BRP protection

### Check BRP Status:
```bash
# Read-only dashboard BRP summary
curl -s http://127.0.0.1:8050/api/brp/status | python3 -m json.tool

# Recent BRP evaluations with predictive/multimodal metadata
curl -s "http://127.0.0.1:8050/api/brp/evaluations?limit=10" | python3 -m json.tool

# Adaptive rules learned from observations
curl -s http://127.0.0.1:8050/api/brp/adaptive-rules | python3 -m json.tool

# Condensed operator BRP insights
curl -s "http://127.0.0.1:8050/api/brp/insights?limit=10" | python3 -m json.tool

# Count BRP evaluations
wc -l logs/quantumarb/brp/evaluations.jsonl

# View recent BRP decisions
tail -10 logs/quantumarb/brp/evaluations.jsonl | python3 -m json.tool

# Check BRP statistics
grep -c '"decision":"BLOCK"' logs/quantumarb/brp/evaluations.jsonl
grep -c '"decision":"ALLOW"' logs/quantumarb/brp/evaluations.jsonl
```

## 💰 TRADING OPERATIONS

### Send Test Intent:
```bash
# Create test intent
python3.10 -c "
import json, uuid
intent = {
    'intent_type': 'evaluate_arb',
    'source_agent': 'operator',
    'target_agent': 'quantumarb_enhanced',
    'intent_id': str(uuid.uuid4()),
    'payload': {
        'ticker': 'BTC-USD',
        'direction': 'long',
        'confidence': 0.8,
        'horizon_minutes': 5
    }
}
with open('test_intent.json', 'w') as f:
    json.dump(intent, f, indent=2)
print('Test intent created: test_intent.json')
"

# Send to agent
cp test_intent.json data/inboxes/quantumarb_enhanced/
```

### Check Trade Results:
```bash
# Check outbox for responses
ls -la data/outboxes/quantumarb_enhanced/

# View P&L ledger
python3.10 -c "
from simp.organs.quantumarb.pnl_ledger import get_default_ledger
ledger = get_default_ledger()
print('Total P&L entries:', ledger.get_ledger_info()['entry_count'])
"
```

## ⚠️ EMERGENCY PROCEDURES

### Immediate Stop:
```bash
# Stop the enhanced agent
kill 53461  # Replace with actual PID

# Alternative: Use kill command
pkill -f "quantumarb_agent_enhanced"

# Verify stopped
ps aux | grep quantumarb_enhanced
```

### BRP Lockdown:
```bash
# Set BRP to maximum restriction
python3.10 -c "
from simp.organs.quantumarb.brp_integration import set_brp_mode
from simp.security.brp_models import BRPMode
set_brp_mode(BRPMode.ENFORCED)
print('BRP set to ENFORCED mode')
"
```

### System Recovery:
```bash
# Restart the system
./activate_live_trading.sh

# Or start agent only
./start_quantumarb_enhanced.sh
```

## 📈 MONITORING

### Key Log Files:
- `logs/quantumarb/agent_console.log` - Agent activity
- `logs/quantumarb/brp/evaluations.jsonl` - BRP decisions
- `logs/quantumarb/brp/trade_outcomes.jsonl` - Trade results
- `logs/quantumarb/brp/emergency_stops.jsonl` - Emergency events

### Dashboard Metrics to Watch:
1. **Agents Online** - Should be 4
2. **Pending Intents** - Should be low/none
3. **BRP Decisions** - Check for BLOCK decisions
4. **Trade Execution** - Monitor success/failure rates
5. **BRP Insights** - Review `/api/brp/status` and `/api/brp/insights` for elevated decisions, top threat tags, and active adaptive rules

## 🔧 TROUBLESHOOTING

### Common Issues:

#### Agent Not Processing Intents:
```bash
# Check inbox
ls -la data/inboxes/quantumarb_enhanced/

# Check agent logs
tail -50 logs/quantumarb/agent_console.log

# Restart agent
pkill -f "quantumarb_agent_enhanced"
./start_quantumarb_enhanced.sh
```

#### BRP Not Evaluating:
```bash
# Check BRP module
python3.10 -c "import simp.organs.quantumarb.brp_integration; print('OK')"

# Check logs
tail -f logs/quantumarb/brp/evaluations.jsonl
```

#### Dashboard Not Accessible:
```bash
# Check broker
curl http://127.0.0.1:5555/health

# Restart broker if needed
./bin/start_broker.sh
```

## 📋 DAILY CHECKLIST

### Morning Check:
- [ ] System health: `curl http://127.0.0.1:5555/health`
- [ ] Agent status: `ps aux | grep quantumarb_enhanced`
- [ ] BRP logs: `tail -5 logs/quantumarb/brp/evaluations.jsonl`
- [ ] P&L: Check dashboard or ledger

### Throughout Day:
- [ ] Monitor dashboard for anomalies
- [ ] Check for BRP BLOCK decisions
- [ ] Review trade execution success rate
- [ ] Monitor system resource usage

### End of Day:
- [ ] Review daily P&L
- [ ] Check BRP statistics
- [ ] Backup important logs
- [ ] Document any issues

## 🎯 KEY PERFORMANCE INDICATORS

### Trading KPIs:
- **Success Rate**: > 95% of trades should succeed
- **BRP Block Rate**: < 5% (unless threat detected)
- **Execution Time**: < 2 seconds per trade
- **P&L**: Positive daily P&L target

### System KPIs:
- **Uptime**: > 99.9%
- **Agent Responsiveness**: < 1 second
- **BRP Evaluation Time**: < 100ms
- **Error Rate**: < 0.1%

## 📞 SUPPORT

### Immediate Issues:
1. Check this quick reference guide
2. Review relevant log files
3. Restart affected component
4. Document the issue

### Escalation:
- System logs: `logs/quantumarb/`
- BRP logs: `logs/quantumarb/brp/`
- Configuration: `live_trading_config.json`
- Activation report: `system_activation_report.txt`

---

*Last Updated: System Activation - April 13, 2026*  
*System Version: SIMP-BRP-LIVE v1.0*  
*Emergency Contact: System Administrator*
