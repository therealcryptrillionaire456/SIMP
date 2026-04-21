# Agent Channel Map

This is the expected default mesh topology for the current hot runtime. It is
used by the wire-up audit to flag agents with no channel edges and to
re-subscribe known agents when the broker mesh has drifted after a restart.

| Agent | Expected Channels |
| --- | --- |
| `projectx_native` | `system`, `safety_alerts`, `maintenance_requests`, `system_health`, `trade_updates` |
| `projectx_quantum_advisor` | `system`, `projectx_tasks`, `maintenance_requests`, `quantum_advisory`, `trade_updates`, `system_health` |
| `quantum_signal_bridge` | `system`, `quantum`, `trade_signals` |
| `quantum_advisory_broadcaster` | `system`, `quantum_advisory`, `trade_updates` |
| `quantum_intelligence_prime` | `system`, `quantum` |
| `goose_orchestrator` | `system`, `orchestration_commands`, `maintenance_requests` |
| `goose_bridge` | `system`, `maintenance_requests` |
| `goose_kloutbot_bridge` | `system`, `maintenance_requests`, `trade_updates` |
| `kloutbot` | `system`, `trade_updates`, `maintenance_events` |
| `ktc_agent` | `system`, `trade_updates`, `maintenance_events` |
| `brp_audit_consumer` | `system`, `safety_alerts` |

Notes:
- `gate4_real` is currently file-inbox driven, but its trade results are mirrored
  onto `trade_updates`.
- `quantumarb_phase4` remains a file-based execution surface and is therefore
  reported separately from mesh-native consumers.
