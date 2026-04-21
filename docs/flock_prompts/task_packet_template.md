# Task Packet Template

Mother Goose should assign work using this standardized task packet format.

## Task Packet Structure:

**Task ID**: [Date]-[Sequence]-[Goose]
**Objective**: Clear, single objective
**Owner**: Which goose (SIMP Goose, Stray Goose, Watchtower)
**Priority**: P1 (revenue), P2 (analytical), P3 (showcase), P4 (infrastructure)

**Allowed Files**:
- [List specific files or directories]
- [Be explicit about boundaries]

**Forbidden Areas**:
- [List protected files/systems]
- [No-go zones]

**Success Conditions**:
- [Measurable outcomes]
- [Acceptance criteria]
- [Test requirements]

**Stop Conditions**:
- [Time limit (e.g., 90 minutes)]
- [Scope expansion triggers]
- [Risk thresholds]

**Test Command**:
```bash
[Exact command to run for validation]
```

**Completion Report Format**:
- Files changed
- Tests run and results
- Any deviations from plan
- Next steps if incomplete

## Example Task Packet:

**Task ID**: 2026-04-11-01-SIMP
**Objective**: Implement TimesFM observability endpoints
**Owner**: SIMP Goose
**Priority**: P2 (analytical backbone)

**Allowed Files**:
- simp/server/http_server.py
- simp/server/broker.py  
- tests/test_timesfm_observability_endpoints.py
- simp/integrations/timesfm_service.py (if exists)

**Forbidden Areas**:
- Any provider configuration files
- Any unrelated routes or endpoints
- Startup scripts or process management
- Database schemas or migrations

**Success Conditions**:
1. New endpoint `/timesfm/health` returns JSON with status
2. New endpoint `/timesfm/stats` returns TimesFM metrics
3. Broker stats include TimesFM block
4. Tests pass with 100% coverage for new code
5. No breaking changes to existing functionality

**Stop Conditions**:
- If task exceeds 90 minutes
- If touching provider configs
- If modifying unrelated subsystems
- If test coverage drops below existing levels

**Test Command**:
```bash
python3.10 -m pytest tests/test_timesfm_observability_endpoints.py -v --tb=short
```

**Completion Report Format**:
```
Task: [Task ID]
Status: [Complete/Partial/Blocked]
Files Changed:
- file1.py (lines added: X, lines modified: Y)
- file2.py (lines added: X, lines modified: Y)

Tests Run:
- test_timesfm_health_endpoint: PASS
- test_timesfm_stats_endpoint: PASS
- test_broker_includes_timesfm: PASS

Deviations:
[Any changes from original plan]

Next Actions:
[If incomplete, what's needed]
```

## Mother Goose Assignment Prompt:

When assigning a task, use this format:

```text
Assigning task: [Task ID]

Objective: [Clear objective]

Boundaries:
- Allowed: [list]
- Forbidden: [list]

Success looks like: [success conditions]

Stop if: [stop conditions]

Validate with: [test command]

Report back with: [completion report format]

Begin when ready.
```

## SIMP Goose Response Format:

When completing a task, SIMP Goose should respond:

```text
Task: [Task ID]
Status: Complete

Files Changed:
1. [file path] - [changes made]
2. [file path] - [changes made]

Tests Run:
1. [test name]: [PASS/FAIL]
2. [test name]: [PASS/FAIL]

Compilation: [All files compile successfully]

Deviations: [None or explanation]

Ready for next task.
```

## Task Lifecycle:

1. **Assignment**: Mother Goose creates task packet
2. **Acceptance**: Goose acknowledges and begins
3. **Execution**: Goose works within boundaries
4. **Validation**: Goose runs tests and compiles
5. **Report**: Goose provides completion report
6. **Evaluation**: Mother Goose reviews and assigns next task

## Task Types:

### Type 1: Implementation (SIMP Goose)
- Code changes
- Test writing
- Module creation
- Bug fixes

### Type 2: Analysis (Stray Goose)
- Architecture mapping
- Opportunity ranking
- Research synthesis
- Planning documents

### Type 3: Monitoring (Watchtower)
- Health checks
- Log analysis
- Performance monitoring
- Alert setup

### Type 4: Orchestration (Mother Goose)
- Task assignment
- Progress tracking
- Blocker resolution
- Scope management

## Task Queue Management:

Mother Goose maintains a simple task queue:
1. Current task (in progress)
2. Next task (ready when current completes)
3. Backlog (prioritized but not scheduled)

Never assign more than one task per goose at a time.
Wait for completion report before assigning next task.