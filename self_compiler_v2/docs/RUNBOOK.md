# Sovereign Self Compiler v2 - Operator Runbook

## Overview

The Sovereign Self Compiler v2 is a controlled recursive self-compilation system that enables the SIMP ecosystem to inspect, plan, generate, execute, verify, and stage its own improvements with safety guarantees. This runbook provides operational guidance for running, monitoring, and troubleshooting the system.

## System Architecture

### Core Components

1. **Inventory Scanner** (`inventory.py`): Discovers and catalogs codebase components
2. **Planner** (`planner.py`): Creates next-step recursive plans based on goals
3. **Prompt Compiler** (`prompt_compiler.py`): Compiles structured self-prompts
4. **Executor** (`executor.py`): Safely executes generated tasks in staged environment
5. **Evaluator** (`evaluator.py`): Scores and gates candidate outputs
6. **Promoter** (`promoter.py`): Handles staging vs promotion decisions
7. **Trace Logger** (`trace_logger.py`): Structured logging for the entire pipeline
8. **CLI** (`cli.py`): Command-line interface for running sessions

### Data Flow

```
Goal → Inventory → Plan → Prompt → Execute → Evaluate → Promote → Trace
      ↑                                                          ↓
      └───────────────────── Recursive Loop ─────────────────────┘
```

### Safety Mechanisms

- **Bounded Recursion**: Maximum depth of 3 cycles (configurable)
- **Staged Execution**: All artifacts land in staging first
- **Explicit Gates**: Automated quality and safety checks
- **ProjectX Integration**: Safety review for sensitive changes
- **Rollback Guarantees**: Always able to revert to known good state

## Quick Start

### Installation

```bash
# Navigate to self-compiler directory
cd /Users/kaseymarcelle/Downloads/kashclaw\ \(claude\ rebuild\)/simp/self_compiler_v2

# Install dependencies
pip install -r requirements.txt  # If requirements file exists
# Or install core dependencies:
pip install psutil requests
```

### Basic Usage

```bash
# Run a simple self-compilation session
python -m src.cli run "Create a test module for the SIMP system" --cycles 1

# Show recent traces
python -m src.cli traces --limit 10

# Show session report
python -m src.cli report <session_id>

# Clean up old files
python -m src.cli cleanup --hours 24
```

### Phase 2 Features (Enhanced Capabilities)

#### 25-Cycle Bounded Autonomy (Default)
```bash
# Run 25 cycles with safe stop conditions (default)
python -m src.cli run "25-cycle optimization"

# 25 cycles with custom pause and failure limits
python -m src.cli run "Safe optimization" --cycles 25 --pause 30 --max-failures 3 --max-time 1800

# Continuous mode with 25-cycle bound
python -m src.cli run "Bounded continuous" --cycles 25 --continuous --pause 60
```

#### Scaling to 100 Cycles
```bash
# Scale to 100 cycles with increased time limits
python -m src.cli run "100-cycle deep scan" --cycles 100 --max-time 7200

# 100 cycles with continuous mode
python -m src.cli run "Long-running analysis" --cycles 100 --continuous --pause 120 --max-failures 5

# Test 100-cycle configuration
python -m src.cli run "Scale test" --cycles 100 --max-time 10800 --max-failures 5
```

#### Session Management & Monitoring
```bash
# Stress test the SIMP system
python -m src.cli stress-test --agents all --duration 60

# Manage saved sessions
python -m src.cli sessions list
python -m src.cli sessions show <session_id>
python -m src.cli sessions resume <session_id>

# Generate enhanced reports with scaling metrics
python -m src.cli enhanced-report <session_id> --format json --output report.json

# Monitor sessions in real-time
python -m src.cli monitor <session_id> --interval 5
```

For detailed documentation on Phase 2 features, see [PHASE2_FEATURES.md](PHASE2_FEATURES.md).

### Configuration

The system is configured via `config/self_compiler_config.json`. Key sections:

- **recursion**: Controls recursion depth and timeouts
- **execution**: Resource limits and execution modes
- **evaluation**: Scoring weights and required gates
- **promotion**: Promotion policies and safety rules
- **integration**: ProjectX, Mesh Bus, and other integrations
- **observability**: Tracing and logging settings

## Operational Procedures

### Starting a Session

1. **Define Clear Goal**: Be specific about what you want the system to improve
2. **Set Appropriate Cycles**: Start with 1 cycle for testing, max 3 for production
3. **Choose Target Directories**: Specify which codebase areas to inventory
4. **Set Approval Level**: Decide if auto-approval is safe for this session

Example:
```bash
python -m src.cli run \
  "Improve error handling in the inventory scanner" \
  --cycles 2 \
  --directories ./src ./config \
  --auto-approve
```

### Monitoring Sessions

#### Real-time Monitoring

```bash
# Watch trace events in real-time
watch -n 2 "python -m src.cli traces --session <session_id> --limit 5"

# Check session status
python -m src.cli report <session_id>
```

#### Trace Analysis

Traces are stored in JSONL format in `traces/` directory:

```bash
# View current trace file
tail -f traces/current_traces.jsonl | jq .

# Search for specific events
grep "promotion_decided" traces/current_traces.jsonl | jq .
```

#### Performance Monitoring

Key metrics to monitor:
- Cycle completion time (should be < 5 minutes)
- Memory usage (should be < 1GB)
- Success rate of promotions
- Error frequency and types

### Handling Promotions

#### Promotion Decisions

The system can make four types of promotion decisions:

1. **PROMOTE**: Artifact passes all gates and is promoted
2. **REJECT**: Artifact fails evaluation and is rejected
3. **REVISE**: Artifact needs revision based on feedback
4. **ESCALATE**: Requires operator or ProjectX review

#### Manual Review Process

When escalation is required:

1. **Review Evaluation Report**: Check `evaluation_result.json` in staging
2. **Examine Artifacts**: Inspect generated files in staging directory
3. **Check ProjectX Judgment**: Review safety assessment if applicable
4. **Make Decision**: Use CLI to approve or reject

```bash
# After reviewing, you can manually promote specific artifacts
# (This requires modifying the promoter.py logic for manual overrides)
```

#### Rollback Procedures

If a promotion causes issues:

1. **Locate Rollback Plan**: Find `rollback_<promotion_id>.json` in backups/
2. **Execute Rollback**: Use promoter's rollback functionality
3. **Verify Restoration**: Check that original files are restored

```python
# Manual rollback example
from src.promoter import Promoter
promoter = Promoter(config, staging_dir, promotion_dir)
promoter.execute_rollback(Path("backups/rollback_abc123.json"))
```

### Maintenance Tasks

#### Regular Cleanup

```bash
# Clean files older than 24 hours (recommended daily)
python -m src.cli cleanup --hours 24

# Clean old trace files (recommended weekly)
# Manually remove files older than 7 days from traces/
```

#### Configuration Updates

1. **Backup Current Config**: Always backup before changes
2. **Test Changes**: Run a test session with new configuration
3. **Monitor Impact**: Watch for performance or behavior changes
4. **Rollback if Needed**: Restore old config if issues arise

#### Dependency Management

Check and update dependencies quarterly:
```bash
pip list --outdated
pip install --upgrade psutil requests
```

## Troubleshooting

### Common Issues

#### Issue: Session Hangs or Times Out
**Symptoms**: No progress after several minutes, high CPU usage
**Solutions**:
1. Check resource limits in config (`execution.resource_limits`)
2. Increase timeout values if needed
3. Check for infinite loops in generated code
4. Kill hanging processes manually if necessary

#### Issue: Low Evaluation Scores
**Symptoms**: Artifacts consistently score below minimum threshold
**Solutions**:
1. Review evaluation criteria in config (`evaluation.score_weights`)
2. Check if gates are too strict for the task
3. Examine evaluation feedback for specific issues
4. Adjust minimum score threshold if appropriate

#### Issue: ProjectX Review Failures
**Symptoms**: Promotions stuck in ESCALATE state
**Solutions**:
1. Verify ProjectX endpoint is accessible
2. Check network connectivity
3. Review ProjectX configuration (`integration.projectx`)
4. Consider temporary disable if ProjectX is unavailable

#### Issue: Disk Space Exhaustion
**Symptoms**: "No space left on device" errors
**Solutions**:
1. Run cleanup: `python -m src.cli cleanup --hours 0` (clean all)
2. Increase cleanup frequency
3. Monitor staging and backup directory sizes
4. Consider moving traces to different storage

### Debugging Procedures

#### Step 1: Check Logs
```bash
# View application logs
tail -f logs/self_compiler.log  # If logging to file is configured

# View system logs
dmesg | tail -20
```

#### Step 2: Examine Traces
```bash
# Get detailed trace for failed session
python -m src.cli report <failed_session_id>

# Search for error events
grep '"status":"failed"' traces/current_traces.jsonl | jq .
```

#### Step 3: Inspect Staging Directory
```bash
# List contents of staging for a specific execution
ls -la staging/exec_<execution_id>/

# Check execution results
cat staging/exec_<execution_id>/execution_result.json | jq .

# Examine generated artifacts
cat staging/exec_<execution_id>/generated_script.py
```

#### Step 4: Test Components Independently
```python
# Test executor directly
from src.executor import Executor, ExecutionMode
executor = Executor(config["execution"], Path("./staging"))
result = executor.execute_task(test_prompt)

# Test evaluator directly  
from src.evaluator import Evaluator
evaluator = Evaluator(config["evaluation"])
result = evaluator.evaluate(execution_result, prompt)
```

## Security Considerations

### Sensitive Operations

The following operations require special attention:

1. **Production Code Modifications**: Always require ProjectX review
2. **Configuration Changes**: Test in staging before promotion
3. **Security Script Updates**: Review manually before approval
4. **Self-Compiler Modifications**: Extreme caution required

### Access Control

1. **Operator Authentication**: Ensure only authorized users can run sessions
2. **Approval Workflows**: Multi-person approval for sensitive promotions
3. **Audit Logging**: All actions must be traceable and immutable
4. **Backup Integrity**: Regular verification of backup files

### Network Security

1. **ProjectX Endpoint**: Use HTTPS for ProjectX communications
2. **Mesh Bus Channels**: Encrypt sensitive event data
3. **External Dependencies**: Verify integrity of pip packages
4. **Firewall Rules**: Restrict network access for execution sandbox

## Performance Optimization

### Configuration Tuning

#### For Development/Testing:
```json
{
  "recursion": {
    "max_depth": 1,
    "max_cycle_time_seconds": 60
  },
  "execution": {
    "resource_limits": {
      "memory_mb": 512,
      "timeout_seconds": 30
    }
  }
}
```

#### For Production:
```json
{
  "recursion": {
    "max_depth": 3,
    "max_cycle_time_seconds": 300
  },
  "execution": {
    "resource_limits": {
      "memory_mb": 2048,
      "timeout_seconds": 120
    }
  }
}
```

### Monitoring and Alerting

Set up monitoring for:

1. **Disk Usage**: Alert when staging exceeds 80% capacity
2. **Memory Usage**: Alert when approaching resource limits
3. **Error Rate**: Alert when failure rate exceeds 10%
4. **Cycle Duration**: Alert when cycles take > 5 minutes

### Scaling Considerations

For large codebases:

1. **Incremental Inventory**: Scan only changed directories
2. **Parallel Execution**: Run multiple cycles concurrently (future enhancement)
3. **Distributed Tracing**: Use external tracing system for large volumes
4. **Database Backend**: Replace JSON files with database for high volume

## Integration Guide

### ProjectX Integration

ProjectX provides safety reviews for sensitive promotions:

1. **Enable in Config**: Set `integration.projectx.enabled: true`
2. **Configure Endpoint**: Set `integration.projectx.endpoint`
3. **Define Sensitive Paths**: List in `evaluation.sensitive_paths`
4. **Test Connection**: Verify ProjectX is reachable before production use

### Mesh Bus Integration

For internal event coordination:

1. **Enable Channels**: Configure in `integration.mesh_bus.channels`
2. **Subscribe to Events**: Other systems can listen to self-compiler events
3. **Event TTL**: Set appropriate TTL for event retention

### Agent Lightning Integration

For advanced tracing and learning:

1. **Enable Trace Correlation**: Set `integration.agent_lightning.trace_correlation: true`
2. **Learning Signals**: Enable to improve prompt generation over time
3. **Performance Integration**: Correlate with system performance metrics

### Obsidian Integration

For documentation and knowledge management:

1. **Configure Vault Path**: Set `integration.obsidian.vault_path`
2. **Generate Runbooks**: Enable automatic documentation generation
3. **Sync Traces**: Optionally sync trace data for analysis

## Recovery Procedures

### Complete System Failure

If the self-compiler becomes unusable:

1. **Stop All Sessions**: Kill any running processes
2. **Backup Current State**: Copy staging, traces, and config
3. **Restore from Backup**: Use latest known-good backup
4. **Verify Integrity**: Test basic functionality
5. **Investigate Root Cause**: Examine logs and traces

### Data Corruption

If trace or staging data becomes corrupted:

1. **Isolate Corrupted Data**: Move to quarantine directory
2. **Restore from Backups**: Use promoter backup files
3. **Regenerate Missing Data**: Run new sessions as needed
4. **Implement Prevention**: Add data validation checks

### Security Breach

If unauthorized access is suspected:

1. **Immediate Shutdown**: Stop all self-compiler processes
2. **Preserve Evidence**: Secure logs, traces, and artifacts
3. **Access Review**: Audit all recent sessions and promotions
4. **Credential Rotation**: Change any compromised credentials
5. **Security Assessment**: Conduct thorough security review

## Training and Knowledge Transfer

### New Operator Onboarding

1. **Read Architecture Docs**: Review ARCHITECTURE.md and this runbook
2. **Run Test Sessions**: Practice with non-critical goals
3. **Shadow Experienced Operator**: Observe real sessions
4. **Handle Simulated Incidents**: Practice troubleshooting scenarios
5. **Get Certification**: Pass operational proficiency test

### Knowledge Documentation

Maintain the following documentation:

1. **This Runbook**: Keep updated with operational experience
2. **Architecture Decisions**: Document design choices and rationale
3. **Incident Reports**: Record and analyze all incidents
4. **Improvement Log**: Track system enhancements and optimizations

### Continuous Improvement

Regularly:

1. **Review Session Outcomes**: Analyze success/failure patterns
2. **Solicit Operator Feedback**: Gather user experience insights
3. **Update Configuration**: Refine based on operational data
4. **Enhance Safety Mechanisms**: Strengthen based on near-misses
5. **Performance Benchmarking**: Compare against baseline metrics

## Appendices

### A. Command Reference

```bash
# Full CLI reference
python -m src.cli --help
python -m src.cli run --help
python -m src.cli traces --help
python -m src.cli report --help
python -m src.cli cleanup --help
python -m src.cli config --help
```

### B. File Locations

- **Configuration**: `config/self_compiler_config.json`
- **Source Code**: `src/`
- **Staging Area**: `staging/`
- **Promoted Artifacts**: `promoted/`
- **Backups**: `backups/` (within promoted directory)
- **Traces**: `traces/`
- **Logs**: `logs/` (if file logging enabled)

### C. Contact Information

- **Primary Operator**: [Name/Team]
- **Backup Operator**: [Name/Team]
- **Security Contact**: [Name/Team]
- **Emergency Contact**: [Phone/Email]

### D. Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-04-14 | 2.0.0 | Initial release | Stray Goose |
| [Future] | 2.1.0 | [Planned enhancements] | [Team] |

---

**Last Updated**: 2026-04-14  
**Next Review Date**: 2026-07-14  
**Review Frequency**: Quarterly