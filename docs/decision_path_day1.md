# Decision Path — Day 1 Map

## Current "Signal → Trade" Flow

```
quantum_signal_bridge.py                    (file-based signal source)
        │ writes to: data/quantum_broadcast/*.json
        ▼
gate4_inbox_consumer.py                     (watches inbox, processes signals)
        │ creates: trade_record dict with signal_id + lineage
        │ writes to: logs/gate4_trades.jsonl
        │ writes to: data/phase4_pnl_ledger.jsonl
        ▼
simp/routing/signal_router.py               (MultiPlatformRouter)
        │ RouterSignal → PlatformResult
        │ NO persistent decision journal
        ▼
simp/organs/quantumarb/                     (execution layer)
        │ arb_detector: ArbOpportunity → trades
        │ executor: trade execution (via exchange connectors)
        │ pnl_ledger: PnLRecord → data/pnl_ledger.jsonl
        │ compounding: growth curve tracking
```

## Where `decision_id` Could Be Minted (Least-Change Options)

| Location | Change Required | Complexity | Owner |
|---|---|---|---|
| **A** `gate4_inbox_consumer.py:650` | Add `decision_id = f"g4:{signal_id}"` when building `trade_record` | LOW — add one field | A2 |
| **B** `simp/routing/signal_router.py:795` (route method) | Mint `decision_id` when `RouterResult` is created | LOW — in the existing signal processing path | A3 |
| **C** `simp/task_ledger.py:79` (create_task) | Add optional `decision_id` field to task schema | LOW — new optional field | A3 |
| **D** `simp/models/canonical_intent.py` | Add `decision_id` to intent metadata | MEDIUM — touches core schema (protected file) | A4 |

## Recommendation (A3 → A2 handoff)

**Option A** is the path of least resistance for Day 1. The adapter shim
`state/decision_adapter.py` already implements this as `legacy:<signal_id>`.

For **Day 2**, Option B + C should be the native path:
- `signal_router.py` mints `decision_id` when a `RouterSignal` is routed
- `task_ledger.py` carries `decision_id` for downstream tracking
- `gate4_inbox_consumer.py` reads `decision_id` from the signal/inbox file and passes it through

## Schema Compatibility: `task_ledger.py`

`TaskLedger.create_task()` uses a dict-based schema. Adding an optional `decision_id`
field is backward compatible:
- Existing records won't have it → reads as `None`
- New records can carry it → no schema validation rejects it
- **Verdict: GREEN** — no schema break

The same applies to `state/decision_journal.ndjson` — it's a new file, no migration needed.
