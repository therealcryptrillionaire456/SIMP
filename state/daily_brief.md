# Day 1 — Stabilize the Command Surface

## Objective
By end of Day 1 every lane must be able to observe the system through one canonical board, the verifier must run cleanly against the real repo, and the swarm must be able to start/stop without manual log spelunking.

## Mode
**Shadow** — same code path, orders replaced with paper-fills at last venue mid. Used for remediation baseline.

## Top 3 Risks

**R1 — startup drift:** `startall.sh` launches things not in the canonical hot path. Some processes may be orphans or dead entries. Need to inventory and map every process to the canonical path.

**R2 — decision journal schema drift:** Existing code may write fills without `decision_id`. The lineage stage in the verifier requires decision IDs to pass. A post-hoc shim may be needed for the first 24h.

**R3 — policy surface unclear:** Multiple files may claim to enforce caps (budget, position, live mode). Need to find every file matching `policy_guard*`, `kill_switch*`, `budget*`, `risk_caps*`, `live_mode*` and produce a single authority map.

## Queue (10 cards, one per lane)

| Lane | Card | Action |
|------|------|--------|
| A0 | d1_a0_01 | Publish daily brief and close-out checklist |
| A1 | d1_a1_01 | Inventory every process startall.sh launches; map to canonical hot path; mark orphans |
| A2 | d1_a2_01 | Run verify_revenue_path.py against real repo; enumerate every failing stage |
| A3 | d1_a3_01 | Read task_ledger.py and builder_pool.py; confirm where a decision could be emitted; propose minimal adapter |
| A4 | d1_a4_01 | Inventory A2A routes in http_server.py; mark each as live/dead/duplicate |
| A5 | d1_a5_01 | Locate every file matching policy_guard*, kill_switch*, budget*, risk_caps*, live_mode*; produce single authority map |
| A6 | d1_a6_01 | Run snapshot every 30s for 1h; post baseline status_board and first metrics summary |
| A7 | d1_a7_01 | Classify top-level files: critical/operational/experimental/historical/generated |
| A8 | d1_a8_01 | Read AGENTS.md and README.md; mark claims by tier (Implemented/Prototype/Aspirational) |
| A9 | d1_a9_01 | Independently re-run each lane's Day 1 verification claim; post first truth report |

## Shift Timeline
- Hours 0-1: Step 0 (land kit) + Step 1 (open shift)
- Hours 1-6: Step 2 (lane-by-lane work)
- Hour 6: Step 3 (gate check)
- Hours 7-8: Step 4 (close-out, handoff, truth report)

## Promotion Gate (to fully_live)
Requires A9 to confirm:
1. Verifier green for 2 consecutive snapshots
2. Status board schema-valid, all lanes reported, 0 Sev1 open
3. Safety authority doc: exactly one authoritative chain
4. Kill-switch test: green ↔ red ↔ green demonstrated
5. Policy-blocked path: synthetic block recorded, not dropped silently
