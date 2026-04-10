# BRP Mother Goose Integration

## Architecture

The SIMP broker (`SimpBroker`) serves as the Mother Goose orchestration entrypoint. It coordinates agent communication, routes intents, and evaluates multi-step plans through the BRP supervisor layer.

## Integration Points

### 1. Broker Plan Evaluation

**File:** `simp/server/broker.py`
**Method:** `SimpBroker.evaluate_plan()`
**Line:** ~120

The broker exposes a `evaluate_plan()` method that constructs a `BRPPlan` and submits it to the BRP bridge for review. This is the primary Mother Goose integration point.

```python
broker = SimpBroker(brp_bridge=BRPBridge())
result = broker.evaluate_plan(
    steps=[{"action": "trade_buy"}, {"action": "trade_sell"}],
    source_agent="mother_goose",
)
# result contains: decision, threat_score, severity, threat_tags, summary
```

### 2. Automatic Plan Review on Route

**File:** `simp/server/broker.py`
**Method:** `SimpBroker.route_intent()`
**Line:** ~145

When `route_intent()` receives an intent whose `params` contain a `steps` list, it automatically triggers BRP plan evaluation and attaches the review to the routing response under `brp_plan_review`.

```python
result = await broker.route_intent({
    "source_agent": "mother_goose",
    "target_agent": "worker:001",
    "intent_type": "execute_plan",
    "params": {
        "steps": [
            {"action": "trade_buy", "quantity": 100},
            {"action": "trade_sell", "quantity": 100},
        ]
    }
})
# result["brp_plan_review"]["decision"] == "SHADOW_ALLOW"
```

### 3. KashClaw Trade Gate

**File:** `simp/integrations/kashclaw_shim.py`
**Method:** `KashClawSimpAgent.handle_trade()`

Before trade execution, emits a `BRPEvent` for evaluation. After execution, emits a `BRPObservation`. BRP metadata is attached to the trade response under `brp`.

### 4. QuantumArb Shadow Observer

**File:** `simp/agents/quantumarb_agent.py`
**Method:** `QuantumArbAgent.handle_detect_arb()`

Emits `BRPEvent` and `BRPObservation` in shadow mode for every arbitrage detection. Never alters arb decision outcomes.

## Runtime Behavior

| Mode | Behavior |
|------|----------|
| shadow (default) | All events/plans receive SHADOW_ALLOW. Full audit logging. |
| advisory | High-threat events get ELEVATE. Never blocks. |
| enforced | Restricted actions get DENY. High-threat actions get ELEVATE. |
| disabled | All events get LOG_ONLY. |

## Data Flow

```
Mother Goose (Broker)
  ├─ evaluate_plan(steps) ──> BRPBridge.evaluate_plan() ──> BRPResponse
  │                                                          └─> JSONL
  ├─ route_intent(with steps) ──> auto plan review ──> attached to response
  │
  ├─ KashClaw goose
  │   ├─ BRPEvent (pre-trade) ──> BRPBridge.evaluate_event()
  │   ├─ organ.execute()
  │   └─ BRPObservation (post-trade) ──> BRPBridge.ingest_observation()
  │
  └─ QuantumArb goose
      ├─ BRPEvent (pre-detect) ──> BRPBridge.evaluate_event()
      ├─ arb logic (unmodified)
      └─ BRPObservation ──> BRPBridge.ingest_observation()
```

## Configuration

The BRP bridge is injected via constructor:

```python
bridge = BRPBridge(data_dir="data/brp", default_mode="shadow")
broker = SimpBroker(brp_bridge=bridge)
kashclaw = KashClawSimpAgent(brp_bridge=bridge, brp_mode="shadow")
quantumarb = QuantumArbAgent(brp_bridge=bridge, brp_mode="shadow")
```

When `brp_bridge=None`, all agents operate without BRP (backward compatible).
