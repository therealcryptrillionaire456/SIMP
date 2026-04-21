# SIMP Protocol Specification v1.0

## Abstract

SIMP (Structured Intent Messaging Protocol) defines a standard for agent-to-agent
communication via a centralized broker. It enables heterogeneous AI agents to register,
discover, and route structured intents through a validated pipeline with audit logging,
security, and observability.

**Protocol Version:** 1.0
**SIMP Version:** 0.4.0

---

## 1. Protocol Overview

SIMP follows a hub-and-spoke model with a central broker that:

- Registers and monitors agents via health checks
- Validates and routes intents through a canonical pipeline
- Tracks tasks through their lifecycle with a persistent ledger
- Provides observability via a real-time WebSocket dashboard and structured logs
- Enforces security through API keys, control tokens, signatures, and rate limiting

### Transport

Two delivery mechanisms are supported:

| Transport | Mechanism | Use Case |
|-----------|-----------|----------|
| **HTTP** | POST to agent endpoint | Real-time, online agents |
| **File-based** | Write to `data/inboxes/<agent_id>/` | Offline agents, batch processing |

---

## 2. Message Formats

### 2.1 Intent (Request)

An intent is the fundamental unit of communication in SIMP.

```json
{
  "intent_id": "intent:<source_agent>:<uuid4>",
  "simp_version": "1.0",
  "source_agent": "<agent_id>",
  "target_agent": "<agent_id>",
  "intent_type": "<type>",
  "params": {},
  "timestamp": "<ISO 8601>",
  "signature": "<hex-encoded Ed25519 signature>",
  "priority": "medium"
}
```

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `intent_id` | Yes | string | Unique ID in format `intent:<source>:<uuid>` |
| `source_agent` | Yes | string | Sending agent's registered ID |
| `intent_type` | Yes | string | One of the registered intent types (see Section 3) |
| `params` | Yes | object | Intent-specific parameters |
| `target_agent` | No | string | Specific target agent; if omitted, broker routes via BuilderPool |
| `simp_version` | No | string | Protocol version (default: `"1.0"`) |
| `timestamp` | No | string | ISO 8601 UTC timestamp |
| `signature` | No | string | Ed25519 signature for verification |
| `priority` | No | string | `critical`, `high`, `medium` (default), or `low` |

### 2.2 Response

```json
{
  "type": "response",
  "intent_id": "<original_intent_id>",
  "agent_id": "<responding_agent_id>",
  "status": "completed|failed",
  "response": {},
  "timestamp": "<ISO 8601>"
}
```

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `intent_id` | Yes | string | The original intent ID being responded to |
| `agent_id` | Yes | string | The responding agent's ID |
| `status` | Yes | string | `completed` or `failed` |
| `response` | Yes | object | Result data or error details |
| `timestamp` | Yes | string | ISO 8601 UTC timestamp |

### 2.3 Registration

```json
{
  "agent_id": "<unique_id>",
  "agent_type": "<type>",
  "endpoint": "http://<host>:<port>",
  "metadata": {
    "public_key": "<optional PEM-encoded Ed25519 public key>",
    "simp_versions": ["1.0"]
  }
}
```

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `agent_id` | Yes | string | Unique agent identifier (max 128 chars, sanitized) |
| `agent_type` | Yes | string | Agent category (e.g., `vision`, `research`, `trading`) |
| `endpoint` | Yes | string | Agent's HTTP endpoint or IPC address |
| `metadata` | No | object | Additional agent metadata |
| `metadata.public_key` | No | string | PEM-encoded Ed25519 public key for signature verification |
| `metadata.simp_versions` | No | array | Supported protocol versions (default: `["1.0"]`) |

---

## 3. Intent Types

The following intent types are registered in the canonical intent registry.
Each maps to a `task_type` used for routing.

| Intent Type | Task Type | Description |
|-------------|-----------|-------------|
| `code_task` | implementation | Code implementation task |
| `code_editing` | implementation | Code modification and refactoring |
| `planning` | architecture | Architecture and planning |
| `research` | research | Research and information gathering |
| `market_analysis` | analysis | Market analysis and prediction |
| `trade_execution` | implementation | Trade execution on exchanges |
| `orchestration` | architecture | Multi-agent orchestration command |
| `scaffolding` | scaffold | Project scaffolding and setup |
| `test_harness` | test | Test creation and execution |
| `prediction_signal` | analysis | Predictive signal generation |
| `arbitrage` | implementation | Arbitrage opportunity execution |
| `spec` | spec | Specification writing |
| `architecture` | architecture | Architecture design |
| `docs` | docs | Documentation generation |
| `computer_use` | implementation | Computer-use action execution |
| `computer_use_design_review` | research | Design review via computer-use |
| `improve_tree` | analysis | Decision tree optimization request |
| `native_agent_repo_scan` | analysis | ProjectX repo introspection scan |
| `code_review` | test | Code review and quality assessment |
| `summarization` | docs | Content summarization |
| `submit_goal` | architecture | High-level goal submission for decomposition |
| `test` | test | Generic test intent |
| `system_test` | test | System-level test intent |
| `research_request` | research | Research request from agent |
| `research_finding` | research | Research finding report |
| `detect_signal` | analysis | Signal detection |
| `analyze_patterns` | analysis | Pattern analysis |
| `vectorize` | implementation | Vectorization task |
| `generate_strategy` | analysis | Strategy generation |
| `validate_action` | test | Action validation |
| `trade_signal` | analysis | Trade signal emission |
| `arbitrage_check` | analysis | Arbitrage opportunity check |
| `orchestration_command` | architecture | Orchestration command |
| `check_status` | research | Status check request |
| `replan` | architecture | Replanning request |

---

## 4. Agent Lifecycle

### 4.1 Registration

```
POST /agents/register
Authorization: Bearer <API_KEY>
```

The broker stores the agent record with health state initialized to `online`.
Maximum agents: configurable via `SIMP_MAX_AGENTS` (default: 100).

### 4.2 Health Monitoring

The broker polls each agent's `/health` endpoint at a configurable interval
(default: 30s, via `SIMP_HEALTH_CHECK_INTERVAL`).

- Timeout: 5s (`SIMP_HEALTH_CHECK_TIMEOUT`)
- After 3 consecutive failures (`SIMP_HEALTH_FAIL_THRESHOLD`): agent marked offline
- Auto-deregistration after sustained failures

### 4.3 Intent Handling

Agents receive intents via:

```
POST <agent_endpoint>/intents/handle
```

The agent processes the intent and responds with a structured response.

### 4.4 Deregistration

```
DELETE /agents/<agent_id>
Authorization: Bearer <CONTROL_TOKEN>
```

Agents are removed immediately. Automatic deregistration occurs after sustained
health check failures.

---

## 5. Routing Algorithm

Intent routing follows this decision tree:

1. **Direct routing** — If `target_agent` is specified, deliver directly to that agent.
2. **BuilderPool routing** — If no target, the BuilderPool selects an agent by `task_type` mapping from the routing policy.
3. **Weighted scoring** — Agents are scored by: `health × load × round-robin` weighting.
4. **Multi-hop retry** — Failed deliveries retry with exponential backoff.
5. **Circuit breaker** — 5 failures within 10 minutes triggers a 5-minute cooldown for the target agent.

### Routing Policy

The routing policy is a JSON configuration (`data/routing_policy.json`) that maps
task types to preferred agents with fallback chains:

```json
{
  "implementation": ["gemma4", "claude_cowork"],
  "research": ["pplx_research", "gemma4"],
  "analysis": ["kloutbot", "gemma4"]
}
```

---

## 6. Task Lifecycle

Tasks transition through the following states:

```
queued → claimed → in_progress → completed | failed | blocked
```

| State | Description |
|-------|-------------|
| `queued` | Task is in the queue, awaiting claim |
| `claimed` | An agent has claimed the task |
| `in_progress` | Agent is actively working on the task |
| `completed` | Task finished successfully |
| `failed` | Task failed (see Error Taxonomy, Section 9) |
| `blocked` | Task is waiting on subtask completion |

### Priority Levels

| Priority | Value | Description |
|----------|-------|-------------|
| `critical` | 0 | Immediate processing |
| `high` | 1 | Expedited processing |
| `medium` | 2 | Normal processing (default) |
| `low` | 3 | Background processing |

Subtask ordering is enforced via the `blocked` state — a parent task remains
blocked until all subtasks complete.

---

## 7. Security Model

### 7.1 Authentication

| Layer | Mechanism | Scope |
|-------|-----------|-------|
| API Key | `Authorization: Bearer <key>` | Data plane (route, register, tasks) |
| Control Token | `Authorization: Bearer <token>` | Admin endpoints (start, stop, deregister) |
| Ed25519 Signatures | Optional per-intent | Intent integrity verification |

### 7.2 Rate Limiting

Token-bucket rate limiting with configurable rates:

| Endpoint | Default Limit |
|----------|--------------|
| `/intents/route` | 60 per minute |
| All others | 200 per day |

Configurable via `SIMP_RATE_LIMIT_ROUTE` and `SIMP_RATE_LIMIT_DEFAULT`.

### 7.3 Request Guards

- **Agent ID sanitization** — IDs are validated against `[a-zA-Z0-9_-]`, max 128 chars
- **Payload size limits** — Max 1MB (`SIMP_MAX_PAYLOAD_BYTES`)
- **Intent ID length** — Max 256 chars (`SIMP_MAX_INTENT_ID_LEN`)
- **JSON validation** — All request bodies validated before processing
- **Path traversal protection** — File-based delivery paths are sanitized

### 7.4 Dashboard Security

The dashboard is designed to be safe for public exposure:

- **GET-only** — No mutating operations
- **XSS protection** — Content-Security-Policy headers
- **Secret redaction** — API keys, tokens, and file paths stripped from responses
- **CORS** — Configurable origins via `DASHBOARD_CORS_ORIGINS`

---

## 8. Observability

### 8.1 Structured Event Logging

All broker events are logged to a ring buffer (queryable via `GET /logs`):

- Agent registration and deregistration
- Intent routing, completion, and failure
- Health check results
- Task state transitions

### 8.2 Real-Time Dashboard

The dashboard (`dashboard/server.py`, port 8050) provides:

- **WebSocket** real-time updates
- **Activity charts** with time-series visualization
- **Task search and filtering** by status, agent, type
- **Agent topology view** showing registered agents and health
- **Memory browser** for conversations, tasks, and knowledge index
- **Orchestration monitor** showing queue state and active tasks
- **Computer-use log** for ProjectX action audit trail

### 8.3 Audit Database

All intents are persisted to SQLite (`data/intents.db`) with full request/response
payloads for post-hoc analysis. A separate audit database (`data/audit.db`) records
security events.

---

## 9. Error Taxonomy

Failures are classified into the following categories, each with a defined retry policy:

| Failure Class | Retryable | Delay | Max Retries | Requeue | Description |
|---------------|-----------|-------|-------------|---------|-------------|
| `rate_limited` | Yes | 60s | 3 | Yes | Agent or endpoint is rate-limited |
| `schema_invalid` | No | — | — | No | Intent failed schema validation |
| `policy_denied` | No | — | — | No | Routing policy rejected the intent |
| `agent_unavailable` | Yes | 10s | 2 | Yes | Target agent is offline or unreachable |
| `timeout` | Yes | 5s | 1 | Yes | Agent did not respond within timeout |
| `execution_failed` | Yes | 5s | 1 | Yes | Agent returned an execution error |
| `claim_conflict` | No | — | — | No | Another agent already claimed the task |

Non-retryable failures are immediately marked as terminal. Retryable failures
are requeued with the specified delay and decrement the retry counter.

---

## 10. HTTP API Reference

### Agent Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/agents/register` | API Key | Register a new agent |
| GET | `/agents` | API Key | List all registered agents |
| GET | `/agents/<agent_id>` | None | Get agent details |
| DELETE | `/agents/<agent_id>` | Control Token | Deregister an agent |

### Intent Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/intents/route` | API Key | Route an intent to target agent |
| GET | `/intents/<intent_id>` | None | Get intent status |
| POST | `/intents/<intent_id>/response` | API Key | Record intent response |
| POST | `/intents/<intent_id>/error` | None | Record intent error |

### Task Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/tasks` | API Key | List tasks |
| GET | `/tasks/<task_id>` | API Key | Get task details |
| GET | `/tasks/queue` | API Key | Get task queue state |

### System Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| GET | `/stats` | None | Broker statistics |
| GET | `/status` | None | Broker status |
| GET | `/logs` | None | Structured event log |
| GET | `/routing/policy` | API Key | Current routing policy |
| POST | `/control/start` | Control Token | Start broker |
| POST | `/control/stop` | Control Token | Stop broker |

### Memory Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/memory/conversations` | None | List conversations |
| GET | `/memory/conversations/<id>` | None | Get conversation |
| POST | `/memory/conversations` | API Key | Save conversation |
| GET | `/memory/tasks` | None | List memory tasks |
| GET | `/memory/tasks/<slug>` | None | Get memory task |
| GET | `/memory/index` | None | Knowledge index |
| GET | `/memory/context-pack` | None | Context pack |

---

## 11. Version Negotiation

As of SIMP v0.4.0, protocol version negotiation is supported:

- **Broker** reports supported protocol versions in `GET /stats` response
- **Intents** may include a `simp_version` field; unsupported versions generate a warning but are not rejected (forward-compatible)
- **Agents** declare supported versions during registration via `metadata.simp_versions`

Current supported protocol version: **1.0**

---

## 12. Conformance

An implementation is conformant with SIMP Protocol v1.0 if it:

1. Accepts and produces messages in the formats defined in Section 2
2. Implements the agent lifecycle described in Section 4
3. Routes intents according to the algorithm in Section 5
4. Classifies failures according to the taxonomy in Section 9
5. Enforces the security model described in Section 7

---

*SIMP Protocol Specification v1.0 — April 2026*
