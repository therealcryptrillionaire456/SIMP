# Safety Authority — Day 1 Map

## Single Authority Chain for Live-Mode Decisions

After exhaustive search of the repo, there are **two** files that claim to enforce
trading policy and caps. One is authoritative; the other is secondary.

---

## PRIMARY AUTHORITY: `simp/policies/trading_policy.py`

| Function | What It Enforces | Source of Truth |
|---|---|---|
| `TradingPolicy.__init__()` | Kill switch path, starting capital, daily loss limit, position size | `SIMP_KILL_SWITCH_PATH` env / `data/KILL_SWITCH` |
| `TradingPolicy.kill_switch_active()` | Check if kill switch file exists | `self._kill_switch_path.exists()` |
| `TradingPolicy.activate_kill_switch()` | Write kill switch file | `data/KILL_SWITCH` |
| `TradingPolicy.deactivate_kill_switch()` | Remove kill switch file | `data/KILL_SWITCH` |
| `TradingPolicy.check()` | All pre-trade gating (kill switch, daily loss, position size) | Module-level `MAX_DAILY_LOSS_PCT`, `MAX_POSITION_SIZE_PCT` |
| `TradingPolicy.approve_exchange()` | Exchange allowlist | `EXCHANGE_ALLOWLIST` (environment: `SIMP_LIVE_TRADING_ENABLED` + `SIMP_LIVE_EXCHANGES`) |

### Hard Limits (module-level, override via env)

| Variable | Default | Env Override |
|---|---|---|
| `MAX_DAILY_LOSS_PCT` | 0.02 (2%) | `SIMP_MAX_DAILY_LOSS_PCT` |
| `MAX_POSITION_SIZE_PCT` | 0.05 (5%) | `SIMP_MAX_POSITION_PCT` |
| `MAX_OPEN_POSITIONS` | 3 | `SIMP_MAX_OPEN_POSITIONS` |

### Kill Switch Path

- **Default:** `data/KILL_SWITCH` (relative to repo root)
- **Configurable via:** `SIMP_KILL_SWITCH_PATH` environment variable
- **Also duplicated in `contracts/live_limits.json`:** `kill_switch_path: "state/KILL"`
- **Discrepancy:** `trading_policy.py` uses `data/KILL_SWITCH`; `live_limits.json` says `state/KILL`. **These are different paths.** This is a Sev2.

---

## SECONDARY: `simp/projectx/risk_engine.py`

| Function | What It Enforces | Notes |
|---|---|---|
| `RiskConfig.kill_switch` | Bool field for global halt | NOT file-based — in-memory config |
| `RiskEngine.set_kill_switch()` | Toggle in-memory kill switch | Mirrors the file-based one but independently |
| `RiskEngine._gate_kill_switch()` | Raises `RiskViolation` | Secondary check, called by ProjectX execution |

The risk engine is a separate copy of policy enforcement. It does NOT read
`data/KILL_SWITCH` — it has its own in-memory bool. This is a potential
split-brain source.

---

## Contracts: `contracts/live_limits.json`

This file is described as "human-edited only" by the kit charter. Values:

| Key | Value | trading_policy.py Equivalent | Match? |
|---|---|---|---|
| `daily_cap_usd` | 250.0 | `MAX_DAILY_LOSS_PCT * starting_capital` | ⚠️ Computed, not static |
| `max_position_usd` | 50.0 | `MAX_POSITION_SIZE_PCT * starting_capital` | ⚠️ Computed, not static |
| `max_per_strategy_gross_usd` | 100.0 | — | N/A — no equivalent in trading_policy |
| `max_orders_per_minute` | 6 | — | N/A — no equivalent |
| `kill_switch_path` | `state/KILL` | `data/KILL_SWITCH` | ❌ MISMATCH |
| `mode_file_path` | `state/mode.json` | — | N/A — new concept |
| `allowed_venues` | paper, coinbase, kalshi, alpaca | Derived from `EXCHANGE_ALLOWLIST` | ⚠️ Not directly comparable |

---

## Verdict: Sev2 — Dual Authority

**Finding:** There are two files that claim authority over live-mode decisions:
1. `simp/policies/trading_policy.py` (primary, file-based kill switch)
2. `simp/projectx/risk_engine.py` (secondary, in-memory kill switch)

Both must agree. Currently:
- `trading_policy.py` reads `data/KILL_SWITCH`
- `risk_engine.py` has its own in-memory flag
- `contracts/live_limits.json` says `state/KILL`

**Recommendation:** Unify to `state/KILL` as the single kill switch path. Wire
`risk_engine.py` to read the same file. This requires human arbitration before
changing — no mutations made today.

## Canonical Safety Authority (enforced today)

For Day 1, `simp/policies/trading_policy.py` is the **single authoritative
chain**. All kill-switch and policy gating questions should be answered by
reading that file and its `check()` method. The secondary `risk_engine.py`
path is acknowledged but NOT authoritative.
