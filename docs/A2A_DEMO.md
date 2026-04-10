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

## Architecture Note

> A2A is an adapter surface. SIMP CanonicalIntent remains the routing authority.

The A2A compatibility layer translates between A2A protocol conventions and SIMP's
native intent routing. It does not replace or bypass the broker's core routing logic.
All A2A requests are validated, translated, and routed through the standard SIMP pipeline.
