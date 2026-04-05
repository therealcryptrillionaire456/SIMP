# SIMP — System for Inter-Agent Market Planning

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

A production-grade protocol for AI agent-to-agent communication. SIMP acts as a central coordination and routing layer for multi-agent systems.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    SIMP Broker (:5555)                │
│  ┌────────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Rate Limit │  │ Auth     │  │ Request Guards   │ │
│  │ (token     │  │ (bearer  │  │ (sanitize IDs,   │ │
│  │  bucket)   │  │  token)  │  │  validate JSON)  │ │
│  └────────────┘  └──────────┘  └──────────────────┘ │
│  ┌────────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Intent     │  │ Event    │  │ Orchestration    │ │
│  │ Router     │  │ Log Ring │  │ Loop             │ │
│  │            │  │ Buffer   │  │                  │ │
│  └────────────┘  └──────────┘  └──────────────────┘ │
│  ┌────────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Task       │  │ Memory   │  │ Builder Pool     │ │
│  │ Ledger     │  │ Hooks    │  │ + Routing Policy │ │
│  └────────────┘  └──────────┘  └──────────────────┘ │
└──────────────────────────────────────────────────────┘
         │                    │
    ┌────┴────┐         ┌────┴────┐
    │ HTTP    │         │ File    │
    │ Agents  │         │ Agents  │
    ├─────────┤         ├─────────┤
    │ router  │         │ bullbear│
    │ kloutbot│         │ kashclaw│
    │ pplx    │         │ quantum │
    │ claude  │         │         │
    └─────────┘         └─────────┘

┌──────────────────────────────────────────────────────┐
│             Dashboard (:8050) — GET-only             │
│  Public-safe read-only monitoring with redaction     │
│  Agents · Tasks · Logs · Topology · Memory · Stats   │
│  Orchestration · Computer Use (ProjectX)             │
└──────────────────────────────────────────────────────┘
```

## Features

- **Intent-based routing** — Agents communicate via typed intents with source/target/params
- **7 registered agents** — HTTP-based and file-based delivery modes
- **Structured event logging** — Ring buffer with queryable JSON events
- **Rate limiting** — Token-bucket per-endpoint rate control
- **Authentication** — Bearer token auth on control endpoints
- **Request validation** — Input sanitization, size limits, path traversal protection
- **Graceful shutdown** — Drain in-flight intents, stop background tasks
- **Task ledger** — JSONL-backed task persistence with failure taxonomy
- **Memory layer** — Conversation archive, task memory, knowledge index
- **Orchestration loop** — Autonomous task queue processing
- **Routing policy** — JSON-configurable agent routing with fallback rules
- **Public dashboard** — Safe for reverse proxy exposure, redacts secrets
- **Computer-use agent** — ProjectX bounded action layer for screenshot-driven GUI automation and shell execution

## Quickstart

```bash
# Clone and install
git clone https://github.com/therealcryptrillionaire456/SIMP.git
cd SIMP
pip install -r requirements.txt  # or: pip install -e .

# Start the broker
python3.10 -m simp.server.http_server

# Start the dashboard (separate terminal)
python3.10 dashboard/server.py

# Run tests
python3.10 -m pytest tests/ -q
```

## Test Suites

| Suite | Tests | What it covers |
|-------|-------|----------------|
| test_request_guards | 26 | Input validation, sanitization |
| test_kashclaw_integration | 23 | Trading agent integration |
| test_sprint5_audit | 19 | Security findings verification |
| test_protocol_validation | 17 | Intent routing, schema compliance |
| test_sprint11_projectx | 16 | ProjectX skeleton + observation layer |
| test_sprint12_actions | 15 | GUI actions + shell execution |
| test_sprint13_safety | 13 | Logging, safety gate, abort |
| test_sprint8_memory | 10 | Memory layer, datetime deprecation |
| test_sprint2_hardening | 10 | Rate limiting, auth, path safety |
| test_sprint4_shutdown | 9 | Graceful shutdown, cleanup |
| test_sprint3_observability | 9 | Structured logging, ring buffer |
| test_sprint14_integration | 8 | SIMP integration + dashboard endpoint |
| test_sprint10_final | 7 | Production readiness verification |
| test_sprint7_orchestration | 6 | Orchestration loop integration |
| test_intent_schema | 6 | Coordination intent schemas |
| test_agent_manager_security | 5 | Agent manager security tests |
| test_sprint9_protocol | 4 | Protocol cleanup, module compilation |
| test_intent | 4 | Core intent/crypto/agent |

## Security

All endpoints validated. Dashboard is GET-only with sensitive field redaction.

| Protection | Implementation |
|-----------|----------------|
| Input validation | `request_guards.py` — sanitize IDs, validate JSON |
| Rate limiting | Token-bucket per endpoint (no external deps) |
| Auth | Bearer token on `/control/*` and `DELETE /agents` |
| Request size | Flask `MAX_CONTENT_LENGTH = 64KB` |
| Path traversal | Sanitized agent IDs in file-based delivery |
| CORS | Configurable origins via `DASHBOARD_CORS_ORIGINS` |
| Secret redaction | Dashboard strips API keys, tokens, file paths |

## Computer Use (ProjectX)

ProjectX provides a bounded, auditable interface for AI agents to interact with the host computer.

| Tier | Actions | Risk Level |
|------|---------|------------|
| 0 — Observation | get_screenshot, get_active_window, ocr_screen, snapshot_state | Read-only, always allowed |
| 1 — GUI | click, double_click, type_text, press, scroll, focus_app | Low-risk, reversible |
| 2 — Shell | run_shell | Medium-risk, logged |
| 3 — Restricted | (future) | Requires explicit approval |

All actions pass through `safe_execute()` which validates, captures pre/post state, and logs to JSONL.

```bash
# Initialize ProjectX in the broker
from simp.projectx.computer import ProjectXComputer
pc = ProjectXComputer(log_dir="./projectx_logs", max_tier=2)
result = pc.safe_execute({"action": "run_shell", "params": {"command": "echo hello"}})
```

## Production Deployment

For production, use gunicorn instead of the Flask dev server:

```bash
python3.10 bin/start_production.py --workers 4 --port 8080 --host 0.0.0.0
```

Or with environment variables:
```bash
SIMP_HTTP_HOST=0.0.0.0 SIMP_HTTP_PORT=8080 python3.10 bin/start_production.py
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SIMP_CONTROL_TOKEN` | (unset) | Bearer token for control endpoints |
| `SIMP_BROKER_URL` | `http://127.0.0.1:5555` | Broker URL for dashboard |
| `DASHBOARD_CORS_ORIGINS` | `*` | Comma-separated CORS origins |
| `DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind host |
| `DASHBOARD_PORT` | `8050` | Dashboard bind port |

## Sprint History

| Sprint | Focus | Status |
|--------|-------|--------|
| 1 | Input validation, broken validation.py fix | Done |
| 2 | Rate limiting, control auth, path safety | Done |
| 3 | Event loop refactor, structured logging, /logs | Done |
| 4 | Graceful shutdown, datetime fix, dead code removal | Done |
| 5 | CORS config, dashboard health, final audit | Done |
| 6 | Dashboard feature completion (logs, topology, queue) | Done |
| 7 | Orchestration loop integration | Done |
| 8 | Memory layer activation | Done |
| 9 | Protocol cleanup, Pydantic v2 migration | Done |
| 10 | Production readiness, README, version bump | Done |
| 11 | ProjectX skeleton + observation layer | Done |
| 12 | GUI actions + shell execution | Done |
| 13 | Logging, safety gate, abort | Done |
| 14 | SIMP integration + dashboard endpoint | Done |
| 15 | Production readiness, README, version 0.3.0 | Done |

## License

MIT
