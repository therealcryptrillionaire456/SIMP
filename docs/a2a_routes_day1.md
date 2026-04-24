# A2A Routes — Day 1 Inventory

HTTP routes on the SIMP broker (port 5555). Generated from `simp/server/http_server.py`.

## Legend
- **Live** — actively used by running agents
- **Dead** — defined but uncalled by any running agent
- **Duplicate** — same logic at different paths
- **Needs-Auth** — requires X-API-Key or Bearer token
- **Touches-Venue** — can cause trades/external API calls

---

## Core Broker Routes

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/health` | GET | **Live** | No | No | Simple health check |
| `/agentic/contract` | GET | Dead | No | No | Agentic contract endpoint |
| `/agentic/intents/route` | POST | Dead | Yes | No | Duplicate of `/intents/route` |
| `/skills` | GET | Dead | No | No | Skill listing |
| `/tasks/<task_id>/stream` | GET | Dead | No | No | SSE stream for tasks |
| `/native/tools/list` | GET | Live | No | No | Tool discovery |
| `/native/tools/<agent_id>/list` | GET | Live | No | No | Per-agent tools |
| `/native/tools/<agent_id>/<tool_name>/invoke` | POST | Live | Yes | Depends | Tool execution |
| `/mcp/tools/list` | GET | Dead | No | No | MCP compat layer |
| `/mcp/tools/<agent_id>/list` | GET | Dead | No | No | Per-agent MCP |
| `/mcp/tools/<agent_id>/<tool_name>/call` | POST | Dead | Yes | No | MCP tool call |
| `/timesfm/health` | GET | Dead | No | No | TimesFM health |
| `/timesfm/audit` | GET | Dead | No | No | TimesFM audit |

## Agent Registry

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/agents/register` | POST | **Live** | Yes | No | Agent self-registration |
| `/agents` | GET | **Live** | No | No | List all agents |
| `/agents/heartbeat` | POST | **Live** | Yes | No | Heartbeat (legacy) |
| `/agents/<agent_id>` | GET | **Live** | No | No | Get agent info |
| `/agents/<agent_id>` | DELETE | Live | Yes | No | Deregister agent |
| `/agents/<agent_id>/heartbeat` | POST | **Live** | Yes | No | Per-agent heartbeat |
| `/agents/<agent_id>/heartbeat` | GET | Live | No | No | Get heartbeat |
| `/agents/sweep-stale` | POST | Live | Yes | No | Stale agent cleanup |

## Intent Routing

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/intents/route` | POST | **Live** | Yes | Depends | Main intent routing |
| `/intents/<intent_id>` | GET | **Live** | No | No | Intent status |
| `/intents/<intent_id>/response` | POST | Live | Yes | No | Record response |
| `/intents/<intent_id>/error` | POST | Live | Yes | No | Record error |
| `/intents/flows` | GET | Dead | No | No | Intent flow listing |
| `/intents/flows/<flow_id>` | GET | Dead | No | No | Flow detail |

## Routing Policy (Duplicate)

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/routing/policy` | GET | Live | No | No | Original policy endpoint |
| `/routing-policy` | GET | **Duplicate** | No | No | V2 naming, same data |
| `/reload-routing-policy` | POST | Dead | Yes | No | Policy reload |

## Control

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/control/ready` | GET | **Live** | No | No | Broker readiness |
| `/control/start` | POST | Live | Yes | No | Start broker |
| `/control/stop` | POST | Live | Yes | No | Stop broker |

## Stats & Status

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/stats` | GET | **Live** | No | No | Broker statistics |
| `/status` | GET | **Live** | No | No | System status |
| `/logs` | GET | Live | No | No | Broker logs |

## ProjectX

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/projectx/contracts` | GET | Live | No | No | List ProjectX contracts |
| `/projectx/contracts` | POST | Dead | Yes | No | Create contract |
| `/projectx/contracts/summary` | GET | Dead | No | No | Contract summary |
| `/projectx/phases/status` | GET | Live | No | No | Phase status |
| `/projectx/phases/status` | POST | Dead | Yes | No | Update phase status |
| `/projectx/phases/summary` | GET | Dead | No | No | Phase summary |

## Tasks

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/tasks` | GET | Live | No | No | Task list |
| `/tasks/<task_id>` | GET | Live | No | No | Task detail |
| `/tasks/queue` | GET | Live | No | No | Task queue |

## Transport (Mesh)

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/transport/status` | GET | Dead | No | No | Transport layer status |
| `/transport/peers` | GET | Dead | No | No | Peer listing |
| `/transport/discover` | POST | Dead | Yes | No | Peer discovery |

## Memory

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/memory/conversations` | GET | Dead | No | No | Conversations |
| `/memory/conversations/<conv_id>` | GET | Dead | No | No | Conversation detail |
| `/memory/conversations` | POST | Dead | Yes | No | Save conversation |
| `/memory/tasks` | GET | Dead | No | No | Memory tasks |
| `/memory/tasks/<slug>` | GET | Dead | No | No | Task detail |
| `/memory/index` | GET | Dead | No | No | Knowledge index |
| `/memory/context-pack` | GET | Dead | No | No | Context packs |

## Dashboard

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/dashboard` | GET | **Live** | No | No | Dashboard HTML |
| `/dashboard/ui` | GET | **Duplicate** | No | No | Same as `/dashboard` |
| `/dashboard/static/app.js` | GET | Live | No | No | Dashboard JS |
| `/dashboard/static/style.css` | GET | Live | No | No | Dashboard CSS |

## Security

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/security/audit-log` | GET | Live | Yes | No | Audit log |

## A2A Routes

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/.well-known/agent-card.json` | GET | **Live** | No | No | A2A agent card |
| `/a2a/tasks` | POST | Live | Yes | No | Submit A2A task |
| `/a2a/tasks/<task_id>` | GET | Live | No | No | A2A task status |
| `/a2a/tasks/types` | GET | Dead | No | No | Task type list |
| `/a2a/agents/projectx/agent.json` | GET | Live | No | No | ProjectX card |
| `/a2a/agents/projectx/tasks` | POST | Live | Yes | No | ProjectX task |
| `/a2a/agents/projectx/health` | GET | Live | No | No | ProjectX health |
| `/a2a/agents/brp/agent.json` | GET | Dead | No | No | BRP card |
| `/a2a/agents/brp/tasks` | POST | Dead | Yes | No | BRP task |
| `/a2a/agents/brp/health` | GET | Dead | No | No | BRP health |
| `/a2a/events` | GET | Live | No | No | A2A events |
| `/a2a/events/<intent_id>` | GET | Dead | No | No | Events by intent |
| `/a2a/events/stream` | GET | Live | No | No | SSE event stream |
| `/a2a/security` | GET | Live | No | No | Security schemes |

## A2A Financial-Ops

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/a2a/agents/financial-ops/agent.json` | GET | Live | No | No | FinOps card |
| `/a2a/agents/financial-ops/tasks` | POST | Live | Yes | No | FinOps task |
| `/a2a/agents/financial-ops/connector-health` | GET | Live | No | No | Connector health |
| `/a2a/agents/financial-ops/proposals` | POST | Live | Yes | No | Submit proposal |
| `/a2a/agents/financial-ops/proposals` | GET | Live | No | No | List proposals |
| `/a2a/agents/financial-ops/proposals/<id>` | GET | Live | No | No | Proposal detail |
| `/a2a/agents/financial-ops/proposals/<id>/approve` | POST | Live | Yes | No | Approve proposal |
| `/a2a/agents/financial-ops/proposals/<id>/reject` | POST | Live | Yes | No | Reject proposal |
| `/a2a/agents/financial-ops/policy-changes` | POST | Live | Yes | No | Submit policy change |
| `/a2a/agents/financial-ops/policy-changes/<id>/approve` | POST | Live | Yes | No | Approve change |
| `/a2a/agents/financial-ops/proposals/<id>/execute` | POST | Live | Yes | No | Execute proposal |
| `/a2a/agents/financial-ops/ledger` | GET | Live | No | No | Spend ledger |
| `/a2a/agents/financial-ops/reconciliation` | POST | Live | Yes | No | Run reconciliation |
| `/a2a/agents/financial-ops/export` | GET | Live | No | No | Export data |
| `/a2a/agents/financial-ops/rollback` | POST | Live | Yes | Yes | Rollback operation |
| `/a2a/agents/financial-ops/rollback/status` | GET | Live | No | No | Rollback status |
| `/a2a/agents/financial-ops/gates` | GET | Live | No | No | Gate status |
| `/a2a/agents/financial-ops/gates/simulate-gate1` | POST | Dead | Yes | No | Gate simulation |
| `/a2a/agents/financial-ops/budget` | GET | Live | No | No | Budget status |

## Financial-Ops (Duplicate — bare routes)

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/rollback/status` | GET | **Duplicate** | No | No | Same as finops rollback/status |
| `/rollback/history` | GET | **Duplicate** | No | No | Rollback history |
| `/gates` | GET | **Duplicate** | No | No | Same as finops/gates |
| `/gates/1` | GET | Live | No | No | Gate 1 status |
| `/gates/2` | GET | Live | No | No | Gate 2 status |
| `/gates/1/sign-off` | POST | Live | Yes | No | Gate 1 sign-off |
| `/gates/2/sign-off` | POST | Live | Yes | No | Gate 2 sign-off |
| `/gates/1/promote` | POST | Live | Yes | Yes | Promote Gate 1 |
| `/gates/2/promote` | POST | Live | Yes | Yes | Promote Gate 2 |
| `/alerts` | GET | Live | No | No | Budget alerts |
| `/alerts/<id>/acknowledge` | POST | Live | Yes | No | Acknowledge alert |

## Mesh Routes

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/mesh/routing/status` | GET | Dead | No | No | Mesh status |
| `/mesh/routing/agents` | GET | Dead | No | No | Mesh agents |
| `/mesh/routing/discover` | POST | Dead | Yes | No | Mesh discovery |
| `/mesh/routing/agent/<agent_id>` | GET | Dead | No | No | Mesh agent info |
| `/mesh/routing/config` | GET,POST | Dead | Yes | No | Mesh config |
| `/mesh/send` | POST | Dead | Yes | No | Mesh send |
| `/mesh/poll` | GET | Dead | No | No | Mesh poll |
| `/mesh/subscribe` | POST | Dead | Yes | No | Mesh subscribe |
| `/mesh/subscriptions` | GET | Dead | No | No | List subs |
| `/mesh/unsubscribe` | POST | Dead | Yes | No | Mesh unsubscribe |
| `/mesh/stats` | GET | Dead | No | No | Mesh stats |
| `/mesh/agent/<agent_id>/status` | GET | Dead | No | No | Agent mesh status |
| `/mesh/channels` | GET | Dead | No | No | Mesh channels |
| `/mesh/events` | GET | Dead | No | No | Mesh events |

## Orchestration

| Route | Method | Status | Needs-Auth | Touches-Venue | Notes |
|-------|--------|--------|------------|---------------|-------|
| `/orchestration/plans` | POST | Live | Yes | No | Create plan |
| `/orchestration/plans/maintenance` | POST | Live | Yes | No | Maintenance plan |
| `/orchestration/plans/demo` | POST | Dead | Yes | No | Demo plan |
| `/orchestration/plans` | GET | Live | No | No | List plans |
| `/orchestration/plans/<plan_id>` | GET | Live | No | No | Plan detail |
| `/orchestration/plans/<plan_id>/execute` | POST | Live | Yes | Yes | Execute plan |

---

## Summary

| Metric | Count |
|--------|-------|
| **Total routes** | ~105 |
| **Live** | ~45 |
| **Dead** | ~40 |
| **Duplicate** | ~8 |
| **Needs-Auth** | ~30 |
| **Touches-Venue** | ~5 |

## Key Findings

1. **Duplicate bare routes:** `/gates/*`, `/rollback/*` exist alongside their A2A-prefixed equivalents. These are convenience aliases that expose the same functions without the `/a2a/agents/financial-ops/` prefix.
2. **Dead mesh routes:** All `/mesh/*` routes appear uncalled by any running agent. Mesh bus is not in the active hot path.
3. **Dead memory routes:** All `/memory/*` routes are uncalled. Memory is accessed through other mechanisms.
4. **Dead A2A BRP routes:** BRP bridge routes are stubbed — BRP is not in the current hot path.
5. **Two intent routing paths:** `/intents/route` (main) and `/agentic/intents/route` (legacy/duplicate). The `/agentic/` prefix is likely deprecated.
6. **Two routing policy paths:** `/routing/policy` and `/routing-policy` — same data, different names.

All routes serve on the same Flask app (port 5555). No routes bypass `CanonicalIntent` — every route goes through `SimpHttpServer` which uses `SimpBroker` internally.
