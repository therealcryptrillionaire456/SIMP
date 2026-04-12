# Kloutbot Compiler & Horizon Advice Integration Contract

## Overview

This document specifies the integration contract between Kloutbot's strategy generation, the QIntentCompiler, and TimesFM horizon advice system. It defines the data flows, schemas, and lifecycle for producing coherent long-horizon strategies.

## 1. Compiler Interface

### 1.1 Input Parameters

Kloutbot calls the QIntentCompiler with the following parameters:

```python
# Method signature from KloutbotAgent
async def handle_generate_strategy(self, params: Dict[str, Any]) -> Dict[str, Any]:
    # ...
    tree = await self.compiler.compile_intent(
        streams=streams,
        foresight=foresight,
        deltas=deltas,
        horizon_steps=horizon_steps,  # From TimesFM advice
        timestamp=timestamp
    )
```

#### `streams` Structure
```json
{
  "affinity": [0.7, 0.72, 0.75, 0.78, 0.8, 0.82, 0.85, 0.87, 0.9, 0.92, 0.95, 0.97, 1.0, 1.0, 1.0, 1.0],
  "momentum": [0.65, 0.68, 0.7, 0.72, 0.75, 0.77, 0.8, 0.82, 0.85, 0.87, 0.9, 0.92, 0.95, 0.97, 1.0, 1.0],
  "volume": [0.6, 0.62, 0.65, 0.67, 0.7, 0.72, 0.75, 0.77, 0.8, 0.82, 0.85, 0.87, 0.9, 0.92, 0.95, 0.97],
  "sentiment": [0.55, 0.57, 0.6, 0.62, 0.65, 0.67, 0.7, 0.72, 0.75, 0.77, 0.8, 0.82, 0.85, 0.87, 0.9, 0.92]
}
```

#### `foresight` Structure
```json
{
  "affinity": 0.85,
  "drift_risk": 0.1
}
```

#### `deltas` Structure
```json
{
  "momentum": 0.8,
  "volume": 0.7,
  "sentiment": 0.65
}
```

#### `horizon_steps`
- Integer value from TimesFM horizon advice: 8, 16, or 32
- Determines how far into the future the compiler should optimize

### 1.2 Compiler Output

The QIntentCompiler returns a `DecisionTree` object which Kloutbot converts to a dictionary:

```python
# From KloutbotAgent.handle_generate_strategy
tree_dict = tree.to_dict()
action_params = self.compiler.get_action_params()
```

#### DecisionTree Structure
```json
{
  "tree": {
    "root": {
      "condition": "affinity > 0.8",
      "true_branch": {
        "action": "buy",
        "confidence": 0.85,
        "parameters": {
          "size": 0.3,
          "slippage_tolerance": 0.01
        }
      },
      "false_branch": {
        "action": "hold",
        "confidence": 0.6,
        "parameters": {}
      }
    },
    "metadata": {
      "generated_at": "2026-04-09T05:52:27.731075+00:00",
      "horizon_steps": 32,
      "optimization_iterations": 42
    }
  }
}
```

#### Action Parameters
```json
{
  "action": "buy",
  "confidence": 0.85,
  "size": 0.3,
  "slippage_tolerance": 0.01,
  "time_in_force": "GTC"
}
```

## 2. Horizon Advice System

### 2.1 TimesFM Integration

Kloutbot calls TimesFM service to get horizon advice before compiler invocation:

```python
# From KloutbotAgent._get_strategy_horizon_advice
resp = await svc.forecast(
    series_id=f"{self.agent_id}:affinity",
    history=self._affinity_buffer,
    forecast_horizon=32,
    context=ctx
)
```

### 2.2 Horizon Summary Schema

The `horizon_summary` field in strategy responses:

```json
{
  "horizon_summary": {
    "label": "long",
    "steps": 32,
    "applied": true,
    "rationale": "TimesFM affinity forecast: long horizon (32 steps). Affinity persists ~32 steps before dropping below 0.5 threshold.",
    "source": "timesfm"
  }
}
```

#### Field Definitions
- `label`: One of `"short"`, `"medium"`, `"long"`
- `steps`: Corresponding step count (8, 16, 32)
- `applied`: Boolean indicating if TimesFM advice was used (vs fallback)
- `rationale`: Human-readable explanation of horizon determination
- `source`: Either `"timesfm"` or `"fallback"`

### 2.3 Fallback Behavior

When TimesFM is unavailable or returns errors:

```json
{
  "horizon_summary": {
    "label": "medium",
    "steps": 16,
    "applied": false,
    "rationale": "TimesFM unavailable: using default medium horizon (16 steps)",
    "source": "fallback"
  }
}
```

## 3. A2A Mapping

### 3.1 AgentDecisionSummary Format

Kloutbot's strategy output maps to A2A AgentDecisionSummary:

```json
{
  "agent_id": "kloutbot",
  "decision_id": "strat_2026-04-09T05:52:27.731075",
  "timestamp": "2026-04-09T05:52:27.731075+00:00",
  "decision_type": "strategy_generation",
  "confidence": 0.85,
  "action": "buy",
  "parameters": {
    "size": 0.3,
    "slippage_tolerance": 0.01,
    "time_in_force": "GTC"
  },
  "horizon": {
    "label": "long",
    "steps": 32,
    "source": "timesfm",
    "rationale": "TimesFM affinity forecast: long horizon (32 steps)..."
  },
  "supporting_data": {
    "tree": { ... },
    "streams_snapshot": { ... },
    "mutation_telemetry": { ... }
  }
}
```

### 3.2 Horizon-Based Routing

Different horizons trigger different A2A handling:

| Horizon | Typical Use Case | A2A Routing |
|---------|------------------|-------------|
| Short (8) | Immediate execution | Direct to execution agents |
| Medium (16) | Near-term planning | Planning + approval pipeline |
| Long (32) | Strategic positioning | Strategic review + capital allocation |

## 4. Lifecycle

### 4.1 Strategy Generation Flow

```
1. Receive strategy request with foresight/deltas
2. Record current affinity in buffer
3. Call TimesFM for horizon advice
   - Success: Use TimesFM recommendation
   - Failure: Fallback to medium horizon
4. Call QIntentCompiler with horizon_steps
5. Package results with horizon_summary
6. Return complete strategy response
```

### 4.2 Data Dependencies

```
Kloutbot Agent
    │
    ├── TimesFM Service (horizon advice)
    │       └── affinity_buffer (16+ observations)
    │
    ├── QIntentCompiler (strategy generation)
    │       ├── streams (16 observations each)
    │       ├── foresight (current state)
    │       ├── deltas (recent changes)
    │       └── horizon_steps (from TimesFM)
    │
    └── PolicyEngine (safety check)
```

## 5. Error Handling

### 5.1 Compiler Failures

If compiler fails, strategy generation returns error:

```json
{
  "status": "error",
  "error_code": "compiler_failure",
  "error_message": "QIntentCompiler failed to generate strategy: ...",
  "timestamp": "..."
}
```

### 5.2 TimesFM Failures

TimesFM failures don't break strategy generation:

```json
{
  "status": "success",
  "strategy": { ... },
  "horizon_summary": {
    "label": "medium",
    "steps": 16,
    "applied": false,
    "rationale": "TimesFM unavailable: using default medium horizon (16 steps)",
    "source": "fallback"
  }
}
```

## 6. Testing Contract

### 6.1 Required Test Coverage

1. **Compiler Integration Tests**
   - Verify correct parameter passing to QIntentCompiler
   - Test DecisionTree conversion to dictionary
   - Verify action parameters extraction

2. **Horizon Advice Tests**
   - Test all three horizon buckets (short/medium/long)
   - Test TimesFM success and failure scenarios
   - Verify fallback behavior

3. **A2A Compatibility Tests**
   - Verify output matches AgentDecisionSummary schema
   - Test horizon-based routing logic
   - Verify telemetry includes all required fields

### 6.2 Mock Patterns

```python
# Mock compiler
mock_compiler = Mock()
mock_tree = Mock()
mock_tree.to_dict.return_value = {"tree": "test"}
mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
mock_compiler.get_action_params = Mock(return_value={"action": "test"})
mock_compiler.iteration_count = 0
mock_compiler.improvement_history = []

# Mock TimesFM
mock_service = AsyncMock()
mock_response = Mock()
mock_response.available = True
mock_response.point_forecast = [0.8] * 32
mock_service.forecast.return_value = mock_response
```

## 7. Performance Characteristics

### 7.1 Latency Expectations

| Component | Typical Latency | Timeout |
|-----------|----------------|---------|
| TimesFM Forecast | 50-200ms | 500ms |
| QIntentCompiler | 100-500ms | 1000ms |
| Policy Engine | 10-50ms | 100ms |
| Total Strategy Generation | 200-800ms | 2000ms |

### 7.2 Memory Usage

- Affinity buffer: 16 floats = ~128 bytes
- Streams history: 4 streams × 16 observations × 8 bytes = ~512 bytes
- DecisionTree: Variable, typically 1-10KB
- Total per strategy: < 20KB

### 7.3 Throughput

- Maximum sustainable: ~5 strategies/second
- Recommended: 1-2 strategies/second for stable operation
- Burst capacity: 10 strategies/second for < 30 seconds

## 8. Example Flows

### 8.1 Short Horizon Example (Immediate Execution)

```json
{
  "request": {
    "foresight": {"affinity": 0.95, "drift_risk": 0.05},
    "deltas": {"momentum": 0.9, "volume": 0.85, "sentiment": 0.8}
  },
  "response": {
    "status": "success",
    "strategy": {
      "tree": { ... },
      "action": "buy",
      "confidence": 0.92
    },
    "horizon_summary": {
      "label": "short",
      "steps": 8,
      "applied": true,
      "rationale": "TimesFM affinity forecast: short horizon (8 steps). Affinity drops below threshold after 8 steps.",
      "source": "timesfm"
    },
    "mutation_telemetry": {
      "total_strategies_generated": 42,
      "recent_strategies_count": 10,
      "compiler_iterations": 156
    }
  }
}
```

### 8.2 Long Horizon Example (Strategic Positioning)

```json
{
  "request": {
    "foresight": {"affinity": 0.88, "drift_risk": 0.12},
    "deltas": {"momentum": 0.82, "volume": 0.78, "sentiment": 0.75}
  },
  "response": {
    "status": "success",
    "strategy": {
      "tree": { ... },
      "action": "scale_in",
      "confidence": 0.78,
      "parameters": {
        "size": 0.15,
        "duration": "1h",
        "slippage_tolerance": 0.005
      }
    },
    "horizon_summary": {
      "label": "long",
      "steps": 32,
      "applied": true,
      "rationale": "TimesFM affinity forecast: long horizon (32 steps). Strong affinity persistence detected.",
      "source": "timesfm"
    }
  }
}
```

## 9. Error Handling Details

### 9.1 Error Codes

| Error Code | Description | Recovery Action |
|------------|-------------|-----------------|
| `timesfm_unavailable` | TimesFM service unavailable | Use fallback horizon (medium/16) |
| `timesfm_forecast_failed` | TimesFM forecast failed | Use fallback horizon (medium/16) |
| `policy_denied` | Policy engine rejected request | Return error, no strategy generated |
| `compiler_failure` | QIntentCompiler failed | Return error, strategy generation aborted |
| `insufficient_history` | <16 affinity observations | Use fallback horizon (medium/16) |
| `invalid_parameters` | Invalid request parameters | Return error with validation details |

### 9.2 Recovery Procedures

1. **TimesFM Failures**: Automatic fallback to medium horizon (16 steps)
2. **Compiler Failures**: No fallback - return error to caller
3. **Policy Denials**: No fallback - return error to caller
4. **Parameter Errors**: Return validation error with details

## 10. Versioning and Compatibility

### 10.1 Schema Versions

- Current: v1.0
- Backward compatible changes: Adding optional fields
- Breaking changes: Removing required fields, changing field types

### 10.2 Compatibility Matrix

| Kloutbot Version | TimesFM API | QIntentCompiler | A2A Schema |
|------------------|-------------|-----------------|------------|
| 1.0+ | v1.0+ | v1.0+ | v0.7.0+ |
| 0.9.x | v0.9.x | v0.9.x | v0.6.x |

### 10.3 Migration Notes

- Horizon summary field added in v1.0 (previously separate fields)
- Mutation telemetry added in v1.0
- All v0.9.x clients compatible with v1.0 (new fields optional)

## 11. Lifecycle Diagrams

### 11.1 Complete Strategy Generation Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Request       │    │   TimesFM       │    │   QIntent       │
│   Received      │───▶│   Horizon       │───▶│   Compiler      │
│                 │    │   Advice        │    │   Execution     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Record        │    │   Policy        │    │   Package       │
│   Affinity      │    │   Engine        │    │   Results       │
│   in Buffer     │    │   Check         │    │   with Summary  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 11.2 Error Recovery Flow

```
┌─────────────────┐
│   TimesFM       │
│   Call Fails    │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   Use Fallback  │
│   Horizon       │
│   (Medium/16)   │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   Continue      │
│   Strategy      │
│   Generation    │
└─────────────────┘
```

---

*Document Version: 1.1*  
*Last Updated: 2026-04-09*  
*Maintainer: Kloutbot Development Team*