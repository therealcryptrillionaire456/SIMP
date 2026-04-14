# SIMP FinancialOps Operator Guide v0.7.0

## 1. Overview

SIMP FinancialOps is an A2A-compatible financial operations agent for small purchases, subscriptions, and license renewals. All operations default to **simulated mode** — live payments require explicit opt-in via `FINANCIAL_OPS_LIVE_ENABLED=true` and graduation through two gates.

## 2. Safety Guarantees (Verified)

The following safety mechanisms are **enforced at runtime**:

| Safety Mechanism | Implementation | Verification Status |
|---|---|---|
| **Default Simulated Mode** | `FINANCIAL_OPS_LIVE_ENABLED` defaults to `false` | ✅ Verified |
| **Environment Variable Only** | No hardcoded credentials or config files | ✅ Verified |
| **Stripe Test Key Enforcement** | Only `sk_test_` keys accepted | ✅ Verified |
| **Dry-Run Mode Enforcement** | `execute_small_payment()` raises RuntimeError when `dry_run=True` | ✅ Verified |
| **Append-Only Ledgers** | All JSONL files are append-only, never modified | ✅ Verified |
| **Rollback Instant** | Setting `FINANCIAL_OPS_LIVE_ENABLED` to `false` instantly reverts to simulation | ✅ Verified |
| **Budget Monitoring** | Blocks execution at 100%+ of limit | ✅ Verified |
| **Dual-Control Policy Changes** | Requires two distinct operators | ✅ Verified |

## 3. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FINANCIAL_OPS_LIVE_ENABLED` | `false` | Enable live payment execution. When false, all payments are simulated. |
| `STRIPE_TEST_SECRET_KEY` | (unset) | Stripe test-mode API key. Must start with `sk_test_`. |
| `SIMP_REQUIRE_API_KEY` | `true` | Require API key for authenticated endpoints. |
| `SIMP_API_KEY` | (unset) | API key for authenticated endpoints. |

**Never store credentials in code, config files, or agent cards.** Use environment variables only.

## 4. Spending Limits

| Limit | Value |
|---|---|
| Per-transaction | $20.00 |
| Per-day | $50.00 |
| Per-month | $200.00 |
| Allowed categories | cloud_infrastructure, developer_tools, saas_subscription, office_supplies, software_license |
| Disallowed types | cryptocurrency, gambling, cash_advance, wire_transfer, gift_card, personal_expense |

## 5. Approval Workflow

1. **Submit Proposal**: POST `/a2a/agents/financial-ops/proposals`
2. **Review Risk Flags**: Automatic risk scoring (high_amount, above_half_limit, etc.)
3. **Approve or Reject**: POST `/a2a/agents/financial-ops/proposals/<id>/approve` or `/reject`
4. **Execute**: POST `/a2a/agents/financial-ops/proposals/<id>/execute` (requires `FINANCIAL_OPS_LIVE_ENABLED=true`)

All proposals expire after 24 hours. Policy changes require dual-control (two distinct operators).

## 6. Graduation Gates

### Gate 1 — Operational Readiness
| Condition | Type | Description |
|---|---|---|
| connector_health_7_days | Automated | Payment connector healthy for 7+ consecutive days |
| simulated_payments_20 | Automated | At least 20 simulated payments completed |
| no_connector_errors | Automated | No connector errors in the last 7 days |
| ops_policy_reviewed | Manual | Operations policy reviewed and signed off |

### Gate 2 — Go-Live Readiness
| Condition | Type | Description |
|---|---|---|
| gate1_signed_off | Automated | Gate 1 must be fully signed off |
| approval_workflow_tested | Automated | End-to-end approval workflow tested |
| live_ledger_validated | Automated | Live ledger integrity validated |
| reconciliation_run | Automated | Reconciliation completed successfully |
| rollback_system_operational | Automated | Rollback system tested and operational |
| security_review_signed_off | Manual | Security team sign-off |
| pilot_limits_set | Manual | Pilot spending limits configured |

**Endpoints**: GET `/gates`, GET `/gates/1`, GET `/gates/2`, POST `/gates/<n>/sign-off`, POST `/gates/<n>/promote`

## 7. Rollback

Rollback instantly reverts to simulated-only mode. When `FINANCIAL_OPS_LIVE_ENABLED` is not `true`, the system is always in rollback or never-live state.

- **Trigger**: POST `/a2a/agents/financial-ops/rollback`
- **Status**: GET `/rollback/status`
- **History**: GET `/rollback/history`

When rollback is ACTIVE:
- `execute_approved_payment()` is blocked
- The live ledger can be frozen (no new writes)
- SimulatedSpendLedger remains active

## 8. Budget Monitoring

Real-time budget monitoring with three alert levels:
- **OK**: Under 75% of limit
- **WARNING**: 75-99% of limit
- **CRITICAL**: 100%+ of limit (blocks payment execution)

Anomaly detection alerts when daily spend exceeds 2x the historical average.

**Endpoints**:
- GET `/a2a/agents/financial-ops/budget` (public, no auth)
- GET `/alerts` (authenticated)
- POST `/alerts/<id>/acknowledge` (authenticated)

## 9. Stripe Integration

The StripeTestConnector uses stdlib `urllib` only (no third-party dependencies). It enforces:
- Key must start with `sk_test_` — production keys are rejected
- Full key is NEVER logged — only the last 4 characters
- `authorize()` creates a PaymentIntent with `confirm=false` (dry-run)
- `execute_small_payment()` and `refund()` raise RuntimeError in dry_run mode

When `STRIPE_TEST_SECRET_KEY` is not set, the system falls back to StubPaymentConnector.

## 10. Ledger Architecture

All ledgers are **append-only** (JSONL format):
- `data/financial_ops_proposals.jsonl` — Approval queue events
- `data/live_spend_ledger.jsonl` — Live payment attempts and outcomes
- `data/rollback_log.jsonl` — Rollback state changes
- `data/gate_log.jsonl` — Gate condition and sign-off events

Never delete or modify existing entries. The system rebuilds state by replaying events.

## 11. Data Recovery Procedures

### Agent Registry Recovery
The AgentRegistry uses append-only JSONL persistence in `data/agent_registry.jsonl`. To recover:
```bash
# View agent registration events
tail -f data/agent_registry.jsonl

# Reconstruct current state manually
python3 -c "
import json
agents = {}
with open('data/agent_registry.jsonl', 'r') as f:
    for line in f:
        event = json.loads(line.strip())
        if event['event'] == 'registered':
            agents[event['agent_id']] = event['agent_data']
        elif event['event'] == 'deregistered':
            agents.pop(event['agent_id'], None)
print(f'Current agents: {list(agents.keys())}')
"
```

### Intent Ledger Recovery
The IntentLedger stores all routed intents in `data/intent_ledger.jsonl`. To recover:
```bash
# View recent intents
tail -100 data/intent_ledger.jsonl | jq .

# Count intents by type
cat data/intent_ledger.jsonl | jq -r '.intent_type' | sort | uniq -c
```

### Security Audit Recovery
Security events are logged to `data/security_audit.jsonl`. To recover:
```bash
# View security events
cat data/security_audit.jsonl | jq -c 'select(.event_type == "authentication_failure")'
```

## 12. API Reference

### Public Endpoints (No Auth)
| Method | Path | Description |
|---|---|---|
| GET | `/a2a/agents/financial-ops/agent.json` | A2A agent card |
| GET | `/a2a/agents/financial-ops/connector-health` | Connector health |
| GET | `/a2a/agents/financial-ops/budget` | Budget summary |
| GET | `/rollback/status` | Rollback status |
| GET | `/rollback/history` | Rollback history |
| GET | `/gates` | Both gates status |
| GET | `/gates/1` | Gate 1 status |
| GET | `/gates/2` | Gate 2 status |

### Authenticated Endpoints
| Method | Path | Description |
|---|---|---|
| POST | `/a2a/agents/financial-ops/tasks` | Submit financial op |
| POST | `/a2a/agents/financial-ops/proposals` | Submit payment proposal |
| GET | `/a2a/agents/financial-ops/proposals` | List proposals |
| POST | `/a2a/agents/financial-ops/proposals/<id>/approve` | Approve proposal |
| POST | `/a2a/agents/financial-ops/proposals/<id>/reject` | Reject proposal |
| POST | `/a2a/agents/financial-ops/proposals/<id>/execute` | Execute approved payment |
| POST | `/a2a/agents/financial-ops/rollback` | Trigger rollback |
| POST | `/gates/<n>/sign-off` | Sign off gate condition |
| POST | `/gates/<n>/promote` | Promote gate |
| GET | `/a2a/agents/financial-ops/ledger` | Combined ledger |
| POST | `/a2a/agents/financial-ops/reconciliation` | Run reconciliation |
| GET | `/alerts` | Budget alerts |
| POST | `/alerts/<id>/acknowledge` | Acknowledge alert |

## 13. Persistence Notes

### Components with Full Disk Persistence
- **AgentRegistry**: Saves/loads agent state to `data/agent_registry.jsonl`
- **IntentLedger**: Thread-safe append-only logging to `data/intent_ledger.jsonl`
- **SecurityAuditLog**: Security events to `data/security_audit.jsonl`
- **FinancialOps Ledgers**: All financial events to respective JSONL files

### Components with Partial Persistence
- **RoutingPolicy**: Loaded from `docs/routing_policy.json` on startup
- **OrchestrationManager**: Logs events to `data/orchestration_log.jsonl` but doesn't save/load state

### Components Without Persistence
- **RateLimiter**: Uses `time.monotonic()` - resets on process restart
- **In-memory caches**: DeliveryEngine idempotency cache, etc.

## 14. Version History
- **v0.7.0**: Added safety guarantees verification, data recovery procedures, persistence notes
- **v0.6.0**: Initial operator guide with gates, rollback, and budget monitoring