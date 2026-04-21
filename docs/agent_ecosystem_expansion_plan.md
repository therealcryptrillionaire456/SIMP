# SIMP Agent Ecosystem Expansion Plan

## Executive Summary

This document outlines a strategic plan for expanding the SIMP agent ecosystem, focusing on systematic integration of available agents including kashclaw_gemma (port 8780) and other key agents. The plan prioritizes safe, verifiable integration with clear value propositions and phased implementation.

## 1. Current Agent Landscape Analysis

### 1.1 Registered Agents (Documented)
From `.goosehints` and system investigation:

| Agent ID | Type | Port | Status | Description |
|----------|------|------|--------|-------------|
| kashclaw | Trading | N/A | Active | KashClaw trading agent |
| kashclaw_gemma | LLM Planner | 8780 | Available | Gemma4 local LLM planner |
| bullbear_predictor | Signal Generator | File-based | Available | BullBear signal generator |
| quantumarb | Arbitrage | N/A | Active | Arbitrage analysis agent |
| kloutbot | Orchestration | N/A | Active | Orchestration agent |
| claude_cowork | Code Bridge | 8767 | Available | Claude Code bridge |
| projectx_native | Maintenance | 8771 | Available | ProjectX maintenance kernel |
| perplexity_research | Research | N/A | Active | Perplexity research agent |
| gemma4_local | LLM Model | 8780 | Available | Gemma4 local model |
| financial_ops | Financial | Compat layer | Active | FinancialOps simulated agent |

### 1.2 System Architecture Gaps
1. **Routing Policy Mismatch**: Current routing policy uses generic names (grok:001, reasoning:001) not matching actual agent IDs
2. **Verification Gap**: No systematic process for verifying agent availability before registration
3. **Health Monitoring**: Limited standardized health check protocols
4. **Capability Mapping**: Incomplete mapping between agent capabilities and routing needs

## 2. Agent Discovery & Verification Process

### 2.1 Verification Protocol
```python
# Pseudo-code for agent verification
def verify_agent(agent_type, endpoint, expected_capabilities):
    """
    Verify agent is reachable and functional before registration
    """
    steps = [
        "1. Network reachability check (ping/port scan)",
        "2. HTTP endpoint validation (GET /health)",
        "3. Capability verification (POST /capabilities)",
        "4. Intent handling test (sample ping intent)",
        "5. Performance baseline (response time < 5s)"
    ]
```

### 2.2 Agent Categories & Verification Requirements

#### Category A: HTTP-based Agents (kashclaw_gemma, projectx_native, claude_cowork)
- **Verification**: HTTP health endpoint, capability endpoint
- **Registration**: Standard HTTP registration with heartbeat
- **Monitoring**: Continuous health checks, circuit breaker pattern

#### Category B: File-based Agents (bullbear_predictor)
- **Verification**: File existence, process validation, output format check
- **Registration**: File watcher registration, polling mechanism
- **Monitoring**: File modification timestamps, output freshness

#### Category C: Compat Layer Agents (financial_ops)
- **Verification**: Module import, function availability, policy validation
- **Registration**: In-process registration, no external endpoint
- **Monitoring**: Function call success rate, policy compliance

#### Category D: Active Agents (kashclaw, quantumarb, kloutbot, perplexity_research)
- **Verification**: Re-registration with validation, capability audit
- **Registration**: Enhanced registration with capability profiling
- **Monitoring**: Enhanced telemetry, performance metrics

## 3. Registration Strategy

### 3.1 Registration Templates

#### Template 1: HTTP Agent Registration
```json
{
  "agent_id": "kashclaw_gemma",
  "agent_type": "llm_planner",
  "endpoint": "http://localhost:8780",
  "capabilities": ["planning", "research", "summarization", "classification"],
  "health_endpoint": "/health",
  "capabilities_endpoint": "/capabilities",
  "heartbeat_interval": 30,
  "max_response_time": 10,
  "circuit_breaker_threshold": 3
}
```

#### Template 2: File-based Agent Registration
```json
{
  "agent_id": "bullbear_predictor",
  "agent_type": "signal_generator",
  "endpoint": "(file-based)",
  "capabilities": ["prediction_signal", "market_analysis"],
  "watch_path": "/path/to/output/files",
  "poll_interval": 60,
  "file_pattern": "signal_*.json",
  "max_age_seconds": 300
}
```

#### Template 3: Compat Layer Registration
```json
{
  "agent_id": "financial_ops",
  "agent_type": "financial_processor",
  "endpoint": "(compat-layer)",
  "capabilities": ["payment_processing", "budget_monitoring", "approval_workflow"],
  "module_path": "simp.compat.financial_ops",
  "policy_version": "v1.0",
  "simulation_mode": true
}
```

### 3.2 Registration Workflow
1. **Discovery Phase**: Scan for available agents using predefined locations
2. **Verification Phase**: Run category-specific verification tests
3. **Registration Phase**: Register with broker using appropriate template
4. **Testing Phase**: Send test intents to validate functionality
5. **Monitoring Phase**: Start continuous health monitoring

## 4. Integration Testing Approach

### 4.1 Test Pyramid for Agent Integration

#### Level 1: Unit Tests (Per Agent)
- Agent-specific functionality
- Capability validation
- Error handling

#### Level 2: Integration Tests (Agent + Broker)
- Registration/verification flow
- Intent routing
- Response handling

#### Level 3: System Tests (Multi-Agent)
- Workflow orchestration
- Capability chaining
- Failure recovery

#### Level 4: End-to-End Tests (Full Ecosystem)
- Real-world use cases
- Performance under load
- Long-running stability

### 4.2 Test Suite Structure
```
tests/agent_integration/
├── test_agent_verification.py      # Verification protocols
├── test_agent_registration.py      # Registration workflows
├── test_kashclaw_gemma_integration.py
├── test_projectx_integration.py
├── test_bullbear_integration.py
├── test_claude_cowork_integration.py
├── test_multi_agent_orchestration.py
└── fixtures/
    └── agent_fixtures.py           # Test fixtures
```

### 4.3 Key Test Scenarios
1. **Agent Discovery Test**: Verify agent detection in expected locations
2. **Health Check Test**: Validate health endpoint responses
3. **Capability Test**: Confirm advertised capabilities match actual functionality
4. **Intent Routing Test**: Ensure proper routing based on capabilities
5. **Failure Recovery Test**: Test circuit breaker and fallback mechanisms
6. **Performance Test**: Validate response time SLAs

## 5. Priority Ranking & Implementation Roadmap

### 5.1 Priority Matrix (Value vs Complexity)

| Agent | Business Value | Integration Complexity | Priority | Phase |
|-------|---------------|------------------------|----------|-------|
| **kashclaw_gemma** | High (LLM planning core) | Medium (HTTP agent) | P0 | Phase 1 |
| **projectx_native** | High (System maintenance) | Medium (HTTP agent) | P0 | Phase 1 |
| **bullbear_predictor** | High (Revenue signal) | High (File-based) | P1 | Phase 2 |
| **claude_cowork** | Medium (Code assistance) | Low (HTTP agent) | P2 | Phase 2 |
| **gemma4_local** | Medium (LLM fallback) | Low (Same as kashclaw_gemma) | P3 | Phase 3 |
| **Active agents (re-registration)** | High (System integrity) | Low (Validation only) | P0 | Phase 1 |

### 5.2 Implementation Roadmap

#### Phase 1: Foundation (Weeks 1-2)
**Objective**: Establish verification framework and integrate high-value HTTP agents

1. **Week 1**: 
   - Create agent verification framework
   - Implement HTTP agent verification protocol
   - Integrate kashclaw_gemma (port 8780)
   - Update routing policy with actual agent IDs

2. **Week 2**:
   - Integrate projectx_native (port 8771)
   - Re-register active agents with validation
   - Implement health monitoring dashboard
   - Create basic integration tests

#### Phase 2: Expansion (Weeks 3-4)
**Objective**: Integrate file-based and specialized agents

3. **Week 3**:
   - Implement file-based agent protocol
   - Integrate bullbear_predictor
   - Create file watcher service
   - Add signal processing pipeline

4. **Week 4**:
   - Integrate claude_cowork (port 8767)
   - Enhance capability mapping
   - Implement circuit breaker patterns
   - Add performance monitoring

#### Phase 3: Optimization (Weeks 5-6)
**Objective**: System optimization and completion

5. **Week 5**:
   - Register gemma4_local (alias for kashclaw_gemma)
   - Optimize routing algorithms
   - Implement load balancing
   - Add agent affinity rules

6. **Week 6**:
   - Comprehensive testing suite
   - Performance benchmarking
   - Documentation completion
   - Production readiness review

### 5.3 Success Metrics

#### Quantitative Metrics
- **Agent Uptime**: >99.5% for all registered agents
- **Response Time**: <5s for 95% of intents
- **Registration Success**: 100% verification before registration
- **Test Coverage**: >80% for integration tests

#### Qualitative Metrics
- **Operator Experience**: Single-pane visibility into all agents
- **Developer Experience**: Clear APIs for adding new agents
- **System Resilience**: Graceful degradation during agent failures
- **Documentation**: Complete setup and troubleshooting guides

## 6. Risk Mitigation & Stop Conditions

### 6.1 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Agent process crashes | Medium | High | Circuit breakers, automatic restart |
| Network connectivity issues | Low | High | Retry logic, fallback agents |
| Resource exhaustion | Low | Medium | Resource monitoring, throttling |
| Security vulnerabilities | Low | High | Input validation, rate limiting |
| Configuration errors | Medium | Medium | Validation scripts, dry-run mode |

### 6.2 Stop Conditions
**Immediate Stop Conditions**:
1. Attempting to start new agent processes without verification
2. Agent registration causing broker instability
3. Security vulnerability detected in agent integration
4. Resource usage exceeding safe thresholds

**Warning Conditions** (Require review before proceeding):
1. Agent verification failure rate > 10%
2. Health check failure rate > 20%
3. Response time degradation > 50%
4. Test coverage dropping below 70%

### 6.3 Rollback Plan
1. **Level 1**: Disable problematic agent only
2. **Level 2**: Rollback agent registration changes
3. **Level 3**: Restore previous routing policy
4. **Level 4**: Full system rollback to last stable state

## 7. Deliverables & Artifacts

### 7.1 Technical Deliverables
1. **Agent Verification Framework**: Reusable verification library
2. **Registration Service**: Enhanced agent registration with validation
3. **Health Monitoring Dashboard**: Real-time agent status visualization
4. **Integration Test Suite**: Comprehensive test coverage
5. **Documentation**: Setup guides, API references, troubleshooting

### 7.2 Documentation Deliverables
1. **Agent Integration Guide**: Step-by-step integration instructions
2. **Operator Manual**: Daily operations and monitoring
3. **Troubleshooting Guide**: Common issues and solutions
4. **API Reference**: Complete API documentation
5. **Architecture Diagrams**: System and data flow diagrams

## 8. Conclusion

This expansion plan provides a systematic approach to integrating available agents into the SIMP ecosystem, prioritizing safety, verification, and value delivery. By following this phased approach with clear verification protocols and stop conditions, we can build a robust, scalable agent ecosystem that supports the SIMP vision of becoming "The HTTP of Agentic AI."

The plan balances immediate value (integrating kashclaw_gemma and projectx_native) with long-term scalability, ensuring each integration contributes to system resilience and capability expansion while maintaining operational safety and system stability.