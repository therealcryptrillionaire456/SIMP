# BRP End-to-End Validation Report

## Date: 2026-04-10

## Validation Commands Executed

```bash
python -m py_compile simp/security/brp_models.py          # PASS
python -m py_compile simp/security/brp_bridge.py           # PASS
python -m py_compile simp/server/broker.py                  # PASS
python -m py_compile simp/integrations/kashclaw_shim.py     # PASS
python -m py_compile simp/agents/quantumarb_agent.py        # PASS

python -m pytest tests/test_brp_bridge.py -v                # 22/22 PASS
python -m pytest tests/test_brp_end_to_end_smoke.py -v      # 12/12 PASS
```

## Scenarios Validated

### 1. mother_goose_plan_review
- **Status:** PASS
- **Tests:** `TestMotherGoosePlanReview` (3 tests)
- Multi-step plan evaluated by BRP via `BRPBridge.evaluate_plan()`
- Broker wired with `evaluate_plan()` method and auto-review in `route_intent()`
- Plan with restricted step gets elevated threat score >= 0.8
- Plans and responses persisted to JSONL

### 2. kashclaw_trade_shadow_gate
- **Status:** PASS
- **Tests:** `TestKashClawTradeShadowGate` (2 tests)
- KashClaw `handle_trade()` emits BRPEvent before trade execution
- BRP metadata attached to structured response under `brp` key
- Post-action BRP observation persisted to JSONL
- Trade path works identically when `brp_bridge=None` (backward compatible)

### 3. quantumarb_shadow_observation
- **Status:** PASS
- **Tests:** `TestQuantumArbShadowObservation` (1 test)
- QuantumArb `_process_inbox()` calls `_emit_brp_shadow_observation()` after arb evaluation
- Shadow observation emits BRPEvent and BRPObservation via module-level bridge
- Arb decision outcomes are never modified by BRP
- Shadow tags correctly attached to observation records

### 4. restricted_action_escalation
- **Status:** PASS
- **Tests:** `TestRestrictedActions` (6 tests) + `TestRestrictedActionEscalation` (3 tests)
- All 6 restricted actions flagged with threat >= 0.8
- Enforced mode: DENY for restricted actions
- Shadow mode: SHADOW_ALLOW regardless of threat
- Advisory mode: ELEVATE for high-threat, never DENY

### 5. Feature Flag Checks
- **Status:** PASS
- **Tests:** `TestFeatureFlags` (3 tests) + `TestShadowAllow` (3 tests)
- BRP disabled (`brp_bridge=None`) does not break legacy path
- Advisory mode enriches without blocking
- Shadow mode always returns SHADOW_ALLOW
- Disabled mode returns LOG_ONLY

### 6. JSONL Persistence
- **Status:** PASS
- **Tests:** `TestJSONLPersistence` (5 tests)
- Events, plans, observations, responses all persist to JSONL
- Multiple events correctly appended
- Records contain correct event IDs for correlation

## Files Created

| File | Purpose |
|------|---------|
| `simp/security/__init__.py` | Security module init |
| `simp/security/brp_models.py` | BRP typed schemas and enums |
| `simp/security/brp_bridge.py` | BRP bridge with JSONL persistence |
| `tests/test_brp_bridge.py` | 22 unit tests |
| `tests/test_brp_end_to_end_smoke.py` | 12 smoke tests |
| `simp/docs/brp_event_schema.md` | Schema contract docs |
| `simp/docs/brp_mother_goose_integration.md` | Integration points docs |
| `simp/docs/brp_end_to_end_validation.md` | This file |

## Files Modified

| File | Changes |
|------|---------|
| `simp/server/broker.py` | Added BRP imports, `brp_bridge` to constructor, `evaluate_plan()` method, auto plan review in `route_intent()`, BRP metadata in route result |
| `simp/integrations/kashclaw_shim.py` | Added BRP imports, `brp_bridge`/`brp_mode` to constructor, pre-trade BRP event, post-trade BRP observation in `handle_trade()`, BRP metadata in response |
| `simp/agents/quantumarb_agent.py` | Added `_get_brp_bridge()`, `_emit_brp_shadow_observation()` helper, BRP shadow observation call in `_process_inbox()` after arb evaluation |

## Flock Bringup Fixes (2026-04-10)

### BRP JSONL Path Resolution
- **Issue:** `BRPBridge.__init__` used `Path("data/brp")` which resolved relative to CWD
- **Fix:** Changed to resolve relative to repo root via `Path(__file__).resolve().parent.parent.parent / "data" / "brp"`
- **Impact:** BRP logs now write consistently regardless of which directory the broker is started from

### BRP Lock Bug
- **Issue:** `_append_jsonl()` created a new `threading.Lock()` on every call — the lock was never
  actually shared between threads, defeating its purpose
- **Fix:** Replaced with module-level `_jsonl_lock = threading.Lock()` shared across all calls

### Intent Ledger Path Resolution
- **Issue:** `LedgerConfig.path` defaulted to `"data/task_ledger.jsonl"` (relative)
- **Fix:** Changed to resolve relative to repo root via `os.path.join(_REPO_ROOT, "data", "task_ledger.jsonl")`

### Broker Inbox Base Dir
- **Issue:** `BrokerConfig.inbox_base_dir` defaulted to `"data/inboxes"` (relative)
- **Fix:** Changed to resolve relative to repo root

## Remaining Gaps / Deferred Items

1. **Additional geese:** Kloutbot, A2A safety layer, and Cowork bridge are not yet wired.
2. **Temporal correlation:** BRP observations correlate to events via `event_id` but no cross-event temporal analysis is implemented yet.
3. **Dashboard integration:** BRP metadata is available in structured responses but not yet surfaced in the dashboard UI.
4. **JSONL rotation:** No log rotation strategy for JSONL files.

## Next Steps

1. Wire Kloutbot agent to emit BRP observations for social/reputation actions
2. Add BRP metadata display to the dashboard
3. Implement JSONL log rotation
4. Add BRP metrics to broker statistics endpoint
