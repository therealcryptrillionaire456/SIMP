# Failure Classes — Day 1 Verifier Stages

The verifier (`scripts/verify_revenue_path.py`) runs 12 stages. Five stages can fail with specific terminal statuses. Below is each failure class with the exact code path that should set it.

| # | Stage | Terminal States | Code Path That Should Set It |
|---|-------|-----------------|------------------------------|
| 1 | **execution_terminal** | `executed`, `policy_blocked`, `exchange_error`, `strategy_rejected`, `stale` | `gate4_inbox_consumer.py:650-729` — trade_record `result` field. Sets: `dry_run_ok`→`executed`, `policy_blocked:*`→`policy_blocked`, exchange exceptions→`exchange_error`. Verifier reads `policy_result.status` from decision journal. |
| 2 | **decision_present** | Any fill must have a `decision_id` | `state/decision_adapter.py` — translates existing `signal_id` to `legacy:<signal_id>`. Native path: A3's future `decision_id` minting in `simp/routing/builder_pool.py` or `simp/task_ledger.py`. Verifier reads from `state/decision_journal.ndjson`. |
| 3 | **lineage** | `decision_id` + `created_at` must exist; execution must reference known decision | `gate4_inbox_consumer.py:650` — `signal_id` and `lineage` fields already present. After adapter runs, `decision_id` appears in decision_journal. Verifier checks: fill references a known decision_id, decision has `created_at` and `policy_result`. |
| 4 | **policy_bypass_check** | Every execution must have a policy evaluation record | `gate4_inbox_consumer.py:671-729` — every trade_record has `policy_decision` and `policy_state_version`. The decision adapter copies `policy_result.status` from the trade record's `result` field. Verifier checks: `policy_result` exists in decision entry, status is not blank. |
| 5 | **signal_freshness** | Latest signal ≤ 60s old during market hours | `gate4_inbox_consumer.py` reads from inbox directory. Freshness tracked via `signal_mtime` + `_age_seconds()`. Verifier reads from decision journal entries with `created_at` field. |

## Terminal Status Mapping

| `trade_record.result` | Decision `policy_result.status` | Verdict |
|---|---|---|
| `dry_run_ok` | `executed` | GREEN (paper) |
| `policy_blocked:capital_budget` | `policy_blocked` | GREEN (policy working) |
| `policy_blocked: *` | `policy_blocked` | GREEN (policy working) |
| `exchange_error` | `exchange_error` | GREEN (terminal) |
| `strategy_rejected` | `strategy_rejected` | GREEN (terminal) |
| (no trade_record) | `stale` | YELLOW (permitted, but tracked) |
| (unknown) | (missing) | RED — broken lineage |

## Verification

Each failure class maps to exactly one code path. Changes to any path must update the corresponding verifier stage assertion. A9 validates this table independently.
