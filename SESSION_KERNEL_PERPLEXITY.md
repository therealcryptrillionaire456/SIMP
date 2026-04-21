# SIMP Session Kernel — Perplexity Computer
**Paste this at the start of a new Perplexity Computer session.**

---

## Who I Am / What We're Building
I am Perplexity Computer, working with Kasey on SIMP — "the HTTP of agent protocols." SIMP is a production multi-agent coordination system at v0.4.0 with 451 passing tests. ProjectX is SIMP's native self-maintaining internal agent.

## Repository
- **Repo**: https://github.com/therealcryptrillionaire456/SIMP
- **Branch**: `feat/public-readonly-dashboard`
- **Local SIMP path**: `/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp`
- **Bullbear path**: `/Users/kaseymarcelle/bullbear/` (live system, separate codebase)
- **ProjectX path**: `/Users/kaseymarcelle/ProjectX/`
- **User python**: always `python3.10` (not python3)

## Live System Architecture
```
BROKER: ~/bullbear/simp_coordination_server.py → port 5555
COWORK: ~/bullbear/ claude_cowork Flask app → port 8767
RUNS API: ~/bullbear/ → port varies
DASHBOARD: SIMP repo dashboard/server.py → port 8050 (not yet started)
```

## What Was Completed (Do Not Redo)
- **25 sprints** of SIMP hardening committed to repo (Sprints 1-25)
- **451 tests passing** locally on user's Mac
- **v0.4.0** released with PROTOCOL_SPEC.md, full README, canonical intent schema
- **ProjectX** has: 4-tier action space, safe_execute, log_action, abort, sync_knowledge, check_protocol_health
- **protocol_updater.py** syntax error FIXED (facts: parameter added, compiles clean)
- **simp_brain/protocol_updater.py** committed to SIMP repo with full implementation
- **cowork_bridge.py** committed to SIMP repo at bin/cowork_bridge.py (port 8767 adapter)

## System State Right Now
- Broker (port 5555): bullbear `simp_coordination_server`, 8 agents registered
- claude_cowork (port 8767): running, 3-4 pending inbox tasks
- Cowork bridge 422 issue: the bullbear bridge has a different intent schema than SIMP broker sends — **UNRESOLVED, first thing to fix**
- To restart everything: `bash bin/restart_all.sh` from the SIMP repo

## First Task in a New Session
1. Load skill: `coding-and-data`
2. Read `~/bullbear/simp_coordination_server.py` to get exact intent schema the broker accepts at `/intents/route`
3. Read `~/bullbear/` cowork bridge source to get exact schema `/intents/handle` expects
4. Fix the schema mismatch so `curl http://127.0.0.1:5555/intents/route` successfully delivers to claude_cowork
5. Then queue all pending work through the live broker

## How to Queue Tasks (Current Working Method)
**Direct inbox** (bypasses broker, always works):
```bash
python3 -c "
import json, uuid
from datetime import datetime, timezone
from pathlib import Path
inbox = Path.home() / 'bullbear/signals/cowork_inbox'
inbox.mkdir(parents=True, exist_ok=True)
intent = {
    'intent_id': 'intent:perplexity_research:' + str(uuid.uuid4())[:8],
    'source_agent': 'perplexity_research',
    'target_agent': 'claude_cowork',
    'intent_type': 'code_task',
    'priority': 'high',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'params': {'task': 'YOUR TASK HERE'}
}
f = inbox / f\"{intent['intent_id'].replace(':', '_')}.json\"
f.write_text(json.dumps(intent, indent=2))
print('Queued:', f.name)
"
```

**Via broker** (schema TBD — fix this first):
```bash
curl -X POST http://127.0.0.1:5555/intents/route \
  -H "Content-Type: application/json" \
  -d '{"intent_id":"...","source_agent":"perplexity_research","target_agent":"claude_cowork","intent_type":"code_task","params":{"task":"..."}}'
```

## Pending Tasks Queue (in priority order)
1. **CRITICAL**: Fix broker→cowork 422 schema mismatch
2. **HIGH**: Process 3-4 pending inbox tasks (protocol_updater fix already queued)
3. **HIGH**: Start dashboard (python3.10 dashboard/server.py) and verify WebSocket
4. **MEDIUM**: Merge feat/public-readonly-dashboard → main via PR
5. **MEDIUM**: Wire ProjectX sync_knowledge() into autonomous loop
6. **LOW**: Start Gemma4 via Ollama if installed (bin/start_gemma4_agent.py)

## Key Files
```
SIMP repo:
  simp/models/canonical_intent.py   — 30 intent types, canonical schema
  simp/projectx/computer.py         — ProjectX action layer (sync_knowledge, check_protocol_health)
  simp_brain/protocol_updater.py    — ProjectX KB updater (fixed)
  bin/restart_all.sh                — One-command system restart
  bin/queue_intent.sh               — Queue any task from CLI
  bin/cowork_bridge.py              — SIMP-native cowork bridge (not yet deployed)
  PROTOCOL_SPEC.md                  — Formal SIMP protocol spec
  SPRINT_LOG.md                     — Full 25-sprint history

Bullbear system:
  ~/bullbear/simp_coordination_server.py  — LIVE broker (port 5555)
  ~/bullbear/logs/simp_broker.log         — Broker logs
  ~/bullbear/logs/cowork_bridge.log       — Bridge logs
  ~/bullbear/signals/cowork_inbox/        — File inbox for claude_cowork
  ~/bullbear/data/agent_registry.json     — 8 registered agents
```

## User Preferences
- Always use `python3.10` not `python3`
- Never commit broken experiments or secrets
- All work on branch `feat/public-readonly-dashboard`
- User runs Mac, has Gemma4 locally, wants system to run offline-capable
- ProjectX is SIMP's native agent kernel — every capability must serve a SIMP-facing purpose
