# SIMP Flock Operator Runbook

## Prerequisites
- macOS with Python 3.10+
- Git repo checked out at `feat/public-readonly-dashboard`
- Virtual environment activated: `source .venv/bin/activate`
- Required Python packages: `flask`, `httpx`, `fastapi`, `uvicorn`, `starlette`, `pydantic`

## Quick Start (Full System)

```bash
# 1. Activate venv
source .venv/bin/activate

# 2. Start broker (background)
python bin/start_server.py &

# 3. Wait for broker to be ready
sleep 3
curl -sf http://127.0.0.1:5555/health | python3 -m json.tool

# 4. Register all agents
bash bin/register_agents.sh

# 5. Start cowork bridge (background)
python bin/cowork_bridge.py &

# 6. Start dashboard (background)
python dashboard/server.py &

# 7. Verify all services
bash bin/broker_status.sh
```

## Start Individual Components

### Broker
```bash
# Foreground (see logs in terminal):
python bin/start_server.py

# Or via launchd (macOS):
launchctl load ~/Library/LaunchAgents/com.simp.broker.plist

# Default: http://127.0.0.1:5555
# Health check:
curl -sf http://127.0.0.1:5555/health | python3 -m json.tool
```

### Dashboard
```bash
# Foreground:
python dashboard/server.py

# Or via uvicorn directly:
uvicorn dashboard.server:app --host 0.0.0.0 --port 8050

# Default: http://0.0.0.0:8050
# Requires broker to be running (proxies broker endpoints)
# Health check:
curl -sf http://127.0.0.1:8050/health | python3 -m json.tool

# Environment variables:
#   SIMP_BROKER_URL=http://127.0.0.1:5555  (broker to proxy)
#   DASHBOARD_HOST=0.0.0.0                  (bind host)
#   DASHBOARD_PORT=8050                      (bind port)
#   POLL_INTERVAL=5                          (broker poll seconds)
```

### Cowork Bridge
```bash
# Foreground:
python bin/cowork_bridge.py

# With custom paths:
python bin/cowork_bridge.py \
    --port 8767 \
    --repo-path "$(pwd)" \
    --inbox-dir "$(pwd)/data/inboxes/claude_cowork" \
    --outbox-dir "$(pwd)/data/outboxes/claude_cowork" \
    --tmp-dir "$(pwd)/data/tmp"

# Or via launchd (macOS):
launchctl load ~/Library/LaunchAgents/com.simp.cowork_bridge.plist

# Default: http://127.0.0.1:8767
# Health check:
curl -sf http://127.0.0.1:8767/health | python3 -m json.tool
```

## Health Checks

```bash
# Broker
curl -sf http://127.0.0.1:5555/health | python3 -m json.tool

# Dashboard
curl -sf http://127.0.0.1:8050/health | python3 -m json.tool

# Cowork Bridge
curl -sf http://127.0.0.1:8767/health | python3 -m json.tool

# List registered agents
curl -sf http://127.0.0.1:5555/agents | python3 -m json.tool

# Broker status script
bash bin/broker_status.sh
```

## Send a Test Intent

```bash
# Safe diagnostic intent (no side effects)
bash bin/send_diagnostic_intent.sh

# Manual intent via queue_intent.sh
bash bin/queue_intent.sh "DIAGNOSTIC: Echo test, no side effects" status_check low claude_cowork diagnostic_runner

# Verify delivery:
# 1. Check file inbox (if HTTP delivery failed, intent falls back here)
ls -la data/inboxes/claude_cowork/

# 2. Check outbox for response
ls -la data/outboxes/claude_cowork/

# 3. Check BRP logs
ls -la data/brp/
cat data/brp/events.jsonl | python3 -m json.tool --no-ensure-ascii 2>/dev/null | head -30
```

## Restart Procedures

### Restart Everything
```bash
bash bin/restart_all.sh
# Then re-register agents:
bash bin/register_agents.sh
```

### Restart Broker Only
```bash
# Kill existing
lsof -ti :5555 | xargs kill -9 2>/dev/null
sleep 1

# Start fresh
python bin/start_server.py &
sleep 3

# Re-register agents (registrations are in-memory)
bash bin/register_agents.sh
```

### Restart Dashboard Only
```bash
# Kill existing
lsof -ti :8050 | xargs kill -9 2>/dev/null
sleep 1

# Start fresh
python dashboard/server.py &
```

### Restart Cowork Bridge Only
```bash
# Kill existing
lsof -ti :8767 | xargs kill -9 2>/dev/null
sleep 1

# Start fresh
python bin/cowork_bridge.py &
```

## Known Issues & Workarounds

### Too many open files warning
**Symptom:** `[AgentRegistry] WARNING: persist write failed ([Errno 24] Too many open files`
**Cause:** The BRP bridge's `_append_jsonl` function was creating a new `threading.Lock()` on
every call instead of reusing a module-level lock. This caused unnecessary resource allocation.
**Fix:** Fixed in this branch — now uses a shared `_jsonl_lock` module-level lock.
**Workaround (if still seeing):** Increase the file descriptor limit:
```bash
ulimit -n 4096
```

### Intents showing `queued_no_endpoint`
**Symptom:** Intents sent to `claude_cowork` show `queued_no_endpoint` delivery status.
**Cause:** When the cowork bridge HTTP endpoint was unreachable (connection refused, httpx not
installed, etc.), the broker had no fallback — it would fail without writing to the file inbox.
**Fix:** Fixed in this branch — broker now falls back to file-based inbox delivery when HTTP
delivery fails. The cowork bridge's file poller picks up intents from `data/inboxes/claude_cowork/`.

### BRP logs not being written
**Symptom:** `data/brp/` directory empty or files missing.
**Cause:** BRP bridge used a relative path `Path("data/brp")` which resolved against the process
CWD rather than the repo root.
**Fix:** Fixed in this branch — now resolves relative to the repo root (`simp/security/brp_bridge.py`
parent chain).

### Dashboard not starting
**Symptom:** Port 8050 closed, no process listening.
**Cause:** Dashboard is a FastAPI app that requires `uvicorn`, `httpx`, `fastapi`, and `starlette`.
Must be started manually or via launchd.
**Startup:** `python dashboard/server.py` or `uvicorn dashboard.server:app --host 0.0.0.0 --port 8050`

### Test skips
Some tests may be skipped due to optional dependencies (e.g., `httpx`, `requests`). This is
expected — the core tests use mocks and don't require running services.

## BRP Verification

```bash
# Check BRP directory exists
ls -la data/brp/

# Check JSONL files exist and have content
wc -l data/brp/*.jsonl 2>/dev/null

# View recent events
tail -5 data/brp/events.jsonl | python3 -m json.tool

# View recent plan reviews
tail -5 data/brp/plans.jsonl | python3 -m json.tool

# View recent responses
tail -5 data/brp/responses.jsonl | python3 -m json.tool

# Trigger BRP logging by sending an intent:
bash bin/send_diagnostic_intent.sh
# Then check:
tail -1 data/brp/events.jsonl | python3 -m json.tool
```

## Port Reference
| Service          | Port | Protocol |
|-----------------|------|----------|
| Broker          | 5555 | HTTP     |
| Dashboard       | 8050 | HTTP     |
| Cowork Bridge   | 8767 | HTTP     |
| Gemma4 Agent    | 5010 | HTTP     |
