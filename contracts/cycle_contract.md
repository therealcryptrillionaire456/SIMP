# 30-Minute Cycle Contract

Every agent lane runs the same 6-step cycle. Each cycle produces one journal entry.

## The Cycle
1. **Observe** — read `state/status_board.json`, own lane's pending queue, last handoff note, last A9 truth report.
2. **Decide** — select 1–3 mutations within your ownership scope. If no mutation is safe, you must still report and enqueue next candidates.
3. **Gate-check** — before any write, confirm:
   - kill switch is not set
   - no open Sev1 blocking this lane
   - your mutation touches only files you own per `ownership_matrix.md`
   - if the change affects live trading in any way, A5 must be in the approver set
4. **Execute** — make the mutation. Run the minimal test that proves it. Never batch unrelated changes.
5. **Verify** — run `scripts/verify_revenue_path.py` (for A1/A2/A3/A5) or the lane's conformance probe (for A4/A6/A7/A8). If red, revert within this cycle.
6. **Journal** — append one line to `state/cycle_journal.ndjson` using the schema in `templates/cycle_journal_schema.json`.

## Hard stops inside a cycle
- Kill switch becomes set → finish current write safely, log `halt_observed`, exit cycle.
- Verifier regresses from green → auto-rollback last mutation, escalate Sev1, exit cycle.
- Two consecutive cycles produce no forward progress → lane must post a `blocked` journal entry and A0 rebalances.

## Commander (A0) cycle overrides
- Can coalesce two lanes' cycles if they touch adjacent subsystems.
- Can promote any Sev2 to Sev1.
- Cannot bypass A5.

## Auditor (A9) cycle
A9's cycle is read-only except for:
- `state/incidents/*.md`
- adding assertions to `scripts/verify_revenue_path.py`
- writing `state/shift_truth_report.md` at shift end

A9 runs a superset probe: it re-executes every other lane's most recent verification claim.
