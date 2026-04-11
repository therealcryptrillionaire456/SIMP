# Mid-Flight Maintenance Loop

Once the flock is airborne, Mother Goose should run this maintenance loop every 30-60 minutes.

## Maintenance Check Points:

### 1. System Health Check (Watchtower reports)
```bash
# Run watchtower check
./scripts/watchtower.sh

# Expected healthy signals:
# - Broker: responding
# - Dashboard: OK  
# - Agents: >0 registered
# - Processes: expected count
```

### 2. Goose Status Check (Mother Goose queries each goose)

**To SIMP Goose**:
```
Status check:
- Current task: [Task ID]
- Progress: [% complete or status]
- Blockers: [None or list]
- Estimated completion: [time]
```

**To Stray Goose**:
```
Status check:
- Current analysis: [topic]
- Key findings: [bullet points]
- Recommendations: [for SIMP Goose]
- Estimated completion: [time]
```

**To Watchtower**:
```
Status check:
- System health: [Green/Yellow/Red]
- Alerts: [None or list]
- Log anomalies: [None or list]
```

### 3. Scope Check (Mother Goose evaluates)
- [ ] Is any goose working outside assigned boundaries?
- [ ] Has task scope expanded beyond original definition?
- [ ] Are there duplicate efforts between geese?
- [ ] Is any goose blocked waiting for another?

### 4. Progress Check (Mother Goose reviews)
- [ ] Are tasks progressing at expected pace?
- [ ] Are completion reports being provided?
- [ ] Are tests passing after changes?
- [ ] Is system stability maintained?

## Maintenance Loop Script:

Create `scripts/maintenance_check.sh`:

```bash
#!/bin/bash
# SIMP Flock Maintenance Check

echo "=== SIMP Maintenance Check ==="
echo "Timestamp: $(date)"
echo "Check interval: Every 30-60 minutes"
echo ""

echo "1. System Health:"
./scripts/watchtower.sh | tail -20

echo ""
echo "2. Process Check:"
echo "Broker: $(ps aux | grep -v grep | grep -c "python.*broker") process(es)"
echo "Dashboard: $(ps aux | grep -v grep | grep -c "python.*dashboard") process(es)"
echo "Total Python SIMP processes: $(ps aux | grep -v grep | grep python | grep -c simp)"

echo ""
echo "3. Task Status (manual check required):"
echo "• SIMP Goose: Check current task progress"
echo "• Stray Goose: Check analysis completion"
echo "• Watchtower: Check for alerts"
echo ""
echo "4. Scope Check:"
echo "• Are all geese within boundaries? [YES/NO]"
echo "• Any duplicate work? [YES/NO]"
echo "• Any blockers? [YES/NO]"
echo ""
echo "=== Maintenance Actions ==="
echo "If system unhealthy:"
echo "1. Check logs: tail -50 ~/bullbear/logs/simp_broker.log"
echo "2. Restart if needed: ./bin/restart_all.sh"
echo ""
echo "If goose blocked:"
echo "1. Identify blocker"
echo "2. Assign to appropriate goose"
echo "3. Adjust task if needed"
echo ""
echo "If scope expanded:"
echo "1. Stop expansion immediately"
echo "2. Re-focus on original task"
echo "3. Log expansion for future planning"
```

## Mother Goose Maintenance Prompt:

Every 30-60 minutes, Mother Goose should run:

```text
Run mid-flight maintenance check.

Check:
1) System health (Watchtower report)
2) Goose status (progress, blockers)
3) Scope containment (no expansion, no duplicates)
4) Progress pace (tasks moving, tests passing)

Current concerns:
- [List any known issues]

Return:
- Health status: Green/Yellow/Red
- Blockers needing resolution
- Scope violations if any
- Recommended adjustments
```

## Maintenance Triggers:

### Green (Proceed):
- All systems healthy
- Geese within boundaries
- Tasks progressing
- Tests passing

### Yellow (Monitor):
- Minor health issues
- Slight scope creep
- Slow progress
- Test flakiness

### Red (Intervene):
- System unhealthy
- Major scope violation
- Goose blocked >30min
- Tests failing

## Intervention Actions:

### For System Issues:
1. Check logs immediately
2. Restart affected components
3. Verify health returns
4. Document incident

### For Scope Issues:
1. Stop violating goose immediately
2. Re-focus on original task
3. Document scope violation
4. Adjust boundaries if needed

### For Blockers:
1. Identify root cause
2. Assign to appropriate goose
3. Adjust task or provide help
4. Monitor resolution

### For Progress Issues:
1. Check if task too large
2. Break into smaller tasks
3. Re-prioritize if needed
4. Adjust expectations

## Maintenance Log:

Mother Goose should maintain a simple maintenance log:

```
[Timestamp] Maintenance check
Health: Green
SIMP Goose: Task 2026-04-11-01-SIMP, 75% complete
Stray Goose: Architecture map, synthesizing
Watchtower: All systems nominal
Blockers: None
Actions: None needed
```

## End-of-Loop Actions:

After each maintenance check:

1. **Update task status** in Mother Goose tracking
2. **Adjust assignments** if needed
3. **Document findings** in maintenance log
4. **Schedule next check** (30-60 minutes)

## Emergency Procedures:

If system becomes unstable:
1. **Stop all geese** from making changes
2. **Assess damage** with Watchtower
3. **Roll back** if possible (git revert)
4. **Stabilize** before resuming work

Remember: The maintenance loop turns three smart agents into a controlled pipeline instead of a drift generator.