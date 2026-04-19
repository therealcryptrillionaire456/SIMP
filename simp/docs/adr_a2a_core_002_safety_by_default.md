# ADR 002: Safety by Default (Execution Allowed = False)

## Status
Accepted

## Context
In financial systems, especially those involving automated trading, the default behavior for execution decisions is critical. We must choose between:

1. **Optimistic default**: Execution allowed unless explicitly blocked
2. **Pessimistic default**: Execution blocked unless explicitly allowed

The SIMP system has multiple safety mechanisms:
- Concentration limits (single instrument ≤ 30%)
- Confidence thresholds (≥ 0.3 per decision)
- Agent consensus (no significant conflicting positions)
- Risk posture appropriateness (aggressive posture requires high confidence)

## Decision
**Safety by default**: All `A2APlan` objects default to `execution_allowed = False`.

The system must pass explicit safety checks to enable execution. A plan is only allowed to execute if:
1. All safety checks pass (`safety_checks_failed` is empty)
2. At least one safety check passes (`safety_checks_passed` is not empty)
3. The execution reason explains why execution is allowed

### Default Values in A2APlan:
```python
@dataclass
class A2APlan:
    execution_allowed: bool = False  # ← SAFETY BY DEFAULT
    execution_reason: str = "Default: execution disabled in this phase"
    execution_mode: ExecutionMode = ExecutionMode.SIMULATED_ONLY
    safety_checks_passed: List[str] = field(default_factory=list)
    safety_checks_failed: List[str] = field(default_factory=list)
```

## Consequences

### Positive
- **Fail-safe**: Bugs or missing safety checks don't lead to unintended execution
- **Explicit permission**: Clear audit trail of why execution was allowed
- **Defense in depth**: Multiple layers must be satisfied
- **Operator confidence**: System won't "go rogue" due to configuration errors
- **Gradual enablement**: Can selectively enable execution for specific scenarios

### Negative
- **False negatives**: Safe plans might be blocked if safety rules are too conservative
- **Configuration burden**: Must explicitly configure what's allowed
- **Initial friction**: More work to get first executions through

### Neutral  
- **Audit clarity**: Easy to query "what executed and why" vs "what didn't execute and why not"
- **Testing focus**: Tests must verify both allowed and blocked scenarios
- **Documentation importance**: Must document safety rules clearly

## Implementation Details

### Safety Check Hierarchy
The aggregator applies checks in this order:

1. **Agent Consensus**: Do agents agree on direction? (BUY/SELL conflict)
2. **Confidence Threshold**: All decisions ≥ 0.3 confidence?
3. **Exposure Concentration**: No instrument > 30% of total exposure?
4. **Risk Posture Appropriateness**: Does posture match confidence level?

### Execution Permission Logic
In `determine_execution_permission()`:
```python
def determine_execution_permission(
    safety_results: List[Tuple[bool, str]]
) -> Tuple[bool, str]:
    """Determine if execution should be allowed based on safety checks."""
    
    passed_checks = [msg for passed, msg in safety_results if passed]
    failed_checks = [msg for passed, msg in safety_results if not passed]
    
    if failed_checks:
        # ANY failed check blocks execution
        return False, f"Execution blocked: {len(failed_checks)} safety check(s) failed"
    
    if not passed_checks:
        # No checks passed (edge case)
        return False, "Execution blocked: no safety checks passed"
    
    # All checks passed
    return True, f"Execution allowed: {len(passed_checks)} safety check(s) passed"
```

### Transition to Live Execution
The path from `execution_allowed = False` to `True` has gates:

1. **Gate 0 (Always)**: Safety checks must pass
2. **Gate 1 (Simulation)**: `execution_mode = SIMULATED_ONLY`
3. **Gate 2 (Manual)**: Operator review and manual promotion
4. **Gate 3 (Automated)**: Track record-based auto-promotion

## Examples

### Blocked by Default (No Explicit Allowance)
```python
# Empty decisions list
plan = build_a2a_plan([])
# execution_allowed = False
# execution_reason = "Default: execution disabled in this phase"
```

### Blocked by Safety Check
```python
# Single instrument with 100% concentration
decision = AgentDecisionSummary(
    agent_name="quantumarb",
    instrument="BTC-USD",
    side=Side.BUY,
    quantity=10000.0,
    units="USD",
    confidence=0.9
)

plan = build_a2a_plan([decision])
# execution_allowed = False
# execution_reason = "Execution blocked: 1 safety check(s) failed"
# safety_checks_failed = ["High concentration: BTC-USD has 100.0% of total exposure"]
```

### Allowed After Passing Checks
```python
# Diversified portfolio, high confidence, agent consensus
decisions = [
    AgentDecisionSummary("quantumarb", "BTC-USD", Side.BUY, 3000.0, "USD", 0.85),
    AgentDecisionSummary("kashclaw", "ETH-USD", Side.BUY, 2000.0, "USD", 0.75),
    AgentDecisionSummary("kloutbot", "SOL-USD", Side.BUY, 1000.0, "USD", 0.65),
]

plan = build_a2a_plan(decisions)
# execution_allowed = True (if concentration ≤ 30% per instrument)
# execution_reason = "Execution allowed: 4 safety check(s) passed"
```

## Migration and Configuration

### Safety Threshold Configuration
Thresholds are configurable via `get_aggregator_config()`:
```python
def get_aggregator_config() -> Dict[str, Any]:
    return {
        "concentration_threshold": 0.3,      # 30% max per instrument
        "confidence_threshold": 0.3,         # 30% minimum confidence
        "high_confidence_threshold": 0.8,    # 80% for "high confidence"
        "aggressive_posture_threshold": 0.5, # 50% needed for aggressive
    }
```

### Adjusting for False Negatives
If safe plans are being blocked:
1. **Temporarily**: Use `SIMULATED_ONLY` mode to test
2. **Adjust thresholds**: Modify config (with operator approval)
3. **Add exceptions**: Special rules for specific instruments/agents
4. **Improve agent confidence**: Better calibration of confidence scores

### Monitoring Blocked Plans
Operators should monitor:
- Ratio of allowed vs blocked plans
- Most common failure reasons
- Patterns in false negatives
- Agent-specific failure rates

## Related Decisions
- [ADR 001](./adr_a2a_core_001_single_funnel.md): A2APlan as single execution funnel
- [ADR 003](./adr_a2a_core_003_schema_evolution.md): Schema evolution without breaking consumers

## Notes
This "safety by default" approach is common in aviation, medical devices, and nuclear systems - domains where unintended activation has serious consequences. In financial trading, unintended execution can lead to significant losses, making this conservative approach appropriate.

The default can be gradually relaxed as:
1. Safety rules are validated through simulation
2. Agents demonstrate consistent, reliable decision-making
3. Operators gain confidence in the system
4. Automated monitoring can catch and roll back errors