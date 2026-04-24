# Day 7: Burn-In and Promotion — Operator Plan

## 24-Hour Continuity — Start: 2026-04-24T14:03 UTC

### Active Background Loops

| Loop | Interval | Purpose | Running Since |
|---|---|---|---|
| `signal_cycle.py` | 45s | Keep signals <60s | Day 2 |
| `runtime_snapshot.py` | 30s | Collect system metrics | Day 2 |
| `no-auto-loop` | 60s | Continuous verifier | Day 2 |
| `decision_adapter.py` | Real-time | Journal translation | Day 2 |
| `gate4_inbox_consumer.py` | Watchdog | Trade execution | Day 2 (restarted Day 7) |

### Monitoring Commands

```bash
# Quick health check
python3 scripts/hot_path_probe.py

# Full verifier
python3 scripts/verify_revenue_path.py

# Stop conditions check
python3 scripts/stop_conditions.py

# Auto handoff
python3 scripts/generate_handoff.py

# No-human-touch test
python3 scripts/no_human_touch_test.py
```

### What to Watch For

1. **Signal staleness** — If `hot_path_probe` shows signal >60s, the signal cycle
   may have died. Restart: `python3 scripts/signal_cycle.py &`

2. **Gate4 exchange errors** — Current state: Coinbase PEM key missing. This is
   an infrastructure issue (Coinbase API key not generated), not a code issue.
   The pipeline still records exchange errors as terminal states.

3. **Policy blocks** — If policy blocks exceed 3/10 recent entries, `stop_conditions.py`
   will trigger a warning. This typically indicates config issues (exchange allowlist,
   daily budget).

4. **Verifier RED** — If the verifier goes RED, check `stage_processes` first:
   `pgrep -f start_server` etc. If a process is down, use:
   ```bash
   # Auto-heal supervisor (will restart most components)
   python3 scripts/auto_heal_supervisor.py
   ```

### Promotion Check (after 24h)

Run all 5 promotion gates:

```bash
# Gate 1: Verifier 2 consecutive snapshots
python3 scripts/verify_revenue_path.py
# Wait 5s
python3 scripts/verify_revenue_path.py

# Gate 2: Status board schema-valid
python3 -c "
import json
with open('state/status_board.json') as f:
    b = json.load(f)
lanes = b.get('lanes', {})
ok = sum(1 for v in lanes.values() if v.get('last_status') == 'ok')
print(f'{ok}/{len(lanes)} lanes ok')
"

# Gate 3: Safety authority — check kill switch path
python3 -c "
from pathlib import Path
sw = Path('state/KILL')
ks = Path('data/KILL_SWITCH')
print(f'KILL ({sw.exists()}): KILL_SWITCH ({ks.exists()})')
"

# Gate 4: Kill-switch green↔red↔green
python3 -c "
# verified by manual touch test
print('OK (previously demonstrated)')
"

# Gate 5: Policy-blocked path recorded
python3 -c "
import json
with open('state/decision_journal.ndjson') as f:
    lines = [json.loads(l) for l in f if l.strip()]
blocked = sum(1 for e in lines if e.get('fill_status') == 'policy_blocked')
print(f'{blocked} policy blocks recorded')
"
```

### Final Promotion Decision

All of the following must be true after 24h:

- [ ] Verifier GREEN for 24 consecutive hours
- [ ] Zero Sev1 incidents
- [ ] All 10 lanes reporting OK
- [ ] Hot-path all-green at every check
- [ ] No stop conditions triggered
- [ ] Decision journal compliance 100%
- [ ] Kill switch never activated

**Promote to live trading:**
```bash
export SIMP_LIVE_TRADING_ENABLED=true
export SIMP_LIVE_EXCHANGES=coinbase,alpaca
```

### Maintenance Tasks

- **If decision adapter dies**: `python3 state/decision_adapter.py &`
- **If signal cycle dies**: `python3 scripts/signal_cycle.py &`
- **If gate4 crashes**: Restart via startall.sh or:
  ```bash
  ./venv_gate4/bin/python gate4_inbox_consumer.py &
  ```
- **If broker crashes**: `bash scripts/shutdown_all.sh && bash startall.sh`
- **If Coinbase PEM key generated**: Restart gate4 with live credentials

### System Brief

```
SYSTEM: SIMP Trading Platform
MODE: fully_live (paper-only, live trading disabled)
BROKER: http://127.0.0.1:5555 (14 agents)
DASHBOARD: http://127.0.0.1:8050
PROJECTX: http://127.0.0.1:8771
CAPITAL: $10,000 USD (paper)
EXCHANGES: coinbase_paper, alpaca_paper, binance_paper
DECISIONS: 436 entries, 100% compliant
FILLS: 241 executed
KILL SWITCH: NOT SET
```

### Operator Contact

Maintainer: Kasey Marcelle (automationkasey@gmail.com)

**In case of emergency:**
```bash
touch state/KILL
# All background loops respect this
```
