# ADR 001: A2APlan as the Single Funnel for Execution

## Status
Accepted

## Context
The SIMP system has multiple agents (QuantumArb, KashClaw, Kloutbot) that can generate trading recommendations. Each agent has different:
- Analysis methods (arbitrage, technical analysis, sentiment analysis)
- Risk profiles
- Confidence calibration
- Position sizing logic

Without a unified execution funnel, we would face:
1. **Conflicting actions**: Agents recommending opposite trades on the same instrument
2. **Risk concentration**: Multiple agents piling into the same position
3. **Inconsistent execution**: Different agents using different execution logic
4. **Audit complexity**: No single source of truth for what was executed and why

## Decision
All agent decisions must flow through a single funnel: the `A2APlan` produced by `build_a2a_plan()` in the aggregator.

### Key Components:
1. **AgentDecisionSummary**: Standardized output from each agent
2. **A2AAggregator**: Combines decisions, computes exposures, applies safety checks
3. **A2APlan**: Single output containing execution decision and rationale
4. **Safety Harness**: Pure validation that can block unsafe plans
5. **Simulator**: Stub executor for testing without real execution

### Flow:
```
[Agent 1] → AgentDecisionSummary ↘
[Agent 2] → AgentDecisionSummary → build_a2a_plan() → A2APlan → Safety Check → Simulator/Executor
[Agent 3] → AgentDecisionSummary ↗
```

## Consequences

### Positive
- **Single source of truth**: One A2APlan represents the system's collective decision
- **Centralized safety**: All safety checks applied consistently
- **Conflict resolution**: Conflicting agent recommendations are detected and handled
- **Auditability**: Complete record of inputs, processing, and outputs
- **Testability**: Can test the entire pipeline with mock decisions

### Negative
- **Single point of failure**: If aggregator has bugs, all execution is affected
- **Latency**: Additional processing step between agents and execution
- **Complexity**: More moving parts than direct agent-to-executor connections

### Neutral
- **Agent independence**: Agents don't need to know about each other
- **Pluggable safety**: Safety rules can be updated without changing agents
- **Gradual rollout**: Can simulate before going live

## Implementation Details

### Why Not Multiple Execution Paths?
Alternative: Each agent could execute directly through its own connector.

Problems:
1. **No risk aggregation**: Can't see total exposure across all agents
2. **Race conditions**: Agents executing simultaneously on same instrument
3. **Inconsistent limits**: Different agents using different risk limits
4. **Audit nightmare**: No unified ledger of all system actions

### Why Not Queue-Based?
Alternative: Put all decisions in a queue and let an executor process them.

Problems:
1. **Missing context**: Executor sees individual decisions, not aggregated view
2. **Timing issues**: Decisions from different times mixed together
3. **No collective intelligence**: Can't apply rules like "if 2/3 agents agree"

### Current Implementation
The single funnel approach gives us:
- **Aggregate exposure calculation**: Net position per instrument
- **Risk posture classification**: Conservative/Neutral/Aggressive based on confidence and size
- **Safety checks**: Concentration limits, confidence thresholds, agent consensus
- **Execution decision**: Binary allow/block with clear reason

## Examples

### Successful Funnel Flow
```python
# Three agents recommend buying BTC
decisions = [
    quantumarb_decision,  # BUY BTC, confidence 0.85
    kashclaw_decision,    # BUY BTC, confidence 0.75  
    kloutbot_decision,    # BUY BTC, confidence 0.65
]

plan = build_a2a_plan(decisions)
# Result: execution_allowed = True (if concentration OK)
# Risk posture: AGGRESSIVE (high confidence consensus)
```

### Blocked Flow (Conflict)
```python
# Agents disagree on BTC
decisions = [
    quantumarb_decision,  # BUY BTC, confidence 0.85
    kashclaw_decision,    # SELL BTC, confidence 0.70
]

plan = build_a2a_plan(decisions)
# Result: execution_allowed = False
# Reason: "Execution blocked: conflicting agent directions"
```

## Migration Strategy

### Phase 1: Simulation Only
- All plans have `execution_mode = SIMULATED_ONLY`
- Agents can integrate without risk
- Safety rules can be tuned

### Phase 2: Manual Promotion
- Operator reviews simulated plans
- Manually promotes to `LIVE_CANDIDATE`
- Limited live execution with caps

### Phase 3: Automated Gates
- Automated gates based on track record
- Gradual increase in limits
- Full automated execution

## Related Decisions
- [ADR 002](./adr_a2a_core_002_safety_by_default.md): Safety by default (execution_allowed = False)
- [ADR 003](./adr_a2a_core_003_schema_evolution.md): Schema evolution without breaking consumers

## Notes
This decision aligns with the SIMP philosophy of "structured intent" - all intents flow through the broker, are typed, and can be routed, logged, and audited. The A2APlan is the financial-specific instantiation of this pattern.