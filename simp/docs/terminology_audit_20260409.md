# Terminology Audit & Standardization
**Date:** 2026-04-09  
**Auditor:** Goose #8 (Docs Consolidator & ISO)  
**Scope:** SIMP system documentation and codebase

## Overview

This document identifies terminology inconsistencies across the SIMP system and provides recommendations for standardization. Consistent terminology is critical for integration clarity, developer experience, and system reliability.

## Audit Methodology

1. **Code Analysis:** Examined schema definitions in `simp/financial/a2a_schema.py`
2. **Documentation Review:** Scanned all markdown files in `simp/docs/`
3. **Field Name Consistency:** Checked for variations in field naming
4. **Component References:** Verified consistent naming across documentation

## Identified Inconsistencies

### 1. Field Naming Inconsistencies

| Inconsistent Terms | Location Found | Recommended Standard | Rationale |
|-------------------|----------------|----------------------|-----------|
| `posture` vs `risk_posture` | Code uses `RiskPosture` enum | `risk_posture` | Matches enum name, more descriptive |
| `quantity` vs `size` | Code uses `quantity` in schema | `quantity` | Matches `AgentDecisionSummary` field |
| `side` vs `direction` | Code uses `Side` enum | `side` | Matches enum name, standard trading term |
| `confidence` vs `certainty` | Code uses `confidence` | `confidence` | Used in `AgentDecisionSummary` schema |
| `horizon` vs `horizon_steps` | Documentation inconsistency | `horizon_steps` | More specific for numeric values |

**Code Evidence:**
- `Side` enum defined with BUY/SELL/HOLD values
- `RiskPosture` enum defined with CONSERVATIVE/NEUTRAL/AGGRESSIVE
- `AgentDecisionSummary` has `confidence: Optional[float]` field
- `quantity` field in trade instructions

### 2. Component Reference Inconsistencies

| Inconsistent Terms | Location Found | Recommended Standard | Rationale |
|-------------------|----------------|----------------------|-----------|
| "Kloutbot" vs "KloutBot" | Documentation mixed usage | **KloutBot** | CamelCase matches agent naming pattern |
| "QuantumArb" vs "Quantum Arb" | Documentation | **QuantumArb** | Single word, matches agent name |
| "A2A Safety" vs "A2A Safety Harness" | Documentation | **A2A Safety** | Simpler, matches module purpose |
| "TimesFM" vs "TimesFM Service" | Documentation | **TimesFM** | Context clarifies service nature |
| "Dashboard" vs "Operator Console" | Documentation | **Dashboard** | Clear, matches directory name |

**Documentation Evidence:**
- `a2a_consumer_mapping_guide.md` uses "Kloutbot" (lowercase b)
- `system_integration_status.md` uses "KloutBot" (camel case)
- Multiple documents use "Quantum Arb" with space

### 3. Workflow Terminology Inconsistencies

| Inconsistent Terms | Location Found | Recommended Standard | Rationale |
|-------------------|----------------|----------------------|-----------|
| "Safety Evaluation" vs "Risk Assessment" | A2A documentation | **Safety Evaluation** | Broader term, includes blocking logic |
| "Simulation" vs "Stub Execution" | A2A documentation | **Simulation** | General term, "stub" is implementation detail |
| "Plan" vs "Strategy" vs "Decision Tree" | KloutBot vs A2A | **A2APlan** (aggregated), **Decision Tree** (KloutBot) | Different abstraction levels |
| "Forecast" vs "Prediction" | TimesFM documentation | **Forecast** | TimesFM-specific terminology |
| "Agent Decision" vs "Agent Recommendation" | A2A schema | **Agent Decision** | Matches `AgentDecisionSummary` class |

### 4. State/Status Terminology

| Inconsistent Terms | Location Found | Recommended Standard | Rationale |
|-------------------|----------------|----------------------|-----------|
| "blocked" vs "rejected" | Safety evaluation | **blocked** | Active term, implies safety intervention |
| "approved" vs "passed" | Safety evaluation | **passed** | Neutral term, implies meeting criteria |
| "live" vs "production" | Execution mode | **live** | Matches `ExecutionMode.LIVE_CANDIDATE` |
| "dry-run" vs "simulated" | Execution mode | **simulated** | Matches `ExecutionMode.SIMULATED_ONLY` |

## Impact Analysis

### High Impact Issues (Requires Immediate Attention)
1. **Component name capitalization** - Affects documentation searchability and clarity
2. **Schema field name consistency** - Critical for integration and data validation
3. **KloutBot vs Kloutbot** - Inconsistent agent references across documentation

### Medium Impact Issues
1. **Workflow term confusion** - Could lead to misunderstanding of system behavior
2. **State terminology variations** - Could affect alert and logging clarity
3. **Synonyms in documentation** - Reduces readability and consistency

### Low Impact Issues
1. **Minor spelling variations** - Primarily documentation clarity issue
2. **Synonym usage** - Context usually clarifies meaning

## Recommended Standardization Actions

### Immediate Actions (This Shift)
1. **Update Documentation:** Standardize component references in all markdown files
   - Change "Kloutbot" → "KloutBot" (camel case)
   - Change "Quantum Arb" → "QuantumArb" (remove space)
   - Standardize "A2A Safety" (not "A2A Safety Harness")

2. **Create Terminology Glossary:** Add to `system_overview.md` or create `terminology_glossary.md`

3. **Update Field References:** Ensure documentation matches schema field names

### Short-term Actions (Next 2 Shifts)
1. **Update A2A Documentation:** Standardize workflow terminology
2. **Agent Development Guidelines:** Include terminology standards section
3. **Integration Contracts:** Enforce terminology consistency in new contracts

### Long-term Actions (This Sprint)
1. **Automated Checks:** Add terminology validation to CI/CD pipeline
2. **Style Guide:** Create comprehensive terminology style guide
3. **Regular Audits:** Schedule quarterly terminology reviews

## Proposed Terminology Standards

### Component Names (Capitalization)
- **A2A Core** - Core schemas and aggregation logic
- **A2A Safety** - Risk evaluation and blocking system
- **KloutBot** - Strategy generation agent (camel case)
- **TimesFM** - Forecasting service
- **QuantumArb** - Arbitrage detection agent (no space)
- **KashClaw** - Multi-venue execution agent
- **Dashboard** - Operator console
- **Broker** - Message routing system

### Field Names (Match A2A Schema)
- `risk_posture` - Risk classification (conservative/neutral/aggressive)
- `quantity` - Trade amount (not "size")
- `side` - Trading action (BUY/SELL/HOLD, not "direction")
- `confidence` - Agent certainty score (0.0-1.0)
- `horizon_steps` - Forecast steps ahead (8/16/32)

### Workflow Terms
- **Safety Evaluation** - Comprehensive risk assessment including blocking
- **Simulation** - Stub execution of trades (not "stub execution")
- **A2APlan** - Aggregated trading plan from multiple agents
- **Decision Tree** - KloutBot strategy output
- **Forecast** - TimesFM time-series prediction (not "prediction")

### Execution States
- **blocked** - Prevented by safety checks (not "rejected")
- **passed** - Approved by safety checks (not "approved")
- **live** - Ready for real execution (matches `ExecutionMode.LIVE_CANDIDATE`)
- **simulated** - Test execution only (matches `ExecutionMode.SIMULATED_ONLY`)

## Implementation Guidelines

### For Documentation Writers
1. Use standardized component names (see above)
2. Reference fields using A2A schema names exactly
3. Describe workflows using standardized terms
4. Include term definitions for ambiguous concepts
5. Run terminology check before committing documentation

### For Developers
1. Use A2A schema field names in agent outputs
2. Reference components using standardized names
3. Follow execution state terminology in logs
4. Document any deviations with rationale
5. Update terminology when schema changes

### For Integration Contracts
1. Define all terms used in the contract
2. Reference A2A schema for field definitions
3. Use standardized workflow descriptions
4. Include terminology mapping for legacy systems
5. Validate terminology consistency before approval

## Verification Checklist

### Documentation Review (Apply to all .md files)
- [ ] All component references use standardized names
- [ ] Field names match A2A schema exactly
- [ ] Workflow terms are consistent
- [ ] Execution states use standardized terms
- [ ] Glossary or definitions included for ambiguous terms

### Code Review (Apply to new code)
- [ ] Agent outputs use A2A schema field names
- [ ] Component imports use standardized module names
- [ ] Log messages use consistent terminology
- [ ] Error messages use clear, standardized terms
- [ ] Enum values match terminology standards

### Integration Testing
- [ ] Contracts reference standardized terminology
- [ ] Mapping logic handles any legacy terms
- [ ] Test descriptions use consistent terminology
- [ ] Documentation matches implementation

## Examples of Standardized Usage

### Before (Inconsistent)
"The Kloutbot agent generates a strategy with a 16-step horizon. The A2A Safety Harness evaluates the posture and may block execution if risks are too high. Quantum Arb sends buy recommendations with size and direction parameters."

### After (Standardized)
"The KloutBot agent generates a decision tree with 16 horizon_steps. The A2A Safety system evaluates the risk_posture and may block execution if risks exceed thresholds. QuantumArb emits AgentDecisionSummary objects with side and quantity fields."

### Before (Inconsistent)
"After safety approval, the plan moves to stub execution in dry-run mode before live deployment."

### After (Standardized)
"After passing safety evaluation, the A2APlan undergoes simulation in simulated mode before live candidate promotion."

## Specific Fixes Required

### Documentation Files to Update:
1. `a2a_consumer_mapping_guide.md` - Fix "Kloutbot" → "KloutBot"
2. All documentation - Fix "Quantum Arb" → "QuantumArb"
3. All documentation - Standardize "A2A Safety" (remove "Harness")
4. Review all field references for consistency with schema

### Code Consistency Checks:
1. Verify all enum usage matches terminology
2. Check log messages for consistent terminology
3. Ensure error messages use standardized terms
4. Validate agent output field names match schema

## Next Steps

1. **Review and Approve Standards** - Get consensus on proposed terminology
2. **Update Existing Documentation** - Apply standards to all markdown files
3. **Create Developer Guide** - Include terminology standards section
4. **Monitor New Contributions** - Ensure consistency in new code/docs
5. **Regular Audits** - Schedule quarterly terminology reviews

## Related Documents

- `system_overview.md` - System architecture (includes some terminology)
- `system_integration_status.md` - Integration status (uses standardized terms)
- `a2a_simulation_runbook.md` - Operational guidance (review for consistency)
- `kloutbot_compiler_and_horizon_contract.md` - Integration contract (review for consistency)

---
**Audit Date:** 2026-04-09  
**Next Audit:** 2026-07-09 (quarterly)  
**Status:** Initial audit complete, recommendations proposed  
**Files Examined:** All .md files in simp/docs/, key .py files in simp/financial/  
**Critical Issues Found:** 3 (component naming inconsistencies)  
**Recommended Immediate Actions:** Update documentation with standardized component names