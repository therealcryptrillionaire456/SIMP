# SIMP Protocol Conformance Guide

This document defines the conformance requirements for the SIMP protocol (Standardized Inter-agent Message Protocol). It covers broker behavior, intent delivery, routing, task tracking, orchestration, and A2A interoperability.

## 1. Broker Behavior

| Requirement | Description |
|---|---|
| B-1 | Broker starts in `INITIALIZING` state and must transition to `RUNNING` before processing intents. |
| B-2 | `register_agent()` returns `True` on success, `False` on duplicate or limit reached. |
| B-3 | `route_intent()` is `async def` and must remain awaitable. |
| B-4 | Unknown target agents receive `AGENT_NOT_FOUND` error with intent_id in response. |
| B-5 | `record_response()` and `record_error()` return `bool` and update `IntentRecord`. |
| B-6 | Statistics include: intents_received, intents_routed, intents_completed, intents_failed, agents_online. |

## 2. Intent Delivery (Sprint 51)

| Requirement | Description |
|---|---|
| D-1 | File-based agents (endpoint contains "(file-based)" or not "http") always receive `FILE_BASED_SKIP`. No HTTP is attempted. |
| D-2 | HTTP delivery POSTs to `{endpoint}/intent` with `Content-Type: application/json`. |
| D-3 | On connection error: retry up to `max_attempts` (default 3) with exponential backoff (1s, 2s). |
| D-4 | On HTTP 4xx/5xx: fail immediately with `FAILED_HTTP`, no retry. |
| D-5 | On timeout: fail immediately with `FAILED_TIMEOUT`, no retry. |
| D-6 | Response body is truncated to 500 characters. |
| D-7 | `DeliveryResult` always includes status, attempts, and elapsed_ms. |
| D-8 | Only stdlib `urllib` is used for HTTP — no `requests` library. |

## 3. Task Ledger (Sprint 52)

| Requirement | Description |
|---|---|
| L-1 | Ledger is append-only JSONL at `data/task_ledger.jsonl`. |
| L-2 | `append()` never raises exceptions — errors are logged. |
| L-3 | `load_pending()` skips corrupt (non-JSON) lines silently. |
| L-4 | Each appended record includes a `ledger_ts` timestamp. |
| L-5 | `expire_old_records()` marks aged pending intents as `expired` and appends expiration events. |
| L-6 | `rotate_if_needed()` moves the file when it exceeds `max_size_mb` (default 100 MB). |
| L-7 | Broker appends to ledger after: route_intent (success or failure), record_response, record_error. |

## 4. Routing Engine (Sprint 53)

| Requirement | Description |
|---|---|
| R-1 | Resolution order: explicit target → policy primary → fallback chain → capability match → None. |
| R-2 | Explicit target (non-empty, non-"auto") always wins — no policy lookup. |
| R-3 | Policy rules loaded from `docs/routing_policy.json`. |
| R-4 | `reload_policy()` hot-reloads from disk without restart. |
| R-5 | Capability match scans `agent.metadata.capabilities` for `required_capability`. |
| R-6 | RoutingDecision includes: target_agent, reason, intent_type, policy_matched. |

## 5. Orchestration (Sprint 54)

| Requirement | Description |
|---|---|
| O-1 | Plans are created with `create_plan()` and executed with `execute_plan()`. |
| O-2 | Execution is sequential — steps run in order. |
| O-3 | Execution stops on the first failed step; remaining steps stay `pending`. |
| O-4 | Each step emits an event to `data/orchestration_log.jsonl`. |
| O-5 | Plan templates: maintenance, analysis, full demo. |
| O-6 | Plans are queryable by ID and listable. |

## 6. Intent Format

| Requirement | Description |
|---|---|
| I-1 | `route_intent()` response always includes `intent_id` and `timestamp`. |
| I-2 | If `intent_id` is not provided, the broker generates a UUID. |
| I-3 | Successful routing response includes `delivery_status`. |
| I-4 | `IntentRecord` includes: delivery_status, delivery_attempts, delivery_elapsed_ms. |

## 7. HTTP API

| Requirement | Description |
|---|---|
| H-1 | `/health` returns 200 with status and state. |
| H-2 | `/stats` returns broker statistics including `task_ledger` section. |
| H-3 | `/routing-policy` (GET, auth) returns current policy summary. |
| H-4 | `/reload-routing-policy` (POST, auth) reloads policy and returns rule count. |
| H-5 | `/orchestration/plans` supports POST (create) and GET (list). |
| H-6 | `/orchestration/plans/<id>` (GET) returns plan details. |
| H-7 | `/orchestration/plans/<id>/execute` (POST) executes the plan. |

## 8. A2A Card Invariants

| Requirement | Description |
|---|---|
| A-1 | `/.well-known/agent-card.json` returns valid JSON with no secrets. |
| A-2 | Card never contains: api_key, secret, password, token values. |
| A-3 | File-based agents are excluded from A2A cards. |
| A-4 | FinancialOps card is available at `/a2a/agents/financial-ops/agent.json`. |

## 9. Backward Compatibility

| Requirement | Description |
|---|---|
| BC-1 | `register_agent(agent_id, agent_type, endpoint, metadata=None)` signature unchanged. |
| BC-2 | `route_intent()` remains `async def`. |
| BC-3 | `record_response()` and `record_error()` signatures unchanged. |
| BC-4 | `get_statistics()` returns all previously-documented keys. |
| BC-5 | CanonicalIntent and broker routing authority remain untouched. |
| BC-6 | All 452 pre-existing passing tests continue to pass. |
