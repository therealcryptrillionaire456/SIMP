# Failure Playbooks — Day 2

## Playbook 1: Stale Signal (Decision Journal)

**Symptom**: Verifier reports `FAIL signal_freshness age_s > 60`
**Severity**: Sev3 (Sev2 if >300s)

**Check**:
```bash
# 1. Is signal_cycle running?
pgrep -f "signal_cycle" | head -1 || echo "NOT RUNNING"

# 2. Read last decision timestamp
tail -1 state/decision_journal.ndjson | python3 -c "import sys,json; print(json.load(sys.stdin)['created_at'])"

# 3. Compare to now
python3 -c "from datetime import datetime,timedelta; print(f'{(datetime.utcnow() - datetime.fromisoformat(open(\"state/decision_journal.ndjson\").readlines()[-1].strip().split(chr(10))[-1].split(chr(34)+chr(44)+chr(34))[0].strip(chr(34)))).total_seconds()}s age')"
```

**Remediation**:
```bash
# Restart signal cycle
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
nohup python3 scripts/signal_cycle.py --interval 45 > /dev/null 2>&1 &
```

---

## Playbook 2: Gate4 Pipeline Stale

**Symptom**: No new trade log entries >300s
**Severity**: Sev2

**Check**:
```bash
# 1. Last trade timestamp
tail -1 logs/gate4_trades.jsonl | python3 -c "import sys,json; print(json.load(sys.stdin)['ts'])"

# 2. Is gate4 consumer running?
pgrep -f "gate4_inbox_consumer" | head -1 || echo "NOT RUNNING"

# 3. Is signal bridge running?
pgrep -f "quantum_signal_bridge" | head -1 || echo "NOT RUNNING"

# 4. Inject a manual test signal
python3 scripts/inject_quantum_signal.py --asset BTC-USD --side buy --usd 1.00
sleep 5
ls -t data/inboxes/gate4_real/_failed/ data/inboxes/gate4_real/_processed/ | head -3
```

**Remediation**:
```bash
# Restart gate4 consumer
PID=$(pgrep -f "gate4_inbox_consumer" | head -1)
kill $PID 2>/dev/null
sleep 2
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
./venv_gate4/bin/python gate4_inbox_consumer.py &

# Restart signal bridge if needed
PID=$(pgrep -f "quantum_signal_bridge" | head -1) 
if [ -n "$PID" ]; then kill $PID; sleep 2; fi
./venv_gate4/bin/python quantum_signal_bridge.py --interval 30 &
```

---

## Playbook 3: Broker Down

**Symptom**: `curl http://127.0.0.1:5555/health` fails
**Severity**: Sev1 (revenue broken)

**Check**:
```bash
curl -sf http://127.0.0.1:5555/health || echo "BROKER DOWN"
pgrep -f "bin/start_server" | head -1 || echo "NO BROKER PROCESS"
```

**Remediation**:
```bash
# Full restart
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
bash startall.sh
# Wait 60s for health checks
```

**If broker fails to start**:
```bash
# Check port conflict
lsof -i :5555
# Check venv
ls -la venv_gate4/bin/python
# Check dependency
./venv_gate4/bin/python -c "from simp.server.http_server import create_http_server; print('OK')"
```

---

## Playbook 4: Policy-Blocked Trades

**Symptom**: Trades fail with `policy_blocked: Exchange 'coinbase'`
**Severity**: Sev2 (blocked live, expected in shadow)

**Check**:
```bash
tail -3 logs/gate4_trades.jsonl | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l.strip())
    r=d.get('result','')
    if 'policy_blocked' in r:
        print(f'BLOCKED: {d[\"symbol\"]} {d[\"side\"]} — {r[:80]}')
"
```

**Evaluation**:
- In **shadow mode**: Expected behavior. Policy is correctly protecting live exchanges.
- In **fully_live mode**: Investigate exchange allowlist config.

**Remediation (fully_live only)**:
```bash
# 1. Add coinbase to live exchanges
export SIMP_LIVE_TRADING_ENABLED=true
export SIMP_LIVE_EXCHANGES=coinbase
# 2. Or route through paper exchange (modify gate4_inbox_consumer.py line 690)
```

---

## Playbook 5: Decision Adapter Not Recording

**Symptom**: Decision journal empty or stalled
**Severity**: Sev2

**Check**:
```bash
pgrep -f "state/decision_adapter" | head -1 || echo "NOT RUNNING"
wc -l state/decision_journal.ndjson
```

**Remediation**:
```bash
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
python3 state/decision_adapter.py &
```

---

## Playbook 6: Kill Switch Activated

**Symptom**: `state/KILL` file exists
**Severity**: Sev1

**Response**:
```bash
# 1. Verify it's not a false positive
cat state/KILL

# 2. Understand why by checking decision journal
tail -5 state/decision_journal.ndjson | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l.strip())
    if d.get('policy_result',{}).get('status') in ('kill_switch','blocked'):
        print(json.dumps(d, indent=2)[:200])
"

# 3. Acknowledge (read-only for non-commander)
# 4. Only commander may remove: rm state/KILL
```

---

## Playbook 7: Background Loop Failures

**Symptom**: Snapshot or verifier loop not producing output
**Severity**: Sev3

**Check**:
```bash
# Snapshot freshness
ls -t state/metrics/ | head -3
# Verifier freshness
cat state/metrics/verify.last.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'green={d[\"green\"]} at {d[\"started_at\"]}')"
```

**Remediation**:
```bash
# Restart snapshot loop
pkill -f "runtime_snapshot.py --loop"
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp
nohup python3 scripts/runtime_snapshot.py --loop --interval 30 > /dev/null 2>&1 &

# Restart verifier loop
pkill -f "verify_revenue_path.py --loop"
nohup bash -c 'while true; do python3 scripts/verify_revenue_path.py --json > state/metrics/verify.last.json 2>/dev/null; sleep 60; done' > /dev/null 2>&1 &
```

---

## Escalation Ladder

| Severity | Response Time | Notify | Action |
|---|---|---|---|
| Sev1 | Immediate | Commander | Pause everything, fix broker or kill switch |
| Sev2 | <15 min | Commander | Remediate within 30 min or escalate |
| Sev3 | <60 min | Log | Fix within shift or document |
| Sev4 | <1 shift | Log | Document for next shift |
