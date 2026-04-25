# SIMP — Standardized Intent Messaging Protocol

[![Tests](https://img.shields.io/badge/tests-384_passing-brightgreen)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)]()
[![Version](https://img.shields.io/badge/version-0.4.0-orange)]()

A production-grade protocol for AI agent-to-agent communication. **SIMP (Standardized Intent Messaging Protocol)** acts as a central coordination and routing layer for multi-agent systems — the "HTTP of Agentic AI" — providing validated intent routing, Ed25519 cryptographic provenance, task lifecycle management, and real-time observability via a broker-based architecture.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SIMP Broker (:8080)                   │
│  ┌────────────┐  ┌──────────┐  ┌──────────────────────┐│
│  │ Rate Limit │  │ Auth     │  │ Request Guards       ││
│  │ (token     │  │ (API key │  │ (sanitize IDs,       ││
│  │  bucket)   │  │ +control)│  │  validate JSON)      ││
│  └────────────┘  └──────────┘  └──────────────────────┘│
│  ┌────────────┐  ┌──────────┐  ┌──────────────────────┐│
│  │ Intent     │  │ Event    │  │ Orchestration        ││
│  │ Router     │  │ Log Ring │  │ Loop                 ││
│  │ + BuilderP │  │ Buffer   │  │                      ││
│  └────────────┘  └──────────┘  └──────────────────────┘│
│  ┌────────────┐  ┌──────────┐  ┌──────────────────────┐│
│  │ Task       │  │ Memory   │  │ Builder Pool         ││
│  │ Ledger     │  │ Hooks    │  │ + Routing Policy     ││
│  └────────────┘  └──────────┘  └──────────────────────┘│
└─────────────────────────────────────────────────────────┘
         │                    │
    ┌────┴────┐         ┌────┴────┐
    │ HTTP    │         │ File    │
    │ Agents  │         │ Agents  │
    ├─────────┤         ├─────────┤
    │ gemma4  │         │ bullbear│
    │ kloutbot│         │ kashclaw│
    │ pplx    │         │ quantum │
    │ claude  │         │         │
    └─────────┘         └─────────┘

┌─────────────────────────────────────────────────────────┐
│                 SIMP Broker (:8080)                      │
│  Registration · Routing · Task Ledger                    │
│  Security · Observability · Orchestration                │
├─────────────────────────────────────────────────────────┤
│           ProjectX (Native Agent)                        │
│  Knowledge Sync · Protocol Health · Self-Improve         │
├─────────────────────────────────────────────────────────┤
│        Dashboard (:8050) — GET-only                      │
│  WebSocket · Charts · Search · Security                  │
└─────────────────────────────────────────────────────────┘
     ↕ HTTP/File    ↕ HTTP/File    ↕ HTTP
┌─────────┐  ┌──────────┐  ┌──────────────┐
│ Gemma4  │  │ Claude   │  │ Perplexity   │
│ (local) │  │ Cowork   │  │ Research     │
└─────────┘  └──────────┘  └──────────────┘
```

## Features

- **Intent-based routing** — Agents communicate via 35 typed intents with source/target/params
- **Protocol versioning** — Version negotiation with forward-compatible validation
- **Weighted routing** — BuilderPool with health x load x round-robin scoring
- **Standardized event logging** — Ring buffer with queryable JSON events
- **Rate limiting** — Token-bucket per-endpoint rate control
- **Authentication** — API key + control token on admin endpoints
- **Ed25519 signatures** — Optional cryptographic intent verification
- **Request validation** — Input sanitization, size limits, path traversal protection
- **Graceful shutdown** — Drain in-flight intents, stop background tasks
- **Task ledger** — JSONL-backed task persistence with failure taxonomy and retry
- **Memory layer** — Conversation archive, task memory, knowledge index
- **Orchestration loop** — Autonomous task queue processing
- **Routing policy** — JSON-configurable agent routing with fallback rules
- **Public dashboard** — Safe for reverse proxy exposure, redacts secrets
- **WebSocket updates** — Real-time dashboard with activity charts
- **Computer-use agent** — ProjectX bounded action layer for GUI automation and shell execution
- **Self-improvement** — Recursive optimization engine with mutation memory

## Quickstart

### Step 1: Clone and Install

```bash
git clone https://github.com/therealcryptrillionaire456/SIMP.git
cd SIMP
pip install -r requirements.txt  # or: pip install -e .
```

### Step 2: Start the Broker

```bash
python3 -m simp.server.http_server
# Broker starts on http://127.0.0.1:8080
```

### Step 3: Start the Dashboard

```bash
# In a separate terminal
python3 dashboard/server.py
# Dashboard at http://127.0.0.1:8050
```

### Step 4: Register an Agent

```bash
curl -X POST http://127.0.0.1:8080/agents/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "agent_id": "my_agent",
    "agent_type": "research",
    "endpoint": "http://localhost:9000",
    "metadata": {"simp_versions": ["1.0"]}
  }'
```

### Step 5: Send Your First Intent

```bash
curl -X POST http://127.0.0.1:8080/intents/route \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "intent_id": "intent:my_agent:test-001",
    "source_agent": "my_agent",
    "intent_type": "research",
    "params": {"query": "What is SIMP?"}
  }'
```

## API Reference

### Agent Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/agents/register` | API Key | Register a new agent |
| `GET` | `/agents` | API Key | List all registered agents |
| `GET` | `/agents/<agent_id>` | None | Get agent details |
| `DELETE` | `/agents/<agent_id>` | Control Token | Deregister an agent |

### Intent Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/intents/route` | API Key | Route an intent to target agent |
| `GET` | `/intents/<intent_id>` | None | Get intent status and response |
| `POST` | `/intents/<intent_id>/response` | API Key | Record intent response |
| `POST` | `/intents/<intent_id>/error` | None | Record intent error |

### Task Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/tasks` | API Key | List tasks with filtering |
| `GET` | `/tasks/<task_id>` | API Key | Get task details |
| `GET` | `/tasks/queue` | API Key | Get task queue state |

### System Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `GET` | `/stats` | None | Broker statistics (includes protocol versions) |
| `GET` | `/status` | None | Broker status |
| `GET` | `/logs` | None | Structured event log |
| `GET` | `/routing/policy` | API Key | Current routing policy |
| `POST` | `/control/start` | Control Token | Start broker |
| `POST` | `/control/stop` | Control Token | Stop broker |

### Memory Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/memory/conversations` | None | List conversations |
| `GET` | `/memory/conversations/<id>` | None | Get conversation |
| `POST` | `/memory/conversations` | API Key | Save conversation |
| `GET` | `/memory/tasks` | None | List memory tasks |
| `GET` | `/memory/tasks/<slug>` | None | Get memory task |
| `GET` | `/memory/index` | None | Knowledge index |
| `GET` | `/memory/context-pack` | None | Context pack |

## Agent Development Guide

### Creating a New SIMP Agent

1. **Register with the broker** by POSTing to `/agents/register` with your agent ID, type, and endpoint.

2. **Implement the intent handler** at your agent's endpoint:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/intents/handle", methods=["POST"])
def handle_intent():
    intent = request.json
    # Process the intent based on intent_type
    intent_type = intent.get("intent_type")
    params = intent.get("params", {})

    result = process(intent_type, params)

    return jsonify({
        "type": "response",
        "intent_id": intent["intent_id"],
        "agent_id": "my_agent",
        "status": "completed",
        "response": result
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})
```

3. **Supported intent types**: `code_task`, `research`, `planning`, `market_analysis`, `trade_execution`, `orchestration`, `scaffolding`, `test_harness`, `prediction_signal`, `arbitrage`, `spec`, `architecture`, `docs`, `computer_use`, `code_review`, `summarization`, and more (35 types total). See `PROTOCOL_SPEC.md` for the full list.

4. **Health checks**: The broker pings `/health` every 30 seconds. Return a 200 response to stay registered.

5. **Signatures (optional)**: Generate an Ed25519 keypair and include the public key in registration metadata. Sign intents with `SimpCrypto.sign_intent()`.

## Configuration Reference

| Env Var | Default | Description |
|---------|---------|-------------|
| `SIMP_HOST` | `127.0.0.1` | Broker bind host |
| `SIMP_PORT` | `5555` | Broker socket port |
| `SIMP_HTTP_HOST` | `127.0.0.1` | HTTP server bind host |
| `SIMP_HTTP_PORT` | `8080` | HTTP server bind port |
| `SIMP_ENABLE_TLS` | `false` | Enable TLS |
| `SIMP_TLS_CERT` | — | TLS certificate path |
| `SIMP_TLS_KEY` | — | TLS key path |
| `SIMP_TLS_CA` | — | TLS CA bundle path |
| `SIMP_REQUIRE_SIGNATURES` | `true` | Require Ed25519 intent signatures |
| `SIMP_REQUIRE_API_KEY` | `true` | Require API key authentication |
| `SIMP_API_KEYS` | — | Comma-separated valid API keys |
| `SIMP_CONTROL_TOKEN` | — | Bearer token for control endpoints |
| `SIMP_RATE_LIMIT_ROUTE` | `60/minute` | Rate limit for `/intents/route` |
| `SIMP_RATE_LIMIT_DEFAULT` | `200/day` | Default rate limit |
| `SIMP_MAX_PENDING_INTENTS` | `500` | Max pending intents |
| `SIMP_SOCKET_CONNECT_TIMEOUT` | `10.0` | Socket connect timeout (seconds) |
| `SIMP_SOCKET_RECV_TIMEOUT` | `30.0` | Socket receive timeout (seconds) |
| `SIMP_HEALTH_CHECK_TIMEOUT` | `5.0` | Health check timeout (seconds) |
| `SIMP_HEALTH_CHECK_INTERVAL` | `30.0` | Health check interval (seconds) |
| `SIMP_HEALTH_FAIL_THRESHOLD` | `3` | Consecutive failures before offline |
| `SIMP_DB_PATH` | `data/intents.db` | Intent database path |
| `SIMP_AUDIT_DB_PATH` | `data/audit.db` | Audit database path |
| `SIMP_LOG_DIR` | `logs/` | Log directory |
| `SIMP_TMP_DIR` | `tmp/` | Temporary directory |
| `SIMP_INTENT_TTL` | `3600` | Intent time-to-live (seconds) |
| `SIMP_CLEANUP_INTERVAL` | `300` | Cleanup interval (seconds) |
| `SIMP_MAX_AGENTS` | `100` | Maximum registered agents |
| `SIMP_MAX_PAYLOAD_BYTES` | `1000000` | Max request payload (bytes) |
| `SIMP_MAX_INTENT_ID_LEN` | `256` | Max intent ID length |
| `SIMP_MAX_AGENT_ID_LEN` | `128` | Max agent ID length |
| `SIMP_LOG_LEVEL` | `INFO` | Log level |
| `SIMP_OBFUSCATE_IPS` | `true` | Obfuscate IPs in logs |
| `SIMP_BROKER_URL` | `http://127.0.0.1:5555` | Broker URL (dashboard) |
| `DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind host |
| `DASHBOARD_PORT` | `8050` | Dashboard bind port |
| `DASHBOARD_CORS_ORIGINS` | `*` | Comma-separated CORS origins |

## Production Deployment

### Gunicorn

```bash
python3 bin/start_production.py --workers 4 --port 8080 --host 0.0.0.0
```

Or with environment variables:

```bash
SIMP_HTTP_HOST=0.0.0.0 SIMP_HTTP_PORT=8080 python3 bin/start_production.py
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name simp.example.com;

    ssl_certificate /etc/ssl/certs/simp.pem;
    ssl_certificate_key /etc/ssl/private/simp.key;

    # Broker API
    location /api/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Dashboard (public, GET-only)
    location /dashboard/ {
        proxy_pass http://127.0.0.1:8050/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### TLS

Enable TLS directly on the broker:

```bash
export SIMP_ENABLE_TLS=true
export SIMP_TLS_CERT=/path/to/cert.pem
export SIMP_TLS_KEY=/path/to/key.pem
python3 -m simp.server.http_server
```

## Computer Use (ProjectX)

ProjectX provides a bounded, auditable interface for AI agents to interact with the host computer.

| Tier | Actions | Risk Level |
|------|---------|------------|
| 0 — Observation | get_screenshot, get_active_window, ocr_screen, snapshot_state, sync_knowledge, update_knowledge, check_protocol_health | Read-only, always allowed |
| 1 — GUI | click, double_click, type_text, press, scroll, focus_app | Low-risk, reversible |
| 2 — Shell | run_shell | Medium-risk, logged |
| 3 — Restricted | (future) | Requires explicit approval |

All actions pass through `safe_execute()` which validates, captures pre/post state, and logs to JSONL.

```python
from simp.projectx.computer import ProjectXComputer
pc = ProjectXComputer(log_dir="./projectx_logs", max_tier=2)
result = pc.safe_execute({"action": "run_shell", "params": {"command": "echo hello"}})
```

## Security

All endpoints validated. Dashboard is GET-only with sensitive field redaction.

| Protection | Implementation |
|-----------|----------------|
| Input validation | `request_guards.py` — sanitize IDs, validate JSON |
| Rate limiting | Token-bucket per endpoint (no external deps) |
| Auth | API key on data plane, control token on admin |
| Ed25519 signatures | Optional per-intent cryptographic verification |
| Request size | `MAX_PAYLOAD_BYTES = 1MB` |
| Path traversal | Sanitized agent IDs in file-based delivery |
| CORS | Configurable origins via `DASHBOARD_CORS_ORIGINS` |
| Secret redaction | Dashboard strips API keys, tokens, file paths |
| CSP headers | Content-Security-Policy on all dashboard responses |

## Test Suite

384 tests across 29 test files. Run with:

```bash
python3 -m pytest tests/ -q
```

| Suite | Tests | Coverage |
|-------|-------|----------|
| test_request_guards | 26 | Input validation, sanitization |
| test_kashclaw_integration | 23 | Trading agent integration |
| test_sprint22_routing | 22 | Smart routing, load balancing, circuit breaker |
| test_sprint16_auth | 21 | API key auth, data plane security |
| test_e2e_task_flow | 20 | End-to-end task flow through system |
| test_sprint5_audit | 19 | Security findings verification |
| test_sprint17_schema | 19 | Crypto activation, schema unification |
| test_sprint25_final | 18 | Protocol versioning, docs, v0.4.0 release |
| test_sprint18_scalability | 18 | Connection pooling, async health checks |
| test_sprint11_projectx | 16 | ProjectX skeleton + observation layer |
| test_sprint19_production | 15 | Production server, orchestration fixes |
| test_sprint12_actions | 15 | GUI actions + shell execution |
| test_sprint24_selfimprove | 13 | Recursive self-improvement engine |
| test_sprint13_safety | 13 | Logging, safety gate, abort |
| test_sprint21_ux | 12 | Dashboard UX, security headers, charts |
| test_sprint20_dashboard | 11 | Dashboard live data, WebSocket |
| test_protocol_validation | 11 | Intent routing, schema compliance |
| test_sprint8_memory | 10 | Memory layer, datetime deprecation |
| test_sprint2_hardening | 10 | Rate limiting, auth, path safety |
| test_sprint4_shutdown | 9 | Graceful shutdown, cleanup |
| test_sprint3_observability | 9 | Structured logging, ring buffer |
| test_sprint15_final | 8 | Production readiness v0.3.0 |
| test_sprint14_integration | 8 | SIMP integration + dashboard endpoint |
| test_sprint10_final | 7 | Production readiness verification |
| test_sprint7_orchestration | 6 | Orchestration loop integration |
| test_sprint9_protocol | 4 | Protocol cleanup, module compilation |
| test_intent | 3 | Core intent/crypto/agent |
| test_intent_schema | 6 | Coordination intent schemas |
| test_agent_manager_security | 5 | Agent manager security tests |

## Sprint History

| Sprint | Focus | Key Deliverable | Status |
|--------|-------|-----------------|--------|
| 1 | Input validation, broken validation.py fix | Request guards, sanitization | Done |
| 2 | Rate limiting, control auth, path safety | Token-bucket, bearer auth | Done |
| 3 | Event loop refactor, structured logging | Ring buffer, /logs endpoint | Done |
| 4 | Graceful shutdown, datetime fix | Drain queue, deprecation fix | Done |
| 5 | CORS config, dashboard health, final audit | Security audit, CORS | Done |
| 6 | Dashboard feature completion | Logs, topology, queue views | Done |
| 7 | Orchestration loop integration | Autonomous task processing | Done |
| 8 | Memory layer activation | Conversations, tasks, knowledge | Done |
| 9 | Protocol cleanup, Pydantic v2 migration | Schema unification | Done |
| 10 | Production readiness, README, v0.2.0 | Production release | Done |
| 11 | ProjectX skeleton + observation layer | Computer-use foundation | Done |
| 12 | GUI actions + shell execution | Click, type, run_shell | Done |
| 13 | Logging, safety gate, abort | JSONL audit, safety checks | Done |
| 14 | SIMP integration + dashboard endpoint | ProjectX in dashboard | Done |
| 15 | Production readiness, v0.3.0 | Production release | Done |
| 16 | Data plane authentication | API key auth on all routes | Done |
| 17 | Crypto activation, schema unification | Ed25519, canonical intents | Done |
| 18 | Connection pooling, async health checks | Scalability improvements | Done |
| 19 | Production server, orchestration fixes | Gunicorn, stability | Done |
| 20 | Dashboard live data, WebSocket | Real-time updates | Done |
| 21 | Dashboard UX, security headers | CSP, charts, search | Done |
| 22 | Smart routing, load balancing | BuilderPool, circuit breaker | Done |
| 23 | Gemma4 agent, real task flow | End-to-end agent integration | Done |
| 24 | Recursive self-improvement | Mutation memory, optimizer | Done |
| 25 | Protocol spec, versioning, v0.4.0 | **Final release** | Done |

**25-sprint plan COMPLETE.** See `SPRINT_LOG.md` for detailed change logs.

## Documentation

- [`PROTOCOL_SPEC.md`](PROTOCOL_SPEC.md) — Formal protocol specification (v1.0)
- [`SPRINT_LOG.md`](SPRINT_LOG.md) — Detailed sprint-by-sprint change log
- [`COORDINATION_PROTOCOL.md`](COORDINATION_PROTOCOL.md) — Multi-agent coordination protocol

## A2A Compatibility Layer

SIMP includes a comprehensive A2A (Agent-to-Agent) compatibility layer that enables standard A2A clients to interact with SIMP agents without modifying the core protocol.

### New A2A Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /.well-known/agent-card.json` | No | Broker-level A2A Agent Card |
| `POST /a2a/tasks` | API Key | Submit A2A task (translated to SIMP intent) |
| `GET /a2a/tasks/<id>` | API Key | Get task status |
| `GET /a2a/tasks/types` | No | List supported task types |
| `GET /a2a/events` | API Key | Recent A2A-formatted task events |
| `GET /a2a/events/<intent_id>` | API Key | Events for specific intent |
| `GET /a2a/security` | No | Security posture and scheme declarations |
| `GET /a2a/agents/projectx/agent.json` | No | ProjectX native agent card |
| `POST /a2a/agents/projectx/tasks` | API Key | Submit maintenance task |
| `GET /a2a/agents/projectx/health` | No | ProjectX health diagnostics |
| `GET /a2a/agents/financial-ops/agent.json` | No | FinancialOps agent card |
| `POST /a2a/agents/financial-ops/tasks` | API Key | Submit simulated financial op |

### Demo

See [docs/A2A_DEMO.md](docs/A2A_DEMO.md) for an end-to-end walkthrough, or run:

```bash
python3 examples/a2a_demo.py --broker-url http://127.0.0.1:5555
```

### Architecture Note

> A2A is an adapter surface. SIMP CanonicalIntent remains the routing authority.

## Bill Russell Protocol (BRP)

SIMP includes the Bill Russell Protocol — a defensive security subsystem named after the greatest defensive basketball player ever. BRP provides autonomous threat detection and response capabilities specifically designed to counter advanced AI-level threats.

### BRP Features

- **Pattern Recognition at Depth** — Detects attack signatures before completion (PCAP + Sysmon)
- **Autonomous Reasoning Chains** — Threat assessment without human review
- **Memory Across Time** — Correlates security events weeks apart
- **Sigma Rule Engine** — Custom detection rules for known threat patterns
- **ML Pipeline** — SecBERT fine-tuning for security event classification
- **Telegram Alerts** — Real-time threat notifications

### BRP Architecture

```
simp/security/brp/           # Core protocol (pattern recognition, reasoning, memory)
simp/security/brp_bridge.py  # Bridge to SIMP broker (Mother Goose integration)
simp/security/brp_models.py  # Typed event schemas
simp/agents/brp_agent.py     # BRP agent for SIMP broker
simp/integrations/brp/       # Log ingestion, alerts, sigma rules, ML pipeline
config/brp/                  # BRP configuration
```

### BRP Quick Start

```bash
# Run BRP tests
python3 -m pytest tests/test_brp_bridge.py tests/test_brp_end_to_end_smoke.py -v

# Run BRP integration tests
python3 -m pytest tests/security/brp/ -v
```

See [docs/brp/README.md](docs/brp/README.md) for full documentation.
For the higher-level Bridge framing behind SIMP, see [simp/docs/bridge_manifest.md](simp/docs/bridge_manifest.md).

## License

MIT
