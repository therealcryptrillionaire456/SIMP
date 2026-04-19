# Sovereign Self Compiler v2 - Architecture

## Overview
A controlled recursive self-compilation system that enables the ecosystem to inspect, plan, generate, execute, verify, and stage its own improvements with safety guarantees.

## Core Philosophy
**Controlled Autonomy**: The system can prompt itself and execute results, but only inside a bounded, observable, and reversible pipeline.

## Architecture Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                    Operator Interface                        │
│  (CLI, Dashboard, Manual Approval Gates)                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Recursive Controller                      │
│  • Manages bounded recursion depth                          │
│  • Coordinates pipeline phases                              │
│  • Enforces safety policies                                 │
│  • Maintains session state                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
┌───▼──────┐         ┌─────▼──────┐         ┌─────▼──────┐
│Inventory │         │   Planner  │         │  Prompt    │
│ Scanner  │────────▶│            │────────▶│ Compiler   │
│          │         │            │         │            │
└──────────┘         └────────────┘         └────────────┘
                            │                       │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
┌───▼──────┐         ┌─────▼──────┐         ┌─────▼──────┐
│Executor  │         │ Evaluator  │         │ Promoter   │
│          │────────▶│            │────────▶│            │
│          │         │            │         │            │
└──────────┘         └────────────┘         └────────────┘
                            │                       │
                    ┌───────▼───────────────────────▼───────┐
                    │           Trace Logger                │
                    │  • Structured JSONL logging           │
                    │  • Correlation IDs                    │
                    │  • Learning signal generation         │
                    └───────────────────────────────────────┘
                            │                       │
                    ┌───────▼───────────────────────▼───────┐
                    │        External Integrations          │
                    │  • ProjectX (safety review)           │
                    │  • Mesh Bus (internal events)         │
                    │  • Agent Lightning (traces)           │
                    │  • Obsidian (documentation)           │
                    └───────────────────────────────────────┘
```

## Module Specifications

### 1. Inventory Scanner (`inventory.py`)
**Purpose**: Discovers and catalogs codebase components.

**Inputs**:
- Root directories to scan
- File pattern filters
- Exclusion patterns

**Outputs**:
- Structured inventory JSON
- Component classifications
- Dependency mappings

**Key Methods**:
- `scan_directory(root_path, max_depth=5)`
- `classify_component(file_path, content)`
- `generate_inventory_report()`

**Integration Points**:
- Reuses SIMP memory patterns
- Integrates with Obsidian documentation

### 2. Planner (`planner.py`)
**Purpose**: Creates next-step recursive plans based on goals and current state.

**Inputs**:
- Goal specification
- Current inventory snapshot
- Prior traces and outcomes
- Operator constraints

**Outputs**:
- Structured plan JSON
- Task decomposition
- Resource requirements
- Success criteria

**Key Methods**:
- `create_plan(goal, inventory, constraints)`
- `decompose_task(task)`
- `validate_plan(plan)`

**Safety Features**:
- Bounds recursion depth
- Validates against safety policies
- Requires explicit success criteria

### 3. Prompt Compiler (`prompt_compiler.py`)
**Purpose**: Compiles structured self-prompts from plans.

**Inputs**:
- Plan specification
- Current context
- Previous prompts and outcomes
- Style/tone preferences

**Outputs**:
- Structured prompt JSON
- Expected artifacts
- Evaluation requirements
- Execution mode

**Key Methods**:
- `compile_prompt(plan, context)`
- `validate_prompt(prompt)`
- `version_prompt(prompt)`

**Contracts**:
- Every prompt must declare expected outputs
- Every prompt must specify evaluation criteria
- Prompts are versioned and logged

### 4. Executor (`executor.py`)
**Purpose**: Safely executes generated tasks in staged environment.

**Inputs**:
- Prompt specification
- Execution mode (python, bash, etc.)
- Resource limits
- Timeout constraints

**Outputs**:
- Execution result JSON
- Stdout/stderr capture
- Generated artifacts
- Exit status and metrics

**Key Methods**:
- `execute_task(prompt, mode, limits)`
- `capture_outputs(process)`
- `stage_artifacts(results)`

**Safety Features**:
- All execution in staging directory
- Resource limits enforced
- Timeout protection
- Isolation where possible

### 5. Evaluator (`evaluator.py`)
**Purpose**: Scores and gates candidate outputs against criteria.

**Inputs**:
- Execution results
- Expected artifacts from prompt
- Evaluation criteria
- Baseline comparison (if exists)

**Outputs**:
- Evaluation score (0.0-1.0)
- Pass/fail status per criterion
- Detailed feedback
- Promotion recommendation

**Key Methods**:
- `evaluate_results(results, criteria)`
- `compare_to_baseline(new, old)`
- `check_policy_compliance(artifact)`

**Evaluation Gates**:
1. Schema validation
2. Syntax/parse validation
3. Unit/smoke tests
4. Integration fit check
5. Policy/safety check
6. Baseline comparison

### 6. Promoter (`promoter.py`)
**Purpose**: Handles staging vs promotion decisions.

**Inputs**:
- Evaluation results
- Artifact locations
- Target paths
- Promotion policies

**Outputs**:
- Promotion decision (PROMOTE/REJECT/REVISE/ESCALATE)
- Target paths (if promoted)
- Rollback plan
- Audit trail

**Key Methods**:
- `make_promotion_decision(evaluation)`
- `execute_promotion(artifact, target)`
- `create_rollback_plan()`

**Safety Features**:
- Sensitive paths require ProjectX review
- All promotions create backup
- Rollback plan always generated
- Audit trail immutable

### 7. Trace Logger (`trace_logger.py`)
**Purpose**: Structured logging for the entire pipeline.

**Inputs**:
- Phase events
- Artifact metadata
- Performance metrics
- Error information

**Outputs**:
- JSONL trace files
- Correlation IDs
- Learning signals
- Performance reports

**Key Methods**:
- `start_trace(session_id, goal_id)`
- `log_phase(phase, data)`
- `end_trace(status, metrics)`

**Trace Surfaces**:
- Cognitive (decisions, reasoning)
- Operational (execution, performance)
- Contextual (state, environment)

### 8. Recursive Controller (`controller.py`)
**Purpose**: Orchestrates the entire recursive loop.

**Inputs**:
- Initial goal
- Configuration
- Operator constraints

**Outputs**:
- Session results
- Final artifacts
- Learning summary
- Performance report

**Key Methods**:
- `run_session(goal, config)`
- `manage_recursion(depth, state)`
- `handle_failure(error, context)`

**Control Features**:
- Maximum recursion depth (default: 3)
- Cycle detection
- Timeout enforcement
- Graceful degradation

## Data Contracts

### 1. Prompt Task Schema
```json
{
  "prompt_id": "uuid",
  "goal_id": "uuid",
  "cycle_number": 1,
  "task_summary": "string",
  "prompt_text": "string",
  "expected_artifacts": ["file1.py", "config.json"],
  "execution_mode": "python|bash|document_transform|analysis_only",
  "evaluation_requirements": {
    "schema_validation": true,
    "syntax_check": true,
    "tests_run": ["test_basic"],
    "policy_check": "sensitive"
  },
  "max_recursion_depth": 3
}
```

### 2. Execution Result Schema
```json
{
  "execution_id": "uuid",
  "prompt_id": "uuid",
  "status": "success|failed|timeout",
  "start_time": "iso8601",
  "end_time": "iso8601",
  "exit_code": 0,
  "stdout_path": "/staging/stdout.txt",
  "stderr_path": "/staging/stderr.txt",
  "artifacts_created": ["/staging/file1.py"],
  "tests_run": 5,
  "tests_passed": 5,
  "evaluation_status": "pending"
}
```

### 3. Trace Schema
```json
{
  "trace_id": "uuid",
  "cycle_number": 1,
  "phase": "inventory|planning|prompting|execution|evaluation|promotion",
  "goal_id": "uuid",
  "prompt_id": "uuid",
  "action": "scan_started|plan_created|prompt_generated|execution_started",
  "inputs_summary": {"files_scanned": 150},
  "artifacts": ["inventory.json"],
  "status": "started|completed|failed",
  "error_code": "inventory_empty",
  "latency_ms": 1250,
  "projectx_judgment": "ALLOW|BLOCK|ESCALATE",
  "promotion_decision": "PROMOTE|REJECT|REVISE|ESCALATE"
}
```

## Integration Points

### 1. ProjectX Integration
**Role**: Safety and policy reviewer
**When**: Before promotion of sensitive artifacts
**Judgments**: ALLOW, BLOCK, ESCALATE
**Sensitive Paths**:
- Production config files
- Live trading connectors
- Broker core files
- Security-sensitive scripts
- Self-compiler promotion rules

### 2. Mesh Bus Integration
**Channels**:
- `self_compile_events` - Pipeline phase events
- `artifact_status` - Promotion status updates
- `safety_alerts` - Safety violations
- `maintenance_events` - System maintenance

**Events**:
- `cycle_started`, `inventory_completed`
- `candidate_generated`, `evaluation_failed`
- `promotion_blocked`, `promotion_approved`

### 3. Agent Lightning Integration
**Trace Correlation**: Via trace_id
**Surfaces**: Cognitive, operational, contextual
**Learning Signals**: From evaluation outcomes

### 4. Obsidian Integration
**Documentation**: Runbooks, architecture docs
**Knowledge Graph**: Component relationships
**Search**: Inventory and trace search

## Safety Mechanisms

### 1. Bounded Recursion
- Maximum depth: configurable (default 3)
- Cycle detection: prevents infinite loops
- Timeout enforcement: per-cycle and total

### 2. Staged Execution
- All artifacts land in staging first
- No direct production writes
- Rollback always possible

### 3. Explicit Gates
- Automated quality checks
- Policy compliance validation
- ProjectX review for sensitive changes

### 4. Comprehensive Observability
- Every action logged
- Trace correlation
- Performance monitoring
- Error tracking

### 5. Rollback Guarantees
- Backup before promotion
- Rollback plan always generated
- Atomic promotion operations

## Configuration

### Core Configuration (`config/self_compiler_config.json`)
```json
{
  "recursion": {
    "max_depth": 3,
    "max_total_time_seconds": 3600,
    "max_cycle_time_seconds": 300
  },
  "execution": {
    "staging_directory": "./staging",
    "resource_limits": {
      "memory_mb": 1024,
      "timeout_seconds": 60,
      "max_file_size_mb": 10
    }
  },
  "evaluation": {
    "minimum_score": 0.8,
    "required_gates": ["schema", "syntax", "policy"],
    "sensitive_paths": ["config/", "simp/server/", "simp/broker.py"]
  },
  "integration": {
    "projectx_enabled": true,
    "mesh_bus_enabled": true,
    "obsidian_enabled": false
  }
}
```

## Success Criteria

### Phase 1 (MVP)
- [ ] Inventory scanner discovers codebase components
- [ ] Planner creates simple one-step plans
- [ ] Prompt compiler generates structured prompts
- [ ] Executor runs tasks in staging
- [ ] Evaluator scores against basic criteria
- [ ] Trace logger captures pipeline events

### Phase 2 (Integration)
- [ ] ProjectX integration for safety review
- [ ] Mesh Bus events for coordination
- [ ] Recursive controller with depth limiting
- [ ] Promotion pipeline with rollback

### Phase 3 (Production)
- [ ] All safety mechanisms operational
- [ ] Comprehensive test coverage
- [ ] Performance optimization
- [ ] Operator runbooks complete

## Non-Goals
- Uncontrolled autonomous rewriting of entire ecosystem
- Direct production mutation without staging
- Silent failures or opaque operations
- Unbounded recursive execution
- Bypassing safety gates or policy checks

## Next Steps
1. Implement inventory scanner
2. Build prompt compiler with structured contracts
3. Create staged executor with safety limits
4. Integrate with existing tracing and ProjectX
5. Test bounded recursion controller
6. Document operator runbooks