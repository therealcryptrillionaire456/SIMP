# End-of-Day Landing Protocol

Do not just detach and forget. End each session with this landing protocol.

## Landing Protocol Steps:

### 1. Stop All Active Work
Mother Goose signals all geese to stop work and prepare for landing.

**Message to all geese**:
```
Landing protocol initiated.
Stop all active work immediately.
Prepare completion reports.
```

### 2. Gather Completion Reports
Each goose provides their final status:

**SIMP Goose report**:
```
Final status for [Date]:
Tasks completed:
1. [Task ID]: [Brief description]
   - Files changed: [list]
   - Tests run: [list with results]
   - Status: [Complete/Partial]

Current health: [System functional/Issues]
```

**Stray Goose report**:
```
Final analysis for [Date]:
Analyses completed:
1. [Analysis topic]
   - Key findings: [bullet points]
   - Recommendations: [for next session]
   - Artifacts: [documents created]

Opportunity rankings: [updated list]
```

**Watchtower report**:
```
Final system status for [Date]:
Health: [Green/Yellow/Red]
Metrics:
- Broker uptime: [hours]
- Agent count: [number]
- Error rate: [if measurable]
- Resource usage: [summary]

Alerts outstanding: [list]
```

### 3. System Health Snapshot
Run final health check:
```bash
./scripts/watchtower.sh
./scripts/maintenance_check.sh
```

### 4. Git Status Check
Check for uncommitted changes:
```bash
git status
git diff --stat
```

### 5. Create Landing Report
Mother Goose synthesizes all reports into landing document.

## Landing Report Template:

**Filename**: `logs/landing_report_YYYY-MM-DD.md`

```
# SIMP Flock Landing Report - YYYY-MM-DD

## Session Summary
Start time: [time]
End time: [time]
Duration: [hours]
Mother Goose: [name/version]
Overall status: [Successful/Partial/Aborted]

## Completed Work

### SIMP Goose
1. [Task ID]: [Description]
   - Changes: [files modified]
   - Tests: [results]
   - Impact: [system changes]

### Stray Goose  
1. [Analysis]: [Description]
   - Findings: [key insights]
   - Recommendations: [action items]
   - Artifacts: [documents]

### Watchtower
1. [Monitoring]: [Description]
   - Alerts: [handled]
   - Issues: [identified]
   - Metrics: [collected]

## System State

### Health Status
- Broker: [Healthy/Unhealthy]
- Dashboard: [OK/Down]
- Agents: [count]
- Processes: [stable/unstable]

### Git Status
- Uncommitted changes: [yes/no]
- Branch: [name]
- Last commit: [hash/message]

### Resource Status
- Disk space: [usage]
- Memory: [usage]
- Logs: [size/rotation]

## Blockers & Issues

### Resolved
1. [Issue]: [Resolution]

### Unresolved
1. [Issue]: [Impact, needed for next session]

### New Issues Discovered
1. [Issue]: [Description, severity]

## Next Session Planning

### First Task Recommendation
Task: [Task ID]
Owner: [Goose]
Priority: [P1-P4]
Rationale: [Why this first]

### Preparation Needed
1. [Action]: [Who, by when]
2. [Action]: [Who, by when]

### Risk Assessment
- High risk: [items]
- Medium risk: [items]
- Low risk: [items]

## Sign-off
- Mother Goose: [timestamp]
- SIMP Goose: [work complete]
- Stray Goose: [analysis complete]
- Watchtower: [system stable]
```

## Mother Goose Landing Prompt:

```text
Run end-of-day landing protocol.

Produce:
1) Completed tasks today
2) Files changed today
3) Tests run and results
4) Current health status of broker/proxy/monitoring
5) Unresolved blockers
6) First recommended task for next session

Keep it concise and operational.
Do not invent progress that was not reported by the flock.
```

## Landing Script:

Create `scripts/landing_protocol.sh`:

```bash
#!/bin/bash
# SIMP Flock Landing Protocol

echo "=== SIMP Landing Protocol ==="
echo "Timestamp: $(date)"
echo ""

echo "1. Final System Health:"
echo "----------------------"
./scripts/watchtower.sh

echo ""
echo "2. Git Status:"
echo "-------------"
git status --short
echo ""
echo "Recent commits:"
git log --oneline -5

echo ""
echo "3. Process Status:"
echo "-----------------"
echo "Broker: $(ps aux | grep -v grep | grep -c "python.*broker") process(es)"
echo "Dashboard: $(ps aux | grep -v grep | grep -c "python.*dashboard") process(es)"

echo ""
echo "4. Today's Changes (manual assessment needed):"
echo "---------------------------------------------"
echo "• SIMP Goose tasks completed: [list]"
echo "• Stray Goose analyses completed: [list]"
echo "• Watchtower alerts handled: [list]"

echo ""
echo "5. Recommendations for Next Session:"
echo "-----------------------------------"
echo "First task should be: [task]"
echo "Priority: [P1-P4]"
echo "Owner: [goose]"
echo ""
echo "Preparation needed:"
echo "1. [action]"
echo "2. [action]"

echo ""
echo "=== Landing Complete ==="
echo "System ready for shutdown or continued operation."
echo "Detach tmux with: Ctrl-b d"
echo "Re-attach with: tmux attach -t mothergoose"
```

## Post-Landing Actions:

### Option A: Continue Later
1. Detach tmux: `Ctrl-b d`
2. System remains running
3. Re-attach later: `tmux attach -t mothergoose`

### Option B: Graceful Shutdown
1. Stop broker: `pkill -f "python.*broker"`
2. Stop dashboard: `pkill -f "python.*dashboard"`
3. Verify processes stopped: `./scripts/watchtower.sh`
4. Detach tmux: `Ctrl-b d`

### Option C: Emergency Stop
If system unstable:
1. Kill all SIMP processes: `pkill -f "python.*simp"`
2. Check git for uncommitted changes
3. Revert if necessary: `git checkout -- .`
4. Document emergency stop in landing report

## Daily Landing Checklist:

- [ ] All geese stopped work
- [ ] Completion reports gathered
- [ ] System health snapshot taken
- [ ] Git status checked
- [ ] Landing report created
- [ ] Next session planned
- [ ] Appropriate shutdown/continuation chosen

## Benefits of Landing Protocol:

1. **Knowledge preservation**: No lost context between sessions
2. **Continuity**: Clear starting point for next session
3. **Accountability**: Track what was actually accomplished
4. **Quality control**: Catch issues before they compound
5. **Planning improvement**: Learn from each day's work

## Remember:
The landing protocol turns a chaotic coding session into a professional flight operation with proper debrief and handoff.