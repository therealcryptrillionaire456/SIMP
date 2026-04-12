# SIMP Agent Registry

> **Canonical reference** for all agents registered with the SIMP broker.
> Last updated: 2026-04-04 | Maintained by: CoWork + Perplexity coordination layer
> Source of truth for: agent IDs, transport, capabilities, intent types, codebase locations.

---

## Registry Overview

| Agent ID | Display Name | Transport | Status |
|---|---|---|---|
| `bullbear_predictor` | BullBear Predictor | File-based | ✅ Production |
| `kashclaw` | KashClaw Trading Agent | File-based | ✅ Production |
| `quantumarb` | QuantumArb Agent | File-based | ⚠️ Registered, pending Day 4 wiring |
| `simp_router` | SIMP Router | HTTP :5555 | ✅ Production |
| `kloutbot` | Kloutbot Orchestrator | HTTP :8765 | ✅ Production |
| `perplexity_research` | Perplexity Research Agent | HTTP :8766 | ✅ Production |

Total registered: **6**

---

## Detailed Agent Profiles

### 1. `bullbear_predictor`

| Field | Value |
|---|---|
| **Agent ID** | `bullbear_predictor` |
| **Display name** | BullBear Predictor |
| **Transport** | File-based (`~/bullbear/signals/output/`) |
| **Source** | `~/bullbear/` — locally managed, not in SIMP GitHub repo |
| **Capabilities** | `prediction_signal`, `market_analysis`, `no_trade_gate` |

**Intent types produced:**
- `signal_*.json` — Bull/Bear/NoTrade signal with delta, trust, contradiction_score
- `intent_*.json` — Routed trade intent toward kashclaw
- `executiondecision_*.json` — Execution summary with BLOCKED/REVIEW/dry_run logic

**Intent types consumed:**
- Triggered by BullBear watcher watching `data/inbox/` for new text documents

**Key behaviour notes:**
- The `no_trade_gate` capability means BullBear emits signals but never directly executes.
- All BullBear intents carry `source_agent="kloutbot:grok:001"`, `target_agent="kashclaw:trading:001"`.
- `fire: false` on NOTRADE signals; `fire: true` on BULL/BEAR above threshold.
- Execution pipeline has `dry_run=True` safety gate — no live orders.

---

### 2. `kashclaw`

| Field | Value |
|---|---|
| **Agent ID** | `kashclaw` |
| **Display name** | KashClaw Trading Agent |
| **Transport** | File-based (consumes intents from `signals/output/`) |
| **Source** | `~/Downloads/kashclaw (claude rebuild)/simp/` |
| **Capabilities** | `trade_execution`, `dry_run`, `position_sizing` |

**Intent types consumed:**
- `intent_*.json` from BullBear — validates signal before any execution step
- SIMP intents with `intent_type` in `["validate_trade", "execute_trade", "dry_run_trade"]`

**Intent types produced:**
- `executiondecision_*.json` — BLOCKED, REVIEW, or DRY_RUN outcome

**Key behaviour notes:**
- KashClaw's SIMP shim lives at `simp/integrations/kashclaw_shim.py` (KashClawShim class, 346 lines).
- Position sizing and risk checks happen before any execution.
- In current production state: `dry_run=True` for all paths. No live capital at risk.

---

### 3. `quantumarb`

| Field | Value |
|---|---|
| **Agent ID** | `quantumarb` |
| **Display name** | QuantumArb Agent |
| **Transport** | File-based (pending HTTP endpoint in Day 4) |
| **Source** | `simp/agents/` (partially scaffolded) |
| **Capabilities** | `arbitrage`, `cross_venue`, `latency_arbitrage` |

**Status:** Registered with SIMP broker. Day 4 roadmap item "Multi-Agent Orchestration with QuantumArb" will wire it as an active intent consumer/producer alongside BullBear signals.

**Intent types planned:**
- Consumer: `arbitrage_opportunity` intents from BullBear signal feed
- Producer: `arb_execution_decision` intents back to simp_router

**Key behaviour notes:**
- Must not receive trade execution intents until Day 4 wiring is complete and triple-verified.
- When integrated, should inherit the same `dry_run=True` safety gate as KashClaw.

---

### 4. `simp_router`

| Field | Value |
|---|---|
| **Agent ID** | `simp_router` |
| **Display name** | SIMP Router |
| **Transport** | HTTP `127.0.0.1:5555` |
| **Source** | `simp/server/broker.py` (SimpBroker, 394 lines) + `simp/server/http_server.py` (289 lines) |
| **Capabilities** | `intent_routing`, `agent_registry`, `broadcast` |

**HTTP endpoints:**
| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check — returns broker status |
| `/agents` | GET | List all registered agents |
| `/agents/register` | POST | Register a new agent |
| `/intents/route` | POST | Route an intent to a target agent |
| `/intents/history` | GET | Retrieve intent routing history |

**Key behaviour notes:**
- `route_intent()` in `broker.py` currently records the intent and returns `"status": "routed"` but does not forward to target agent HTTP endpoints (placeholder per roadmap Day 4).
- `X-SIMP-API-Key` header is sent by BullBear's `send_intent_to_simp.py` but validation middleware status should be confirmed in local branch (not visible in GitHub repo).

---

### 5. `kloutbot`

| Field | Value |
|---|---|
| **Agent ID** | `kloutbot` |
| **Display name** | Kloutbot Orchestrator |
| **Transport** | HTTP `127.0.0.1:8765` |
| **Source** | `simp/agents/kloutbot_agent.py` (362 lines) |
| **Capabilities** | `orchestration`, `coordination`, `mcp_bridge` |

**Intent types produced:**
- Higher-level orchestration intents dispatched through simp_router
- `source_agent="kloutbot:grok:001"` on BullBear-originated intents

**Intent types consumed:**
- Orchestration commands from SIMP router
- MCP bridge events from external tools

**Key behaviour notes:**
- Acts as the bridge between external MCP tooling and the SIMP agent network.
- `kloutbot_agent.py` implements the `SimpAgent` base class from `simp/agent.py`.

---

### 6. `perplexity_research`

| Field | Value |
|---|---|
| **Agent ID** | `perplexity_research` |
| **Display name** | Perplexity Research Agent |
| **Transport** | HTTP `127.0.0.1:8766` |
| **Source** | External — Perplexity Computer cloud instance |
| **Capabilities** | `research`, `web_search`, `market_intelligence` |

**Intent types consumed:**
- `research_request` intents from simp_router or kloutbot

**Intent types produced:**
- `research_result` intents with web search summaries and market intelligence

**Key behaviour notes:**
- Perplexity Research is the only agent with real-time web access.
- BullBear's `data/inbox/` can be seeded with Perplexity research output for GraphEngine analysis.
- In the coordination layer, Perplexity Computer (the higher-level orchestration AI) is distinct from `perplexity_research` (the registered SIMP agent).

---

## Coordination Agents (Higher-Level, Not SIMP-Registered)

These are not registered as SIMP agents but operate as orchestration coordinators above the broker:

| Agent | Role | Channel |
|---|---|---|
| **Claude CoWork** | Code scaffolding, test harnesses, git operations, local execution | This session |
| **Perplexity Computer** | Research, roadmap interpretation, schema design, orchestration flow design | Separate session |

Their coordination state is logged to `docs/coordination-log.md` and emitted as `coordination_*.json` artifacts to `signals/output/`.

---

## Proposed Enhancement: Capabilities Field in Registration

Per Enhancement C (Perplexity proposal, CoWork implementation), the following additive change to `/agents/register` will allow programmatic capability discovery:

```json
{
  "agent_id": "bullbear_predictor",
  "agent_type": "predictor",
  "endpoint": "file:///signals/output/",
  "metadata": {
    "capabilities": ["prediction_signal", "market_analysis", "no_trade_gate"],
    "description": "BullBear adversarial macro predictor — BULL/BEAR/NOTRADE signals",
    "version": "1.0.0",
    "dry_run_safe": true
  }
}
```

See `docs/broker-capabilities-patch.diff` for the exact additive broker.py change (zero breaking changes).

---

*This document is a living registry. Update when agents are added, capabilities change, or endpoints move.*
*Both CoWork and Perplexity should update this file when proposing changes that affect agent registration.*
