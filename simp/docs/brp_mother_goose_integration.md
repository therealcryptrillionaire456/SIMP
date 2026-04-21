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

### 5. Kloutbot Strategy Generation

**File:** `simp/agents/kloutbot_agent.py`
**Method:** `KloutbotAgent.handle_generate_strategy()`
**Line:** ~240

Before strategy generation, emits a `BRPEvent` with `event_type="strategy_generation"` and market data context. After generation, emits a `BRPObservation` with outcome (success/error). BRP metadata is attached to the response under `brp`. Default mode: SHADOW.

### 6. Kloutbot Goal Decomposition

**File:** `simp/agents/kloutbot_agent.py`
**Method:** `KloutbotAgent.handle_submit_goal()`
**Line:** ~641

Before goal decomposition, calls `evaluate_plan()` with the goal subtasks as a `BRPPlan`. The plan response is stored in the goal state dict under `brp` and attached to the return value. Default mode: SHADOW.

### 7. CoWork Bridge Peer Intent Gate

**File:** `simp/agents/cowork_bridge.py`
**Method:** `CoWorkBridge._build_app()` → `receive()` endpoint
**Line:** ~447

After firewall and schema checks, before the intent is queued or handled synchronously, emits a `BRPEvent` with `event_type="peer_intent"`. In SHADOW mode, logs and continues. In ENFORCED mode, DENY returns HTTP 403. After processing, emits a `BRPObservation`. Default mode: SHADOW.

### 8. OrchestrationLoop Task Assignment

**File:** `simp/orchestration/orchestration_loop.py`
**Method:** `OrchestrationLoop.run_once()`
**Line:** ~190

Before `broker.route_intent()`, evaluates the task assignment as a `BRPEvent` with `event_type="task_assignment"`. If BRP returns DENY in enforced mode, the task is marked as blocked and skipped. In shadow/advisory mode, BRP metadata is attached to `intent_data` under `brp`. After routing, emits a `BRPObservation` with the delivery outcome. Default mode: SHADOW.

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
  ├─ QuantumArb goose
  │   ├─ BRPEvent (pre-detect) ──> BRPBridge.evaluate_event()
  │   ├─ arb logic (unmodified)
  │   └─ BRPObservation ──> BRPBridge.ingest_observation()
  │
  ├─ Kloutbot goose
  │   ├─ handle_generate_strategy:
  │   │   ├─ BRPEvent (strategy_generation) ──> BRPBridge.evaluate_event()
  │   │   ├─ strategy compilation (unmodified)
  │   │   └─ BRPObservation (success/error) ──> BRPBridge.ingest_observation()
  │   └─ handle_submit_goal:
  │       ├─ BRPPlan (goal_decomposition) ──> BRPBridge.evaluate_plan()
  │       └─ goal decomposition (unmodified)
  │
  ├─ CoWork Bridge
  │   ├─ receive() endpoint:
  │   │   ├─ firewall_check + schema_check
  │   │   ├─ BRPEvent (peer_intent) ──> BRPBridge.evaluate_event()
  │   │   ├─ [ENFORCED DENY → HTTP 403]
  │   │   ├─ intent processing (sync/queue)
  │   │   └─ BRPObservation ──> BRPBridge.ingest_observation()
  │
  └─ OrchestrationLoop
      ├─ run_once():
      │   ├─ BRPEvent (task_assignment) ──> BRPBridge.evaluate_event()
      │   ├─ [ENFORCED DENY → task marked blocked]
      │   ├─ broker.route_intent()
      │   └─ BRPObservation (delivery outcome) ──> BRPBridge.ingest_observation()
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
