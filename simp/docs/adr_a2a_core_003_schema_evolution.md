# ADR 003: Schema Evolution Without Breaking Consumers

## Status
Accepted

## Context
The A2A schema (`AgentDecisionSummary`, `PortfolioPosture`, `A2APlan`) is a critical integration point between:
1. **Producers**: Agents (QuantumArb, KashClaw, Kloutbot) that create decisions
2. **Consumers**: Aggregator, safety harness, simulator, and eventual executors

As the system evolves, we need to:
- Add new fields to capture more information
- Modify validation rules based on operational experience
- Deprecate fields that are no longer useful
- Change default values or behaviors

However, we cannot break existing integrations. Agents might be:
- Running in production with specific field expectations
- Developed by different teams with different release cycles
- Unable to immediately update to new schema versions

## Decision
**Backward-compatible schema evolution** using these techniques:

1. **Additive changes only**: New fields are optional with sensible defaults
2. **Never remove fields**: Deprecated fields remain but may be ignored
3. **Validation leniency**: New validation rules don't break existing valid data
4. **Version awareness**: Schemas can indicate compatibility ranges
5. **Default migration**: New code handles missing fields gracefully

### Implementation Patterns

#### Pattern 1: Optional Fields with Defaults
```python
@dataclass
class AgentDecisionSummary:
    # Required fields (cannot change)
    agent_name: str
    instrument: str
    side: Side
    quantity: float
    units: str
    
    # Optional fields with defaults (can add new ones)
    confidence: Optional[float] = None
    horizon_days: Optional[int] = None
    volatility_posture: Optional[str] = None
    timesfm_used: bool = False
    rationale: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # NEW FIELD EXAMPLE (added in v1.1)
    # source_data_hash: Optional[str] = None  # For audit trail
```

#### Pattern 2: Validation That Allows Old Data
```python
def _validate(self) -> None:
    """Validate with backward compatibility."""
    # Required field validation (strict)
    if not self.agent_name:
        raise ValueError("agent_name must be a non-empty string")
    
    # Optional field validation (lenient for missing)
    if self.confidence is not None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
    
    # NEW VALIDATION EXAMPLE (only if field present)
    # if self.source_data_hash is not None:
    #     if len(self.source_data_hash) != 64:
    #         raise ValueError("source_data_hash must be 64 characters")
```

#### Pattern 3: Default Values for Missing Data
```python
def calculate_metrics(self, decision: AgentDecisionSummary) -> Dict:
    """Calculate metrics, handling missing optional fields."""
    # Use default if confidence missing
    confidence = decision.confidence if decision.confidence is not None else 0.5
    
    # Handle missing horizon with sensible default
    horizon = decision.horizon_days if decision.horizon_days is not None else 7
    
    return {
        "weighted_confidence": confidence * (horizon / 30.0),
        # ... other metrics
    }
```

## Consequences

### Positive
- **Zero-downtime upgrades**: Can deploy new schema without breaking agents
- **Gradual adoption**: Agents can update at their own pace
- **Operational safety**: Old agents continue to work
- **Experimental features**: Can add fields for testing before requiring them
- **Audit trail**: Can see which agents are using which schema features

### Negative
- **Schema bloat**: Accumulation of deprecated fields over time
- **Complexity**: Need to handle multiple "versions" of data
- **Documentation burden**: Must document what's required vs optional
- **Testing matrix**: Need to test with and without optional fields

### Neutral
- **Migration strategy**: Need clear plan for when to require new fields
- **Monitoring**: Need to track adoption of new schema features
- **Cleanup**: Eventually need to remove truly obsolete fields

## Implementation Details

### Current Schema Version
The schema is implicitly at "v1.0" with these characteristics:
- **Required**: `agent_name`, `instrument`, `side`, `quantity`, `units`
- **Optional**: `confidence`, `horizon_days`, `volatility_posture`, `timesfm_used`, `rationale`, `timestamp`
- **Validation**: Basic type checking, range validation for optional fields when present

### Adding a New Field (Example: `source_data_hash`)
1. **Phase 1 (Optional)**: Add field with `None` default, update validation
2. **Phase 2 (Recommended)**: Update agents to populate field, monitor adoption
3. **Phase 3 (Required)**: After sufficient adoption, make field required

```python
# Phase 1: Optional addition
@dataclass
class AgentDecisionSummary:
    # ... existing fields ...
    source_data_hash: Optional[str] = None  # NEW
    
    def _validate(self):
        # ... existing validation ...
        if self.source_data_hash is not None:
            if len(self.source_data_hash) != 64:
                raise ValueError("source_data_hash must be 64 characters")
```

### Changing a Default Value
Example: Changing default `execution_mode` from `SIMULATED_ONLY` to `LIVE_CANDIDATE`:

1. **Phase 1**: Keep old default, add configuration option
2. **Phase 2**: Change default for new plans, old plans keep old behavior
3. **Phase 3**: Remove old default entirely

```python
# Phase 1: Configurable default
def build_a2a_plan(decisions, execution_mode_default=None):
    if execution_mode_default is None:
        execution_mode_default = ExecutionMode.SIMULATED_ONLY  # Old default
    
    # ... build plan with configurable default ...
```

### Deprecating a Field
Example: Deprecating `volatility_posture` in favor of more precise metrics:

1. **Phase 1**: Mark as deprecated in docs, log warnings when used
2. **Phase 2**: Ignore field in new code, keep for backward compatibility
3. **Phase 3**: Remove from schema (after all agents updated)

```python
# Phase 1: Deprecation warning
@dataclass
class AgentDecisionSummary:
    # ... other fields ...
    volatility_posture: Optional[str] = None  # DEPRECATED: Use risk_metrics instead
    
    def __post_init__(self):
        if self.volatility_posture is not None:
            warnings.warn(
                "volatility_posture is deprecated, use risk_metrics instead",
                DeprecationWarning
            )
        # ... rest of validation ...
```

## Examples

### Backward-Compatible Field Addition
**Before (v1.0)**:
```python
decision = AgentDecisionSummary(
    agent_name="quantumarb",
    instrument="BTC-USD",
    side=Side.BUY,
    quantity=1000.0,
    units="USD"
)
```

**After (v1.1 with new field)**:
```python
# Old agent still works (field is optional)
decision_v1_0 = AgentDecisionSummary(
    agent_name="quantumarb",
    instrument="BTC-USD", 
    side=Side.BUY,
    quantity=1000.0,
    units="USD"
)

# New agent can use new field
decision_v1_1 = AgentDecisionSummary(
    agent_name="quantumarb",
    instrument="BTC-USD",
    side=Side.BUY,
    quantity=1000.0,
    units="USD",
    source_data_hash="a1b2c3...",  # NEW FIELD
    risk_metrics={"var_95": 0.05}  # ANOTHER NEW FIELD
)
```

### Graceful Handling of Missing Data
```python
def process_decision(decision: AgentDecisionSummary):
    """Process decision, handling missing optional fields."""
    
    # Handle missing confidence
    confidence = decision.confidence or 0.5  # Default if None
    
    # Handle missing rationale
    rationale = decision.rationale or f"{decision.side.value} {decision.instrument}"
    
    # New field (may be missing in old data)
    if hasattr(decision, 'source_data_hash') and decision.source_data_hash:
        # Use new field if available
        audit_trail = decision.source_data_hash
    else:
        # Fallback for old data
        audit_trail = f"{decision.agent_name}:{decision.timestamp}"
    
    return ProcessedDecision(confidence, rationale, audit_trail)
```

## Migration Strategy

### Version 1.0 → 1.1 Migration Plan
1. **Week 1**: Deploy schema with new optional fields
2. **Week 2-4**: Update agents to use new fields (optional)
3. **Week 5-8**: Monitor adoption, fix any issues
4. **Week 9+**: Consider making fields required if critical

### Communication Plan
- **Schema changes**: Document in `a2a_consumer_mapping_guide.md`
- **Deprecations**: Use Python `DeprecationWarning` and log messages
- **Timeline**: Give 4-8 weeks notice for breaking changes
- **Fallback**: Always maintain working fallback for old agents

### Testing Strategy
- **Unit tests**: Test with and without optional fields
- **Integration tests**: Test old and new agents together
- **Backward compatibility**: Verify old test data still works
- **Forward compatibility**: Test new code with old data

## Related Decisions
- [ADR 001](./adr_a2a_core_001_single_funnel.md): A2APlan as single execution funnel
- [ADR 002](./adr_a2a_core_002_safety_by_default.md): Safety by default

## Notes
This approach follows Postel's Law: "Be conservative in what you send, be liberal in what you accept." The aggregator accepts a wide range of inputs (including missing optional fields) but produces strict, validated outputs.

The schema is designed to evolve like a public API:
1. **Major versions**: Breaking changes (rare, with long migration)
2. **Minor versions**: Additive changes (common, backward-compatible)
3. **Patch versions**: Bug fixes and validation improvements

This allows the A2A system to improve over time without requiring synchronized updates across all agents.