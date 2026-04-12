# A2A Core Schema Mapping Guide

## Overview
This document maps the A2A (Agent-to-Agent) Core Schema requirements to the current SIMP implementation. It identifies gaps and provides a roadmap for achieving full A2A compatibility.

## Current State Analysis

### ✅ Implemented Components

#### 1. **A2A Schema (`simp/financial/a2a_schema.py`)**
- **AgentDecisionSummary**: Standardized agent output format
- **PortfolioPosture**: Aggregate risk and exposure analysis  
- **A2APlan**: Single funnel execution plan
- **Enums**: Side, RiskPosture, ExecutionMode
- **Validation**: Pure, side-effect-free validation functions
- **Serialization**: to_dict()/from_dict() methods

#### 2. **A2A Aggregator (`simp/financial/a2a_aggregator.py`)**
- **build_a2a_plan()**: Main aggregation function
- **Safety checks**: Agent consensus, exposure concentration, confidence thresholds
- **Risk classification**: Conservative/Neutral/Aggressive posture
- **Execution permission**: Safety-by-default logic
- **Utility functions**: Exposure calculation, grouping, filtering

#### 3. **A2A Documentation**
- **ADRs**: Architecture Decision Records (001-003)
- **Consumer Mapping Guide**: Agent integration guidelines
- **Risk Taxonomy**: Safety and risk classification
- **Scenario Catalog**: Use cases and examples
- **Simulation Runbook**: Testing procedures

#### 4. **Agent Integration**
- **QuantumArb**: Produces decision summaries with A2A fields
- **KashClaw**: Has A2A hooks for trade summarization
- **Tests**: Comprehensive test coverage for A2A integration

### ❌ Missing Components (Gaps)

#### 1. **A2A Compatibility Layer (`simp/compat/`)**
- **Agent Cards**: GET /.well-known/agent-card.json
- **Task Translation**: POST /a2a/tasks
- **Event Streaming**: GET /a2a/events, GET /a2a/events/stream
- **Security Endpoints**: GET /a2a/security
- **Version Management**: _SIMP_VERSION constant

#### 2. **HTTP Server Integration**
- Routes for A2A endpoints not implemented in http_server.py
- No agent card serving mechanism
- No task translation endpoint

#### 3. **Event System**
- No Server-Sent Events (SSE) implementation
- No event buffer or stream management
- No subscription mechanism for agents

#### 4. **Agent Registry Integration**
- No automatic agent card generation
- No capability mapping to A2A skills
- No lifecycle state mapping

## A2A Core Schema Requirements vs Current Implementation

### Requirement 1: Agent Cards
| Requirement | Status | Implementation Needed |
|-------------|--------|----------------------|
| GET /.well-known/agent-card.json | ❌ Missing | Create `agent_card.py` with AgentCardGenerator |
| Standard fields: id, name, version, capabilities | ❌ Missing | Map SIMP agent metadata to A2A format |
| Capability mapping to A2A skills | ❌ Missing | Create `capability_map.py` |
| Authentication schemes | ❌ Missing | Create `auth_map.py` |
| Health endpoint | ❌ Missing | Integrate with existing health checks |

### Requirement 2: Task Translation
| Requirement | Status | Implementation Needed |
|-------------|--------|----------------------|
| POST /a2a/tasks | ❌ Missing | Create `task_map.py` with translation logic |
| SIMP intent → A2A task conversion | ❌ Missing | Map intent types to A2A task types |
| A2A task → SIMP intent conversion | ❌ Missing | Reverse mapping for responses |
| Error handling for unsupported tasks | ❌ Missing | Graceful degradation with errors |

### Requirement 3: Event Streaming
| Requirement | Status | Implementation Needed |
|-------------|--------|----------------------|
| GET /a2a/events | ❌ Missing | Create `event_stream.py` with EventStreamBuffer |
| GET /a2a/events/stream (SSE) | ❌ Missing | Implement Server-Sent Events |
| Event types: task, heartbeat, error | ❌ Missing | Define A2A event schema |
| Subscription management | ❌ Missing | Track connected clients |

### Requirement 4: Security & Authentication
| Requirement | Status | Implementation Needed |
|-------------|--------|----------------------|
| GET /a2a/security | ❌ Missing | Create `a2a_security.py` |
| Multiple auth schemes: api_key, oauth2, mtls | ❌ Missing | Map to SIMP's auth system |
| Security policy per agent | ❌ Missing | Create `policy_map.py` |

### Requirement 5: FinancialOps Integration
| Requirement | Status | Implementation Needed |
|-------------|--------|----------------------|
| FinancialOps agent card | ❌ Missing | Create `financial_ops.py` |
| Payment connector integration | ⚠️ Partial | Exists but needs A2A wrapping |
| Approval queue A2A interface | ❌ Missing | Add A2A endpoints to approval queue |
| Budget monitor A2A interface | ❌ Missing | Add A2A endpoints to budget monitor |

### Requirement 6: ProjectX Integration
| Requirement | Status | Implementation Needed |
|-------------|--------|----------------------|
| ProjectX agent card | ❌ Missing | Create `projectx_card.py` |
| Health diagnostics A2A format | ❌ Missing | Create `projectx_diagnostics.py` |
| Native agent capabilities | ⚠️ Partial | Map existing capabilities to A2A |

## Mapping Strategy

### Phase 1: Foundation (Immediate)
1. Create `simp/compat/` directory structure
2. Implement `agent_card.py` with version v0.7.0
3. Implement basic capability mapping
4. Add A2A routes to http_server.py

### Phase 2: Core Functionality (Short-term)
1. Implement task translation layer
2. Implement event streaming with SSE
3. Add security endpoints
4. Integrate with existing agent registry

### Phase 3: FinancialOps Integration (Medium-term)
1. Wrap FinancialOps components with A2A interfaces
2. Implement approval queue A2A endpoints
3. Add budget monitor A2A endpoints
4. Create FinancialOps agent card

### Phase 4: Advanced Features (Long-term)
1. Implement capability negotiation
2. Add agent discovery mechanism
3. Implement protocol version negotiation
4. Add advanced event filtering

## Technical Implementation Details

### Directory Structure
```
simp/compat/
├── __init__.py              # Module exports
├── agent_card.py            # AgentCardGenerator, _SIMP_VERSION
├── auth_map.py              # Auth scheme mapping
├── capability_map.py        # Capability → A2A skill mapping
├── capability_schema.py     # StructuredCapability, normalise_capabilities
├── discovery_cache.py       # CardCache, CompatError, validate_agent_card
├── event_stream.py          # A2A events, EventStreamBuffer, SSE
├── lifecycle_map.py         # SIMP↔A2A state mapping
├── task_map.py              # A2A task translation
├── policy_map.py            # Per-agent safety policies
├── projectx_card.py         # ProjectX A2A card
├── projectx_diagnostics.py  # Health diagnostics
├── a2a_security.py          # Security schemes block
├── financial_ops.py         # FinancialOps card + validate + execute
├── ops_policy.py            # OpsPolicy, SimulatedSpendLedger
├── payment_connector.py     # PaymentConnector ABC, StubConnector, HealthTracker
├── stripe_connector.py      # StripeTestConnector (stdlib urllib only)
├── approval_queue.py        # ApprovalQueue, PolicyChangeQueue
├── live_ledger.py           # LiveSpendLedger
├── reconciliation.py        # ReconciliationResult, run_reconciliation
├── rollback.py              # RollbackManager, LedgerFrozenError
├── gate_manager.py          # GateManager, Gate 1/2 conditions
└── budget_monitor.py        # BudgetMonitor, AlertSeverity
```

### Agent Card Schema
```json
{
  "id": "simp:agent:quantumarb",
  "name": "QuantumArb",
  "version": "0.7.0",
  "capabilities": [
    {
      "type": "skill",
      "name": "arbitrage_detection",
      "description": "Detects cross-exchange arbitrage opportunities"
    }
  ],
  "auth_schemes": ["api_key"],
  "endpoints": {
    "tasks": "/a2a/tasks",
    "events": "/a2a/events",
    "health": "/health"
  },
  "metadata": {
    "x-simp-version": "0.7.0",
    "x-simp-agent-id": "quantumarb"
  }
}
```

### Task Translation Example
```python
# SIMP intent → A2A task
simp_intent = {
    "intent_type": "trade_execution",
    "source_agent": "quantumarb",
    "payload": {
        "instrument": "BTC-USD",
        "side": "buy",
        "quantity": 1000,
        "units": "USD"
    }
}

# Translated to A2A task
a2a_task = {
    "task_id": "task_123",
    "type": "execute_trade",
    "parameters": {
        "asset": "BTC-USD",
        "action": "buy",
        "amount": 1000,
        "currency": "USD"
    },
    "metadata": {
        "x-simp-intent-id": "intent_456",
        "x-simp-source": "quantumarb"
    }
}
```

## Testing Strategy

### Unit Tests
- Agent card generation and validation
- Task translation correctness
- Event streaming functionality
- Security endpoint responses

### Integration Tests
- End-to-end A2A task flow
- Agent card discovery
- Event subscription and delivery
- FinancialOps A2A integration

### Protocol Conformance Tests
- Verify against A2A Core Schema spec
- Test backward compatibility
- Validate error handling
- Test version negotiation

## Migration Plan

### Step 1: Non-breaking Changes
1. Add compat layer alongside existing code
2. Keep existing SIMP APIs unchanged
3. Add feature flags for A2A functionality
4. Test in parallel with existing system

### Step 2: Gradual Adoption
1. Enable A2A for one pilot agent (quantumarb)
2. Monitor performance and stability
3. Fix issues based on real usage
4. Gradually enable for other agents

### Step 3: Full Integration
1. Make A2A the default for new agents
2. Deprecate old SIMP-only APIs (with long sunset period)
3. Update documentation and examples
4. Train operators on A2A interfaces

## Success Metrics

### Technical Metrics
- ✅ All A2A Core Schema endpoints implemented
- ✅ 100% test coverage for compat layer
- ✅ < 50ms latency for agent card requests
- ✅ < 100ms latency for task translation
- ✅ Zero data loss in event streaming

### Operational Metrics
- ✅ All registered agents have A2A cards
- ✅ 95%+ successful task translations
- ✅ < 1% error rate in event delivery
- ✅ All security endpoints functional

### Business Metrics
- ✅ Reduced integration time for new agents
- ✅ Increased interoperability with external systems
- ✅ Improved monitoring and observability
- ✅ Enhanced security audit capabilities

## Next Steps

### Immediate (Next 2 hours)
1. Create `simp/compat/` directory with initial files
2. Implement `agent_card.py` and `capability_map.py`
3. Add A2A routes to `http_server.py`
4. Write basic tests for agent card generation

### Short-term (Next day)
1. Implement task translation layer
2. Add event streaming with SSE
3. Create FinancialOps A2A integration
4. Test with quantumarb agent

### Medium-term (Next week)
1. Implement all missing compat modules
2. Add protocol conformance tests
3. Integrate with dashboard for monitoring
4. Document A2A API for external developers

## Conclusion

The SIMP system has a solid foundation for A2A compatibility with the existing financial A2A components. The main gap is the missing `simp/compat/` layer that provides the HTTP endpoints and protocol translation. By implementing this layer according to the A2A Core Schema, we can achieve full interoperability while maintaining backward compatibility with existing SIMP agents.

The implementation follows the principles established in the A2A ADRs: single funnel execution, safety by default, and backward-compatible schema evolution. This will position SIMP as a fully A2A-compatible agent platform ready for enterprise adoption and external integration.