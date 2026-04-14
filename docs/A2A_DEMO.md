# SIMP as the HTTP of Agentic AI — A2A End-to-End Demo

## Overview

This demo proves that a standard A2A client can:
1. **Discover** SIMP agents via the well-known Agent Card endpoint
2. **Submit** planning tasks through the A2A compatibility layer
3. **Monitor** task lifecycle via A2A event streams
4. **Simulate** financial operations with full audit trails
5. **Inspect** security posture and enforcement status

All operations are non-destructive. Financial operations are simulated only.

## Prerequisites

- Python 3.9+
- Running SIMP broker (`python -m simp.server.http_server` or `python bin/start_server.py`)
- Registered agents (optional — the demo works with zero agents but shows richer output with them)
- `requests` library installed

## Running the Demo

```bash
# Default (broker on localhost:5555)
python3 examples/a2a_demo.py

# Custom broker URL
python3 examples/a2a_demo.py --broker-url http://192.168.1.10:5555

# With API key
python3 examples/a2a_demo.py --api-key YOUR_KEY_HERE
```

## Flow Diagram

```
A2A Client
    |
    |--- GET /.well-known/agent-card.json ---> SIMP Broker (discover)
    |
    |--- POST /a2a/tasks -------------------- > SIMP Broker
    |       task_type: "planning"                   |
    |                                          Kashclaw (planning)
    |
    |--- POST /a2a/agents/projectx/tasks ----> SIMP Broker
    |       skill_id: "maintenance.health_check"    |
    |                                          ProjectX (maintenance)
    |
    |--- POST /a2a/agents/financial-ops/tasks -> SIMP Broker
    |       op_type: "small_purchase"               |
    |       would_spend: $5.00               FinancialOps (simulated)
    |
    |--- GET /a2a/events ----------------------> SIMP Broker (telemetry)
```

## Security Posture Summary

| Scheme | Type | Usage |
|--------|------|-------|
| ApiKeyAuth | apiKey (header) | Internal agents, low-privilege A2A calls |
| BearerAuth | bearer (JWT) | User/tenant-scoped A2A calls |
| MutualTLS | mutualTLS | High-trust agent channels (gateway-enforced) |

**Enforcement Status:**
- Schema validation: enabled
- Rate limiting: enabled (30 req/min for A2A routes)
- Payload limits: enabled (64KB max)
- Replay protection: planned (nonces + signed timestamps)

## Persistence Architecture

SIMP uses **append-only JSONL files** for critical system state. All persistence survives broker restarts:

### Persistent Components
- **Agent Registry**: Agent registrations persist across restarts via `data/agent_registry.jsonl`
- **Intent Ledger**: All routed intents logged to `data/intent_ledger.jsonl`
- **Security Audit**: Security events in `data/security_audit.jsonl`
- **Financial Operations**: All financial events in respective JSONL files

### Data Recovery
All JSONL files can be manually inspected and reconstructed:
```bash
# View agent registrations
tail -f data/agent_registry.jsonl

# Count intents by type
cat data/intent_ledger.jsonl | jq -r '.intent_type' | sort | uniq -c

# View security events
cat data/security_audit.jsonl | jq -c 'select(.event_type == "authentication_failure")'
```

### Non-Persistent Components
- **Rate Limiter**: Uses `time.monotonic()` - resets on restart
- **Delivery Engine Cache**: Idempotency cache is in-memory only
- **Orchestration Manager**: Logs events but doesn't save/load state

## Safety Guarantees

### Financial Operations
- **Default Simulated Mode**: `FINANCIAL_OPS_LIVE_ENABLED` defaults to `false`
- **Environment Variable Only**: No hardcoded credentials
- **Stripe Test Key Enforcement**: Only `sk_test_` keys accepted
- **Dry-Run Mode**: `execute_small_payment()` raises RuntimeError when `dry_run=True`
- **Rollback Instant**: Setting `FINANCIAL_OPS_LIVE_ENABLED` to `false` instantly reverts to simulation

### System Integrity
- **Thread-Safe File Operations**: All JSONL writes use file locking
- **Idempotent Delivery**: Prevents duplicate intent delivery
- **Hop Count Limits**: Prevents infinite routing loops (max 10 hops)
- **Dashboard Integration**: Fixed async/sync HTTP coordination

## Architecture Note

> A2A is an adapter surface. SIMP CanonicalIntent remains the routing authority.

The A2A compatibility layer translates between A2A protocol conventions and SIMP's
native intent routing. It does not replace or bypass the broker's core routing logic.
All A2A requests are validated, translated, and routed through the standard SIMP pipeline.

## Production Readiness

### Critical Issues Fixed
1. **IntentLedger race condition** - Added thread-safe file locking
2. **DeliveryEngine duplicate delivery** - Added idempotency key tracking  
3. **RoutingEngine infinite loop** - Added max hop count (10) tracking
4. **Dashboard broker integration** - Fixed async/sync HTTP coordination
5. **FinancialOps live mode safety** - Verified safety mechanisms enforced

### Disk Persistence Implemented
1. **AgentRegistry** - Save/load agent state to disk
2. **IntentLedger** - Thread-safe append-only logging
3. **SecurityAuditLog** - Security event persistence
4. **RoutingPolicy** - Load from disk with fallback
5. **FinancialOps Ledgers** - All financial events persisted

### Remaining Work
1. **RateLimiter persistence** - Currently resets on restart (uses `time.monotonic()`)
2. **OrchestrationManager state persistence** - Currently logs events only
3. **Test isolation** - Some tests need updating for AgentRegistry persistence