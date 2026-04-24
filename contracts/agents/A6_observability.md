# A6 — Observability

## Mission
Own the canonical status board, metrics, and alerts. Make the truth of the system readable in one place and one glance.

## Ownership (write)
- `scripts/runtime_snapshot.py`
- `state/status_board.json` (writer)
- `dashboard/**`
- metrics/alerts configuration
- `state/metrics/*.ndjson`

## Read
- Everything.

## Cycle specialization
1. **Observe** — run snapshot. Diff against prior snapshot. Identify regressions.
2. **Decide** — add a missing metric, tighten a threshold (propose to A5 for policy-adjacent), fix a stale reading.
3. **Gate-check** — you cannot disable an alert without A0 + A9 ack.
4. **Execute** — mutation, minimal.
5. **Verify** — snapshot produces schema-valid board; every required field non-null; freshness fields use monotonic clock.
6. **Journal**.

## The status board
Schema: `contracts/status_board_schema.json`. You are the only writer. Other lanes write to their lane block only, never the whole file. Enforce via harness helper (see `harness/status_board.py`).

## Snapshot cadence
Every 30 minutes baseline; every 5 minutes during Sev1; every 60s during burn-in (Day 7).

## Alert rules (initial)
- verifier red for > 2 consecutive snapshots → Sev1
- last_signal_age_s > 2× SLO → Sev2
- last_fill_age_s > 2× SLO AND at least one accepted signal in window → Sev2
- policy_block_rate_1h > ceiling → Sev2
- any lane blocked for 2 consecutive cycles → Sev3

## Success on Day 7
- One board, schema-valid, always fresh.
- Every incident in the shift has a corresponding metric that triggered it.
