# BRP-SIMP Integration Points & Risk Assessment

## Integration Points Mapping

### 1. BRP Bridge → SIMP Audit Log
**File**: `simp/security/brp_bridge.py`
**Hook Points**:
1. `evaluate_event()` → `brp_threat_detected`
2. `evaluate_plan()` → `brp_plan_evaluated` 
3. `ingest_observation()` → `brp_observation_logged`

**Data Flow**:
```
BRPEvent/BRPPlan → BRPBridge.evaluate() → BRPResponse → AuditHookAdapter → SecurityAuditLog
```

### 2. Sigma Engine → SIMP Audit Log
**File**: `bill_russel_sigma_rules/sigma_engine.py`
**Hook Points**:
1. `detect()` → `sigma_rule_matched`
2. `process_log_file()` → `sigma_batch_processed`

**Data Flow**:
```
LogEvent → SigmaEngine.detect() → DetectionResult → AuditHookAdapter → SecurityAuditLog
```

### 3. Integration System → SIMP Audit Log
**File**: `simp/orchestration/brp_integration.py`
**Hook Points**:
1. `process_threat_pipeline()` → `threat_pipeline_completed`
2. `_determine_actions()` → `threat_response_determined`
3. `_send_to_simp_agent()` → `threat_alert_sent`

### 4. SIMP Broker → BRP Bridge
**File**: `simp/server/broker.py` (READ-ONLY - no modifications)
**Integration Points**:
1. Intent routing decisions can be sent to BRP for evaluation
2. Agent registration events can trigger BRP baseline analysis
3. API key usage patterns can be analyzed for anomalies

## Risk Assessment Matrix

### High Risk Areas
| Area | Risk Description | Mitigation |
|------|------------------|------------|
| **Performance Impact** | Audit hooks may slow down BRP evaluation | Async logging, batch processing, performance monitoring |
| **Circular Dependencies** | Audit system depending on BRP which depends on audit | Clear interface segregation, dependency injection |
| **Data Schema Evolution** | BRP/SIMP schemas may change independently | Versioned schemas, adapter pattern, migration scripts |

### Medium Risk Areas
| Area | Risk Description | Mitigation |
|------|------------------|------------|
| **Hook Injection Failures** | Hooks may fail silently or crash components | Graceful degradation, health checks, comprehensive logging |
| **Storage Bloat** | Enriched audit logs may grow rapidly | Log rotation, compression, archiving strategy |
| **Configuration Complexity** | Multiple configuration points may conflict | Centralized configuration, validation, documentation |

### Low Risk Areas
| Area | Risk Description | Mitigation |
|------|------------------|------------|
| **Backward Compatibility** | Existing BRP/SIMP functionality may break | Feature flags, optional integration, comprehensive testing |
| **Security Exposure** | Sensitive data may leak through audit logs | Automatic redaction, access controls, encryption |
| **Monitoring Overload** | Too many alerts from integrated system | Configurable thresholds, correlation, alert grouping |

## Rollback Strategy

### Level 1: Configuration Rollback (Immediate)
```bash
# Disable via environment variable
export BRP_AUDIT_ENABLED=false

# Or via configuration file
echo '{"enabled": false}' > config/brp_audit.json
```

### Level 2: Code Rollback (1-2 hours)
1. Revert to using original BRPBridge constructor
2. Remove audit hook imports
3. Restart affected services
4. Verify system functionality

### Level 3: Full System Rollback (4-8 hours)
1. Checkout known good git commit
2. Run full test suite
3. Restart all SIMP/BRP components
4. Validate system integrity

### Rollback Verification Checklist
- [ ] BRP threat detection still functions
- [ ] SIMP security audit log still operational
- [ ] No data corruption in audit logs
- [ ] System performance within baseline
- [ ] All existing tests pass
- [ ] Dashboard displays correctly

## Success Metrics

### Quantitative Metrics
1. **Coverage**: >90% of BRP events logged to SIMP audit
2. **Latency**: <100ms added per event evaluation
3. **Accuracy**: 100% correct severity mapping
4. **Reliability**: <0.1% hook failure rate
5. **Storage**: <10% increase in audit log size

### Qualitative Metrics
1. **Usability**: Security operators can easily query BRP threat data
2. **Actionability**: Threat intelligence leads to actionable insights
3. **Maintainability**: Code is well-documented and testable
4. **Observability**: System state is visible through monitoring
5. **Recoverability**: Rollback procedures are tested and documented

## Implementation Priority Order

### P1 (Critical Path)
1. BRP Audit Hook Adapter (`brp_audit_hooks.py`)
2. Configuration system (`brp_audit_config.py`)
3. Factory pattern for backward compatibility
4. Basic test suite

### P2 (Integration Core)
1. BRP Bridge hook integration
2. Sigma Engine hook integration
3. Integration system updates
4. Performance monitoring

### P3 (Enhancements)
1. Context enrichment
2. Correlation engine
3. Enhanced queries
4. Dashboard integration

### P4 (Optimizations)
1. Async logging
2. Batch processing
3. Storage optimization
4. Advanced monitoring

## Stop Conditions Checklist

**STOP IMMEDIATELY IF**:
- [ ] BRP core protocol modifications required
- [ ] SIMP security audit log core modifications required  
- [ ] Circular dependencies cannot be resolved
- [ ] Performance degradation >20% in critical paths
- [ ] Security vulnerabilities introduced
- [ ] Data corruption occurs
- [ ] Existing functionality breaks

**CONTINUE WITH CAUTION IF**:
- [ ] Minor performance impact (<10%) detected
- [ ] Configuration complexity increases
- [ ] Additional dependencies required
- [ ] Test coverage decreases temporarily

**PROCEED NORMALLY IF**:
- [ ] All tests pass
- [ ] Performance within acceptable bounds
- [ ] Security review passed
- [ ] Rollback procedures tested
- [ ] Documentation complete