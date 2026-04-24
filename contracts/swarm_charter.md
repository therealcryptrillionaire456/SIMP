# SIMP Swarm Charter (v1)

## Purpose
Drive SIMP from "operable runtime" to "closed-loop profit seeker" in 7 days of continuous autonomous execution, in **Fully Live** mode, without breaching safety gates.

## Non-negotiables
1. **Kill switch is sovereign.** The kill-switch file path is the only authority that supersedes every agent. If it is set, every agent halts mutation and execution within one cycle.
2. **No agent may widen its own live-trading permissions.** Policy, budget, position, and venue caps are read-only to all non-human actors.
3. **Every live trade must have a `decision_id` with lineage** (signal → score → decision → policy → execution → feedback). Trades without lineage are automatic Sev1.
4. **Verifier is the promotion gate, not the log feed.** `scripts/verify_revenue_path.py` result drives status; it must distinguish {executed, policy_blocked, exchange_error, strategy_rejected, stale} as terminal states.
5. **One canonical hot path.** `quantum_signal_bridge → gate4_inbox_consumer → trade log → verify_revenue_path.py`. All other paths are deprecated-or-adapter.
6. **Ownership does not overlap on mutation.** Agents share read access; write access is partitioned (see `ownership_matrix.md`).
7. **Every shift ends with an A9 truth report.** If A9 says regressed, the next shift starts in remediation, not new work.

## Operating Modes
- `fully_live`: real orders, real venues, real capital. Daily budget and position caps enforced at broker + policy layers.
- `shadow`: same code path, orders replaced with paper-fills at last venue mid. Used for remediation after a Sev1.
- `halt`: kill switch set. Only A5 (Safety) and A0 (Commander) may act; actions limited to diagnosis and rollback.

Mode transitions are a commander-only action and are journaled.

## Severity Ladder
- **Sev1** — revenue loop broken (verifier red, no fresh fills, unlineaged trade, safety gate bypass).
- **Sev2** — stale (signals or fills older than SLO, but loop intact).
- **Sev3** — drift (config, docs, repo, or protocol inconsistency).
- **Sev4** — hygiene (dead code, naming, cosmetic).

Sev1 preempts all lanes. Sev2 preempts the owning lane. Sev3/4 runs in the background.

## SLOs (initial; tuned on Day 2)
- Signal freshness: latest accepted signal ≤ 60s old during market hours.
- Fill freshness: latest successful fill ≤ 5 min old when at least one live signal has been accepted in that window.
- Bridge round-trip: signal accepted → execution attempted ≤ 3s p95.
- Verifier pass rate over rolling 6h: ≥ 95%.
- Policy-block rate: ≤ 5% of attempted executions (above this = Sev2 and A5 investigates).

## Swarm Roster (stable for 7 days)
- A0 Commander
- A1 Runtime
- A2 Revenue
- A3 Decision
- A4 Protocol
- A5 Safety
- A6 Observability
- A7 Repo Hygiene
- A8 Docs Brain
- A9 Auditor (independent of A0)

## Shift Structure
Three 8-hour shifts per day. Same agent identities span all shifts — context compounds. Every 30 minutes each lane runs its cycle (see `cycle_contract.md`). Every shift ends with a handoff note (see `templates/handoff.md`).
