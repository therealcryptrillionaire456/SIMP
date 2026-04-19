# SIMP Flock Flight Plan - Complete Implementation

## Overview
The SIMP flock flight plan provides a structured, controlled approach to running multiple AI agents (geese) on the SIMP system. It transforms chaotic multi-agent coding into a professional flight operation with clear roles, boundaries, and protocols.

## The Flock Roles

### 1. Mother Goose (Orchestrator)
**Role**: Mission control, task assignment, scope management
**Location**: Control window in tmux
**Rules**: No coding, only orchestration
**Output**: Mission board, task assignments, progress tracking

### 2. SIMP Goose (Implementer)
**Role**: Code and test implementation in SIMP repo
**Location**: SIMP repo directory
**Rules**: Code/tests only, no config changes, additive changes only
**Output**: Files changed, tests run, completion reports

### 3. Stray Goose (Planner)
**Role**: Architecture mapping, opportunity ranking, research synthesis
**Location**: ~/stray_goose directory
**Rules**: Planning only, no implementation, bounded recommendations
**Output**: Architecture maps, execution plans, decision memos

### 4. Watchtower (Monitor)
**Role**: System health monitoring, log watching, alerting
**Location**: Observability window in tmux
**Rules**: Shell/curl only, no infrastructure changes
**Output**: Health reports, status updates, anomaly detection

## Core Scripts

### Startup & Session Management
- `scripts/start_mother_goose_tmux.sh` - Creates tmux session with 4 windows
- `tmux attach -t mothergoose` - Attaches to existing session

### Operational Scripts
- `scripts/watchtower.sh` - System health checks
- `scripts/preflight_check.sh` - Morning verification
- `scripts/maintenance_check.sh` - Mid-flight monitoring
- `scripts/landing_protocol.sh` - End-of-day wrap-up

## Standard Launch Order

1. **Start tmux session**: `./scripts/start_mother_goose_tmux.sh`
2. **Attach**: `tmux attach -t mothergoose`
3. **Start infrastructure**: Broker and dashboard
4. **Start Watchtower**: Health monitoring
5. **Launch Mother Goose**: Mission board creation
6. **Launch SIMP Goose**: Wait for tasks
7. **Launch Stray Goose**: Planning support

## Daily Workflow

### Morning (Preflight)
1. Start tmux session
2. Run preflight checklist
3. Start broker/dashboard
4. Verify system health
5. Mother Goose creates mission board

### During Flight (Maintenance Loop)
1. Every 30-60 minutes: Maintenance check
2. Mother Goose queries goose status
3. Watchtower reports system health
4. Adjust assignments as needed
5. Prevent scope expansion

### End of Day (Landing Protocol)
1. Stop all active work
2. Gather completion reports
3. Take system health snapshot
4. Create landing report
5. Plan first task for next session

## Task Management

### Task Packet Format
- **Objective**: Clear, single objective
- **Allowed Files**: Explicit boundaries
- **Forbidden Areas**: Protected zones
- **Success Conditions**: Measurable outcomes
- **Stop Conditions**: Time/scope limits
- **Test Command**: Validation command
- **Completion Report**: Standard format

### Task Lifecycle
1. Mother Goose assigns task packet
2. Goose accepts and begins work
3. Goose works within boundaries
4. Goose validates with tests
5. Goose provides completion report
6. Mother Goose evaluates and assigns next

## Key Principles

### 1. Role Separation
Each goose has one job. No goose does all four jobs.

### 2. Bounded Work
All work is bounded by time, scope, and file boundaries.

### 3. Additive Changes
Prefer additive, reversible changes over rewrites.

### 4. Test-First Validation
Every change validated with tests before moving on.

### 5. Controlled Pipeline
Mother Goose → Stray Goose → SIMP Goose → Watchtower

## Emergency Procedures

### System Unstable
1. Stop all geese immediately
2. Assess damage with Watchtower
3. Roll back if possible (git revert)
4. Stabilize before resuming

### Scope Expansion
1. Stop violating goose immediately
2. Re-focus on original task
3. Document violation
4. Adjust boundaries if needed

### Process Failure
1. Check logs: `tail -100 ~/bullbear/logs/simp_broker.log`
2. Restart: `./bin/restart_all.sh`
3. Verify: `./scripts/watchtower.sh`

## Benefits

1. **Controlled Chaos**: Multiple agents without cross-talk
2. **Progress Tracking**: Clear completion and next steps
3. **Quality Control**: Tests and validation at each step
4. **Knowledge Preservation**: Landing reports capture context
5. **Scope Management**: Prevents feature creep and drift
6. **Operational Awareness**: Watchtower maintains system visibility

## Quick Start Commands

```bash
# One-command launch
./scripts/start_mother_goose_tmux.sh && tmux attach -t mothergoose

# In tmux, follow launch order:
# 1. Control pane 1: ./bin/start_broker.sh
# 2. Observability pane 0: watch -n 30 ./scripts/watchtower.sh
# 3. Control pane 0: Paste Mother Goose prompt
# 4. Geese pane 0: Paste SIMP Goose prompt
# 5. Geese pane 1: Paste Stray Goose prompt
```

## Documentation Location
All prompts and protocols: `docs/flock_prompts/`

## Ready for Flight
The flock is configured, scripts are written, protocols are defined. The system is ready for controlled, productive multi-agent operation.