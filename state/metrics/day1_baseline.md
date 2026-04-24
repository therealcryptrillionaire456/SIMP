# Day 1 Baseline Metrics

Generated: 2026-04-24T07:34:00Z
Mode: shadow
Snapshot interval: 30s (proposed)

## System State
- Broker: DOWN (not started)
- HTTP Server: DOWN (not started)
- Orchestration Loop: DOWN (not started)
- Dashboard: DOWN (not started)
- Signal Bridge: DOWN (not started)
- Gate4 Consumer: DOWN (not started)

## Verifier (pre-startup)
- Overall: RED (expected)
- Passing stages: kill_switch, mode, bridge_reachable, policy_evaluated, execution_terminal, fill_freshness, lineage, policy_bypass_check, shadow_integrity
- Failing stages: processes (Sev2), signal_freshness (Sev3), decision_present (Sev3, pre-first-trade)

## Policy
- Live mode: shadow
- Budget remaining: $250.00 (contract limit)
- Max position: $50.00
- Daily cap: $250.00
- Block rate (1h): 0.0% (no signals yet)
- Kill switch: NOT SET

## Freshness
- Last signal age: N/A (no signals)
- Last fill age: N/A (no fills)
- Consumer backlog: 0
- Bridge RTT: N/A

## Incidents
- d1_i001: processes stage red (Sev2)
- d1_i002: signal_freshness stage red (Sev3)

## Safety Authority
- Primary: `simp/policies/trading_policy.py::TradingPolicy.check()`
- Secondary: `simp/projectx/risk_engine.py::RiskEngine._gate_kill_switch()`
- **Sev2:** Kill switch path mismatch — `contracts/live_limits.json` says `state/KILL`, `trading_policy.py` defaults to `data/KILL_SWITCH`

## KPI Baselines (pre-system)
| Metric | Value | Target |
|--------|-------|--------|
| Signal freshness | N/A | ≤ 60s |
| Fill freshness | N/A | ≤ 300s |
| Bridge RTT p95 | N/A | ≤ 3000ms |
| Verifier pass rate | 0% (3/12 green) | ≥ 95% |
| Policy block rate | 0% | ≤ 5% |
| Budget remaining | $250.00 | ≥ $25.00 |
| Open Sev1 | 0 | 0 |
| Open Sev2 | 1 (kill switch path) | 0 |
| Open Sev3 | 2 (freshness, decisions) | 0 |
