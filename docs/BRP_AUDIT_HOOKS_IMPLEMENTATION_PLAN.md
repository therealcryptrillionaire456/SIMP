# BRP Integration with SIMP Security Audit - Implementation Plan

## Executive Summary

This document outlines a phased implementation plan for integrating Bill Russell Protocol (BRP) threat detection with the SIMP Security Audit Log system. The integration will create audit hooks that capture BRP threat assessments, decisions, and observations, enriching the SIMP security audit with actionable threat intelligence while maintaining system stability and providing clear rollback paths.

## 1. Current State Analysis

### 1.1 SIMP Security Audit System
- **File**: `simp/server/security_audit.py`
- **Class**: `SecurityAuditLog`
- **Current Capabilities**:
  - Logs events with: timestamp, event_type, severity, details
  - Thread-safe JSONL persistence to `data/security_audit.jsonl`
  - Redaction of sensitive data
  - Event retrieval with filtering
- **Current Event Types**: `agent_registered`, `intent_routed`, `api_key_used`
- **Limitations**: No threat intelligence integration, basic severity levels only

### 1.2 BRP Threat Detection System
- **Core Components**:
  - `sigma_engine.py`: Sigma rule-based threat detection
  - `brp_models.py`: Data models (BRPEvent, BRPPlan, BRPObservation, BRPResponse)
  - `brp_bridge.py`: Evaluation engine with threat scoring
  - `brp_integration.py`: Integration system with pipelines
- **Current Integration**: Standalone system with separate logging
- **Threat Assessment**: Scores 0.0-1.0 with severity mapping (low, medium, high, critical)

### 1.3 Integration Gap Analysis
| Aspect | SIMP Security Audit | BRP System | Integration Need |
|--------|-------------------|------------|------------------|
| **Data Format** | JSONL with fixed schema | BRP models (dataclasses) | Translation layer |
| **Event Types** | Basic system events | Threat detection events | Mapping BRP→SIMP events |
| **Severity** | Low/medium/high | 0.0-1.0 score + severity | Score conversion |
| **Persistence** | `security_audit.jsonl` | Separate JSONL files | Unified logging |
| **Access Pattern** | Broker/agent access | Direct component access | Hook injection points |

## 2. Integration Architecture

### 2.1 High-Level Design
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SIMP Broker   │    │   BRP Bridge    │    │  Sigma Engine   │
│   & Agents      │────│   (Evaluation)  │────│  (Detection)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│               BRP Audit Hook Adapter                        │
│  • Translates BRP events → SIMP audit format                │
│  • Maps threat scores → SIMP severity                       │
│  • Enriches with context                                    │
│  • Handles redaction                                        │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│               SIMP Security Audit Log                       │
│  • Unified threat intelligence                              │
│  • Enriched event context                                   │
│  • Correlation capabilities                                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Integration Points Mapping

#### 2.2.1 BRP Event → SIMP Audit Event Mapping
| BRP Event Type | SIMP Event Type | Severity Mapping | Context Enrichment |
|----------------|-----------------|------------------|-------------------|
| `BRPEvent` | `brp_threat_detected` | Score→Severity: 0.0-0.3=low, 0.3-0.6=medium, 0.6-0.8=high, 0.8-1.0=critical | Agent ID, intent type, action |
| `BRPPlan` | `brp_plan_evaluated` | Based on max threat in plan steps | Plan ID, step count, restricted actions |
| `BRPResponse` | `brp_decision_made` | Based on decision: ALLOW=low, SHADOW=medium, DENY=high | Decision, confidence, recommendations |
| `BRPObservation` | `brp_observation_logged` | Based on observation type | Observation type, outcome, correlation ID |

#### 2.2.2 Hook Injection Points
1. **BRP Bridge Evaluation Hook** (`brp_bridge.py`):
   - After `evaluate_event()` → log threat assessment
   - After `evaluate_plan()` → log plan evaluation
   - After `ingest_observation()` → log observation

2. **Sigma Engine Detection Hook** (`sigma_engine.py`):
   - After `detect()` → log detection results
   - After `process_log_file()` → batch logging

3. **Integration System Pipeline Hook** (`brp_integration.py`):
   - After `process_threat_pipeline()` → log pipeline results
   - After `_determine_actions()` → log action decisions

## 3. Implementation Plan (Phased Approach)

### Phase 1: Foundation & Adapter Creation (Week 1)
**Objective**: Create audit hook adapter without modifying core systems

#### 1.1 Create BRP Audit Hook Adapter
```python
# File: simp/security/brp_audit_hooks.py
class BRPAuditHookAdapter:
    """Adapter that translates BRP events to SIMP audit log format"""
    
    def __init__(self, audit_log: SecurityAuditLog):
        self.audit_log = audit_log
        self._event_mapping = self._build_event_mapping()
    
    def log_brp_event(self, brp_event: BRPEvent, threat_score: float, 
                      response: Optional[BRPResponse] = None):
        """Convert BRPEvent to SIMP audit log entry"""
        # Implementation...
    
    def log_brp_plan(self, brp_plan: BRPPlan, response: BRPResponse):
        """Convert BRPPlan evaluation to audit log"""
        # Implementation...
    
    def log_brp_observation(self, observation: BRPObservation):
        """Convert BRPObservation to audit log"""
        # Implementation...
```

#### 1.2 Create Configuration Module
```python
# File: simp/security/brp_audit_config.py
class BRPAuditConfig:
    """Configuration for BRP audit hooks"""
    
    ENABLED = True  # Feature flag
    LOG_THRESHOLD = 0.3  # Minimum threat score to log
    REDACT_SENSITIVE = True
    EVENT_TYPE_PREFIX = "brp_"
    
    # Severity mapping
    SEVERITY_MAPPING = {
        (0.0, 0.3): "low",
        (0.3, 0.6): "medium", 
        (0.6, 0.8): "high",
        (0.8, 1.0): "critical"
    }
```

#### 1.3 Create Integration Test Suite
```python
# File: tests/test_brp_audit_hooks.py
class TestBRPAuditHooks:
    """Test BRP audit hook integration"""
    
    def test_brp_event_to_audit_log(self):
        # Test event translation
        pass
    
    def test_severity_mapping(self):
        # Test threat score → severity mapping
        pass
    
    def test_redaction(self):
        # Test sensitive data redaction
        pass
```

### Phase 2: Hook Integration (Week 2)
**Objective**: Integrate hooks into existing BRP components without breaking changes

#### 2.1 Enhance BRP Bridge with Audit Hooks
```python
# File: simp/security/brp_bridge.py (additions)
class BRPBridge:
    def __init__(self, data_dir: Path, mode: str = "shadow", 
                 audit_hook: Optional[BRPAuditHookAdapter] = None):
        self.audit_hook = audit_hook
        # Existing initialization...
    
    def evaluate_event(self, event: BRPEvent) -> BRPResponse:
        response = self._evaluate_event_internal(event)
        
        # Audit hook integration
        if self.audit_hook and self.audit_hook.config.ENABLED:
            self.audit_hook.log_brp_event(event, response.threat_score, response)
        
        return response
```

#### 2.2 Create Factory/Initialization Helper
```python
# File: simp/security/brp_audit_factory.py
def create_brp_bridge_with_audit(data_dir: Path, mode: str = "shadow") -> BRPBridge:
    """Factory function to create BRP bridge with audit hooks"""
    audit_log = get_audit_log()  # Get singleton audit log
    audit_hook = BRPAuditHookAdapter(audit_log)
    
    bridge = BRPBridge(data_dir, mode, audit_hook)
    return bridge
```

#### 2.3 Update Existing Integration Points
- Update `brp_integration.py` to use audit-enabled bridge
- Update test files to use factory function
- Ensure backward compatibility (audit hooks optional)

### Phase 3: Enrichment & Correlation (Week 3)
**Objective**: Add context enrichment and correlation capabilities

#### 3.1 Context Enrichment
- Add agent context (ID, type, capabilities)
- Add intent context (type, parameters, source)
- Add temporal correlation (sequence of related events)
- Add system state context (broker status, active agents)

#### 3.2 Correlation Engine
```python
# File: simp/security/brp_correlation.py
class BRPCorrelationEngine:
    """Correlates related BRP events for threat intelligence"""
    
    def correlate_events(self, events: List[Dict]) -> List[CorrelationGroup]:
        # Group related events by agent, intent, timeframe
        pass
    
    def detect_patterns(self, correlated_events: List[CorrelationGroup]) -> List[ThreatPattern]:
        # Detect multi-event threat patterns
        pass
```

#### 3.3 Enhanced Audit Log Queries
- Add threat score filtering
- Add correlation ID queries
- Add pattern detection queries
- Add timeline visualization support

### Phase 4: Dashboard Integration & Monitoring (Week 4)
**Objective**: Integrate with SIMP dashboard and add monitoring

#### 4.1 Dashboard Panels
- BRP Threat Overview panel
- Real-time threat detection feed
- Threat score trends over time
- Correlation pattern visualization

#### 4.2 Alerting Integration
- Integrate with existing alert system
- Configurable alert thresholds
- Alert suppression rules
- Alert correlation

#### 4.3 Performance Monitoring
- Audit hook performance metrics
- Threat detection latency monitoring
- Storage usage monitoring
- Error rate tracking

## 4. Risk Assessment

### 4.1 Technical Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Performance Impact** | Medium | High | Async logging, batch processing, performance monitoring |
| **Data Loss** | Low | High | Atomic writes, write verification, backup strategy |
| **Schema Incompatibility** | Low | Medium | Versioned schemas, migration scripts, backward compatibility |
| **Hook Injection Failures** | Medium | Medium | Graceful degradation, fallback logging, health checks |
| **Circular Dependencies** | Low | High | Clear dependency graph, interface segregation, dependency injection |

### 4.2 Security Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Sensitive Data Exposure** | Medium | High | Automatic redaction, access controls, audit trail |
| **Log Injection Attacks** | Low | Medium | Input validation, output encoding, schema validation |
| **Denial of Service via Logging** | Low | Medium | Rate limiting, log rotation, storage quotas |
| **Privilege Escalation** | Low | High | Principle of least privilege, access auditing, regular reviews |

### 4.3 Operational Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Increased Storage Requirements** | High | Low | Log rotation, compression, archiving strategy |
| **Monitoring Overload** | Medium | Medium | Configurable alerting, severity filtering, correlation |
| **Maintenance Complexity** | Medium | Medium | Clear documentation, automated tests, monitoring |
| **Integration Breakage** | Low | High | Comprehensive test suite, feature flags, rollback plan |

## 5. Rollback Strategy

### 5.1 Rollback Triggers
1. **Performance Degradation**: >20% increase in request latency
2. **Data Corruption**: Audit log schema validation failures
3. **System Instability**: Hook injection causing crashes
4. **Security Issues**: Sensitive data exposure detected
5. **Integration Failures**: BRP components failing to initialize

### 5.2 Rollback Procedures

#### 5.2.1 Phase 1 Rollback (Adapter Issues)
```bash
# Disable BRP audit hooks via configuration
export BRP_AUDIT_ENABLED=false

# Restart affected components
python3.10 bin/start_server.py --no-brp-audit
```

#### 5.2.2 Phase 2 Rollback (Hook Integration Issues)
```bash
# Revert to factory without audit hooks
python3.10 -c "
from simp.security.brp_bridge import BRPBridge
bridge = BRPBridge(data_dir, mode)  # Original constructor
"

# Update integration points to use original bridge
```

#### 5.2.3 Phase 3/4 Rollback (Complex Issues)
```bash
# Full system rollback to pre-integration state
git checkout feat/public-readonly-dashboard  # Return to known good state
python3.10 -m pytest tests/ -v  # Verify system integrity
./bin/start_production.py  # Restart production system
```

### 5.3 Data Migration & Cleanup
1. **Audit Log Migration**: Convert enriched logs to basic format if needed
2. **Schema Rollback**: Versioned schema support for backward compatibility
3. **Data Retention**: Archive enriched logs before rollback for analysis
4. **Cleanup Scripts**: Remove temporary files, indexes, and caches

### 5.4 Verification Procedures
1. **Functional Verification**: All BRP threat detection functions work
2. **Performance Verification**: System performance within acceptable bounds
3. **Security Verification**: No sensitive data exposure, access controls intact
4. **Integration Verification**: All system components interoperate correctly

## 6. Success Metrics & Validation

### 6.1 Key Performance Indicators (KPIs)
| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| **Threat Detection Coverage** | >90% of BRP events logged | Audit log analysis |
| **Logging Latency** | <100ms per event | Performance monitoring |
| **Storage Efficiency** | <10% storage increase | Storage monitoring |
| **Query Performance** | <1s for common queries | Query benchmarking |
| **Error Rate** | <0.1% of events | Error logging analysis |

### 6.2 Validation Tests
1. **Unit Tests**: Adapter translation, severity mapping, redaction
2. **Integration Tests**: Hook injection, event flow, error handling
3. **Performance Tests**: Load testing, stress testing, endurance testing
4. **Security Tests**: Penetration testing, data leakage testing
5. **Regression Tests**: Ensure existing functionality unchanged

### 6.3 Acceptance Criteria
- [ ] All BRP threat events appear in SIMP security audit log
- [ ] Threat scores correctly mapped to SIMP severity levels
- [ ] Sensitive data properly redacted in audit logs
- [ ] No performance degradation >10% in critical paths
- [ ] All existing tests pass without modification
- [ ] Dashboard shows BRP threat information correctly
- [ ] Rollback procedures tested and documented

## 7. Implementation Timeline

### Week 1: Foundation
- Day 1-2: Create BRP audit hook adapter
- Day 3-4: Create configuration and factory modules
- Day 5: Write comprehensive test suite

### Week 2: Integration
- Day 1-2: Integrate hooks into BRP bridge
- Day 3-4: Update integration system
- Day 5: Test backward compatibility

### Week 3: Enrichment
- Day 1-2: Implement context enrichment
- Day 3-4: Build correlation engine
- Day 5: Enhance audit log queries

### Week 4: Dashboard & Monitoring
- Day 1-2: Create dashboard panels
- Day 3-4: Implement alerting integration
- Day 5: Performance monitoring and final validation

## 8. Dependencies & Prerequisites

### 8.1 System Dependencies
- Python 3.10+
- SIMP broker running on port 5555
- BRP components initialized and tested
- Security audit log system operational

### 8.2 Team Dependencies
- **Goose Agent**: Implementation of adapter and hooks
- **Codex Agent**: Dashboard integration
- **Perplexity Agent**: Architecture review and validation
- **Claude Code**: Complex integration tasks if needed

### 8.3 External Dependencies
- No external services required
- No additional libraries beyond existing SIMP stack
- No network dependencies beyond local broker

## 9. Appendix

### 9.1 Event Schema Mapping Details
```json
{
  "timestamp": "ISO8601",
  "event_type": "brp_threat_detected",
  "severity": "high",
  "details": {
    "brp_event_id": "uuid",
    "threat_score": 0.75,
    "brp_severity": "high",
    "decision": "SHADOW",
    "confidence": 0.85,
    "agent_id": "quantumarb",
    "intent_type": "trade_execution",
    "action": "withdraw_funds",
    "recommendations": ["review_manually"],
    "correlation_id": "corr_uuid",
    "redacted_fields": ["api_key", "private_key"]
  }
}
```

### 9.2 Configuration Examples
```yaml
# config/brp_audit.yaml
enabled: true
log_threshold: 0.3
redact_sensitive: true
event_type_prefix: "brp_"
severity_mapping:
  - range: [0.0, 0.3]
    severity: "low"
  - range: [0.3, 0.6]
    severity: "medium"
  - range: [0.6, 0.8]
    severity: "high"
  - range: [0.8, 1.0]
    severity: "critical"
```

### 9.3 Monitoring Dashboard Mockup
```
BRP Threat Intelligence Dashboard
=================================
[Real-time Threat Feed]
• 14:30:23 - quantumarb - trade_execution - HIGH (0.72) - SHADOW
• 14:30:15 - kashclaw - fund_transfer - MEDIUM (0.45) - ALLOW
• 14:29:58 - bullbear - data_access - LOW (0.25) - ALLOW

[Threat Score Trends]
▁▂▃▅▆▇█▇▆▅▃▂▁ (Last 24 hours)

[Top Threat Sources]
1. quantumarb (42%)
2. kashclaw (28%)
3. bullbear (15%)
4. others (15%)

[Correlation Patterns]
• Pattern A: Multiple high-value trades → 3 occurrences
• Pattern B: Rapid intent switching → 1 occurrence
```

## 10. Conclusion

This implementation plan provides a comprehensive, phased approach to integrating BRP threat detection with the SIMP security audit system. By following this plan, we can:

1. **Enhance Security Visibility**: Capture BRP threat intelligence in the central audit log
2. **Maintain System Stability**: Use feature flags and gradual rollout
3. **Ensure Rollback Capability**: Clear procedures for reverting changes
4. **Provide Actionable Intelligence**: Enriched context and correlation for threat analysis

The plan respects the stop conditions by working with existing BRP and SIMP interfaces without modifying core protocols. All integration points use adapter patterns and dependency injection to maintain separation of concerns and enable clean rollback if needed.

**Next Step**: Begin Phase 1 implementation with adapter creation and test suite development.