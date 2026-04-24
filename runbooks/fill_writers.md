# Fill Writers — Day 1 Inventory

All locations that append to persistent trade/fill journals.

## Primary Fill Writer

### `gate4_inbox_consumer.py:467` — `record_trade(payload: dict)`
- **Output file:** `logs/gate4_trades.jsonl`
- **Fields written (sample):** `ts`, `signal_id`, `signal_file`, `symbol`, `side`, `requested_usd`, `executed_usd`, `client_order_id`, `dry_run`, `policy_state_version`, `policy_decision`, `lineage`, `result`, `error`, `available_quote_usd`
- **Missing fields:** `decision_id`, `fill_id`, `is_paper` flag
- **Called from:** Lines 671, 684, 695, 729, 748 (five call sites within the signal processing loop)
- **Also calls:** `append_pnl_entry()` (line 471 → writes to `data/phase4_pnl_ledger.jsonl`), `_record_trade_episode()` (line 472 → writes to `data/phase4_trade_episodes/`)

### `gate4_inbox_consumer.py:375` — `append_pnl_entry(payload: dict)`
- **Output file:** `data/phase4_pnl_ledger.jsonl`
- **Fields:** `ts`, `pnl_type`, `symbol`, `side`, `executed_usd`, `result` (subset of trade_record)

### `gate4_inbox_consumer.py:304` — `_record_trade_episode(payload: dict)`
- **Output file:** `data/phase4_trade_episodes/YYYYMMDD_HHMMSS.json`
- **Fields:** Full payload with extra context (strategy_id, episode metadata)
- **Purpose:** Structured episodes for ML learning

## Secondary Fill Writers

### `simp/organs/quantumarb/pnl_ledger.py` — `PnLLedger` class
- **Output file:** configurable, defaults to `data/pnl_ledger.jsonl`
- **Purpose:** Detailed P&L tracking with `PnLRecord` dataclass (trades with buy/sell legs)
- **Called from:** `quantumarb_agent_phase4.py`, `compounding.py`, `quantum_enhanced_arb.py`

### `simp/organs/quantumarb/compounding.py`
- **Output:** `data/compounding_state.json` (state snapshot), no per-fill journal
- **Purpose:** Growth curve tracking, not fill recording

### `simp/memory/trade_learning.py` / `simp/memory/system_reflection.py`
- **Output file:** `logs/gate4_trades.jsonl` (reads same file as gate4 writes)
- **Purpose:** ML feature extraction from the trade log

## Gap Analysis

| Requirement | Status | Action |
|---|---|---|
| `decision_id` in fills | ⛔ MISSING | Adapter shim needed |
| Canonical path (`state/decision_journal.ndjson`) | ⛔ NOT WRITTEN | New adapter writes to this |
| Schema validation | ⛔ NOT PRESENT | Trade records are plain dicts |
| Paper/live distinction | ✅ PRESENT | `dry_run` boolean flag |
| Policy result in fill | ✅ PRESENT | `result` field with terminal states |
| Signal lineage | ✅ PRESENT | `signal_id` + `lineage` fields |
| P&L distinct from fill log | ✅ PRESENT | Separate PNL ledger |

## Decision

For Day 1, A3 will own writing `state/decision_journal.ndjson` and A2 will own appending fills with `decision_id`. The adapter shim `state/decision_adapter.py` bridges from existing `signal_id`-based records to the new schema until native `decision_id` minting is integrated.
