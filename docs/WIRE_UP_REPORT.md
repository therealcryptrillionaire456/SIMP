# Wire-Up Report

- Generated at: 2026-04-21T16:42:09.951404+00:00
- Broker URL: http://127.0.0.1:5555
- Registered agents reported by broker: 7
- Inventory source: agent_registry
- Channel source: expected_map_fallback

## Edge Inventory

| Producer | Consumer | Channel | Status |
| --- | --- | --- | --- |
| brp_audit_consumer | * | `system` | idle |
| brp_audit_consumer | * | `safety_alerts` | idle |
| goose_kloutbot_bridge | * | `system` | idle |
| goose_kloutbot_bridge | * | `maintenance_requests` | idle |
| goose_kloutbot_bridge | * | `trade_updates` | idle |
| ktc_agent | * | `system` | idle |
| ktc_agent | * | `trade_updates` | idle |
| ktc_agent | * | `maintenance_events` | idle |
| projectx_native | * | `system` | idle |
| projectx_native | * | `safety_alerts` | idle |
| projectx_native | * | `maintenance_requests` | idle |
| projectx_native | * | `system_health` | idle |
| projectx_native | * | `trade_updates` | idle |
| projectx_quantum_advisor | * | `system` | idle |
| projectx_quantum_advisor | * | `projectx_tasks` | idle |
| projectx_quantum_advisor | * | `maintenance_requests` | idle |
| projectx_quantum_advisor | * | `quantum_advisory` | idle |
| projectx_quantum_advisor | * | `trade_updates` | idle |
| projectx_quantum_advisor | * | `system_health` | idle |
| quantum_intelligence_prime | * | `system` | idle |
| quantum_intelligence_prime | * | `quantum` | idle |
| quantum_signal_bridge | * | `system` | idle |
| quantum_signal_bridge | * | `quantum` | idle |
| quantum_signal_bridge | * | `trade_signals` | idle |

## Heartbeats

| Agent | Last Heartbeat | Stale | Expected Channels Missing | Recent Activity |
| --- | --- | --- | --- | --- |
| brp_audit_consumer | 2026-04-21T16:37:00Z | False | none | none |
| goose_kloutbot_bridge | 2026-04-21T16:37:07Z | False | none | none |
| ktc_agent | 2026-04-20T23:38:01Z | False | none | none |
| projectx_native | 2026-04-21T16:36:56Z | False | none | none |
| projectx_quantum_advisor | 2026-04-21T16:37:15Z | False | none | none |
| quantum_intelligence_prime | 2026-04-21T16:37:13Z | False | none | none |
| quantum_signal_bridge | 2026-04-21T16:37:13Z | False | none | none |

## Revenue Path

- Latest successful fill: `{"ts": "2026-04-21T16:36:53.056153+00:00", "signal_id": "eb50a1a4-2912-412f-88e0-5fdd89025a63", "signal_file": "quantum_signal_1776789237_eb50a1a42912.json", "symbol": "BTC-USD", "side": "BUY", "requested_usd": 1.0, "executed_usd": 1.0, "client_order_id": "qsig-eb50a1a4-BTC-USD-479a97", "dry_run": false, "market_price": 76141.89, "response": {"success": true, "success_response": {"order_id": "5f8886c7-6362-41cf-95fe-7a94fd263240", "product_id": "BTC-USD", "side": "BUY", "client_order_id": "qsig-eb50a1a4-BTC-USD-479a97", "attached_order_id": ""}, "order_configuration": {"market_market_ioc": {"quote_size": "1.0", "rfq_enabled": false, "rfq_disabled": false, "reduce_only": false}}}, "result": "ok", "error_classification": null}`
- Broker health surface: `unavailable`
- Mesh activity source: `registry/expected-map fallback`

## Snapshot Start

```markdown
# SIMP Hot Runtime Snapshot

- Timestamp: 2026-04-21T16:18:46.303412+00:00
- Broker: up
- Dashboard: up
- ProjectX: up
- Gate4 latest trade: BTC-USD BUY -> exception:ConnectionError
- Bridge: 2026-04-21 12:18:20,842 [quantum_signal_bridge] INFO QIP intent sent [e3ec5bcf], waiting up to 30s...

## Process Counts
- projectx_supervisor: 1
- projectx_guard: 1
- gate4_consumer: 1
- quantum_signal_bridge: 1
- quantum_mesh_consumer: 1
- quantum_advisory_broadcaster: 1
```

## Verify Start

```json
{
  "timestamp": "2026-04-21T16:18:49.981539+00:00",
  "ok": false,
  "checks": {
    "broker_up": {
      "ok": true
    },
    "dashboard_up": {
      "ok": true
    },
    "projectx_up": {
      "ok": true
    },
    "gate4_consumer_running": {
      "ok": true
    },
    "quantum_bridge_running": {
      "ok": true
    },
    "latest_trade_present": {
      "ok": true
    },
    "latest_trade_fresh": {
      "ok": false,
      "age_seconds": 15709.19
    },
    "latest_trade_successful": {
      "ok": false,
      "result": "exception:ConnectionError",
      "symbol": "BTC-USD",
      "side": "BUY",
      "order_id": null
    }
  },
  "latest_trade": {
    "ts": "2026-04-21T11:57:00.793053+00:00",
    "signal_id": "a6744402-fecf-4364-85ce-a9d2d4eacae7",
    "signal_file": "quantum_signal_1776768784.json",
    "symbol": "BTC-USD",
    "side": "BUY",
    "requested_usd": 1.0,
    "executed_usd": 1.0,
    "client_order_id": "qsig-a6744402-BTC-USD-0b1a28",
    "dry_run": false,
    "result": "exception:ConnectionError",
    "error": "HTTPSConnectionPool(host='api.coinbase.com', port=443): Max retries exceeded with url: /api/v3/brokerage/orders (Caused by NameResolutionError(\"HTTPSConnection(host='api.coinbase.com', port=443): Failed to resolve 'api.coinbase.com' ([Errno 8] nodename nor servname provided, or not known)\"))"
  }
}
```

## Verify Final

```json
{
  "timestamp": "2026-04-21T16:41:10.246084+00:00",
  "ok": true,
  "latest_successful_trade": {
    "symbol": "BTC-USD",
    "side": "BUY",
    "order_id": "5f8886c7-6362-41cf-95fe-7a94fd263240"
  },
  "breaker_reset_state": {
    "cooldown_until": null,
    "consecutive_losses": 0,
    "transient_errors": 0
  }
}
```

## Watchtower Final

```text
SYSTEM HEALTHY
No issues detected. All systems operational.
Sections 1, 4, 5, 6, and 7 returned clean.
Test agent 8888 remains optional and absent by design.
```
