# Sovereign Self Compiler v2 - Phase 2 Features

## Overview
Phase 2 of the Sovereign Self Compiler v2 introduces four major enhancements to the system:
1. **Continuous Mode** - Run indefinitely with configurable pauses
2. **Stress Test Integration** - Integrate with SIMP system stress testing
3. **Session Persistence** - Save, resume, and manage sessions
4. **Enhanced Reporting** - Advanced analytics and real-time monitoring

## 1. Continuous Mode (Hardened for 25-100 Cycles)

### What is Continuous Mode?
Continuous mode allows the self-compiler to run with bounded autonomy, automatically starting new cycles after a configurable pause with safe stop conditions. This is hardened for 25-100 cycle runs with:

- **Bounded autonomy**: Clear stop conditions prevent infinite recursion
- **Safe failure behavior**: Automatic stop after consecutive failures
- **Time limits**: Maximum session duration enforcement
- **State persistence**: Full session state saved after each cycle

### Default Configuration for Scalable Runs
- **Default max_cycles**: 25 (easily bumpable to 100)
- **Default pause between cycles**: 60 seconds
- **Max consecutive failures**: 3 (stops loop if exceeded)
- **Max total time**: 3600 seconds (1 hour)

### Usage for 25-Cycle Runs

```bash
# Run 25 cycles (default) with safe stop conditions
python3.10 src/cli.py run "Optimize codebase"

# Run with explicit 25 cycles and custom pause
python3.10 src/cli.py run "25-cycle optimization" --cycles 25 --pause 30

# Run in continuous mode with 25-cycle limit and failure protection
python3.10 src/cli.py run "Continuous optimization" --cycles 25 --continuous --max-failures 3
```

### Usage for Scaling to 100 Cycles

```bash
# Scale to 100 cycles with increased time limits
python3.10 src/cli.py run "100-cycle deep optimization" --cycles 100 --max-time 7200

# 100 cycles with continuous mode and failure tolerance
python3.10 src/cli.py run "Long-running optimization" --cycles 100 --continuous --pause 120 --max-failures 5 --max-time 10800

# Test 100-cycle configuration without running (dry-run parameters)
python3.10 src/cli.py run "Test scaling" --cycles 100 --max-time 7200 --max-failures 5
```

### Features
- **Graceful Shutdown**: Press `Ctrl+C` to interrupt continuous mode
- **Cycle Pausing**: Configurable pause between cycles (default: 60 seconds)
- **Session Persistence**: Automatically saves state after each cycle
- **Resumable**: Interrupted sessions can be resumed later
- **Safe Stop Conditions**:
  - Max cycles reached (25 default, scalable to 100)
  - Max consecutive failures (3 default)
  - Max total time exceeded (3600 seconds default)
  - Cycle completion indication
  - User interrupt (Ctrl+C)
- **Strong Evaluation Gates**: No promotion without tests and checks
- **High Observability**: Full traces, enhanced reports, stress test hooks

## 2. Stress Test Integration

### What is Stress Test Integration?
Integration with the SIMP system's `watchtower_stress_test.py` to perform load testing on the broker and registered agents.

### Prerequisites
- `watchtower_stress_test.py` must be in the SIMP directory
- SIMP broker must be running
- Agents must be registered with the broker

### Usage

```bash
# Run stress test with default parameters
python3.10 src/cli.py stress-test

# Test specific agents
python3.10 src/cli.py stress-test --agents projectx_native kashclaw_gemma

# Customize test parameters
python3.10 src/cli.py stress-test --concurrent 10 --duration 60 --intents ping health_check
```

### Parameters
- `--agents`: List of agent IDs to test (default: all registered)
- `--concurrent`: Number of concurrent workers (default: 5)
- `--duration`: Test duration in seconds (default: 30)
- `--intents`: Intent types to test (default: ping, health_check)

### Output
- Real-time progress updates
- Summary statistics (success rate, response times)
- Recommendations for system optimization
- JSON results saved to `stress_test_results_<timestamp>.json`

## 3. Session Persistence

### What is Session Persistence?
Automatic saving of session state to disk, allowing:
- Session resumption after interruptions
- Historical session tracking
- Session metadata analysis

### Session Management Commands

```bash
# List all saved sessions
python3.10 src/cli.py sessions list

# List only active sessions
python3.10 src/cli.py sessions list --all

# Show session details
python3.10 src/cli.py sessions show <session_id>

# Resume an interrupted session
python3.10 src/cli.py sessions resume <session_id>
```

### Session Storage
- Location: `self_compiler_v2/sessions/`
- Format: JSON files (`session_<id>.json`)
- Automatic: Sessions are saved after each cycle
- Metadata: Includes timestamps, status, cycles, and goals

### Resume Capabilities
Sessions can be resumed if they are in these states:
- `unknown` (never completed)
- `interrupted` (stopped by user)
- `partial_failure` (some cycles failed)

## 4. Enhanced Reporting

### What is Enhanced Reporting?
Advanced analytics and reporting features including:
- Performance metrics by phase
- Success rate analysis
- Real-time monitoring
- Exportable reports in multiple formats

### Report Generation

```bash
# Generate text format report (default)
python3.10 src/cli.py enhanced-report <session_id>

# Generate JSON format report
python3.10 src/cli.py enhanced-report <session_id> --format json

# Generate JSON report and save to file
python3.10 src/cli.py enhanced-report <session_id> --format json --output report.json
```

### Report Contents
1. **Basic Metrics**
   - Session ID, goal, status
   - Start/end times, cycle count
   - Continuous mode status

2. **Performance Metrics**
   - Average phase durations
   - Phase success rates
   - Promotion outcomes and rates
   - Artifacts promoted count

3. **Trace Metrics**
   - Event counts and distribution
   - Duration and latency statistics
   - Error counts and details

4. **Recommendations**
   - Actionable insights based on analysis
   - Performance optimization suggestions
   - Error resolution guidance

### Real-Time Monitoring

```bash
# Monitor session in real-time
python3.10 src/cli.py monitor <session_id>

# Monitor with custom refresh interval
python3.10 src/cli.py monitor <session_id> --interval 5
```

### Monitoring Features
- **Live Updates**: Shows new events as they occur
- **Status Display**: Current phase, cycle count, session status
- **Error Highlighting**: Immediate visibility of failures
- **Auto-refresh**: Configurable refresh interval (default: 2 seconds)

## Example Workflows

### Workflow 1: Continuous Optimization
```bash
# Start continuous optimization session
python3.10 src/cli.py run "Optimize test coverage" --continuous --pause 300

# Monitor progress in another terminal
python3.10 src/cli.py monitor <session_id>

# If interrupted, resume later
python3.10 src/cli.py sessions list
python3.10 src/cli.py sessions resume <session_id>

# Generate final report
python3.10 src/cli.py enhanced-report <session_id> --format json --output optimization_report.json
```

### Workflow 2: System Stress Testing
```bash
# Run stress test before optimization
python3.10 src/cli.py stress-test --agents all --duration 120

# Analyze stress test results
cat stress_test_results_*.json | jq '.recommendations'

# Run optimization with stress-aware parameters
python3.10 src/cli.py run "Optimize with load considerations" --continuous --pause 600
```

### Workflow 3: Batch Processing
```bash
# Run multiple sessions
python3.10 src/cli.py run "Task 1" --cycles 3 --output task1.json
python3.10 src/cli.py run "Task 2" --cycles 3 --output task2.json

# Compare sessions
python3.10 src/cli.py enhanced-report <session1_id>
python3.10 src/cli.py enhanced-report <session2_id>

# Generate combined report
python3.10 src/cli.py sessions list --all > all_sessions.txt
```

## Configuration

### Continuous Mode Settings
The following configuration options are available in `self_compiler_config.json`:

```json
{
  "recursion": {
    "max_depth": 10,
    "continuous_mode": {
      "default_pause_seconds": 60,
      "max_continuous_cycles": 1000,
      "save_state_interval": 1
    }
  }
}
```

### Session Persistence Settings
```json
{
  "persistence": {
    "sessions_directory": "sessions",
    "auto_save": true,
    "save_interval_cycles": 1,
    "retention_days": 30
  }
}
```

## Troubleshooting

### Common Issues

1. **Stress Test Not Available**
   ```
   Error: Watchtower stress test module not available
   ```
   **Solution**: Ensure `watchtower_stress_test.py` is in the SIMP directory

2. **Cannot Resume Session**
   ```
   Error: Session has status 'success' and cannot be resumed
   ```
   **Solution**: Only sessions with status `unknown`, `interrupted`, or `partial_failure` can be resumed

3. **Continuous Mode Not Pausing**
   **Solution**: Check that `--pause` value is greater than 0

4. **Session Not Found**
   ```
   Session not found or cannot be loaded
   ```
   **Solution**: Verify session ID with `sessions list` command

### Performance Tips

1. **For Long-running Sessions**:
   - Use `--pause 300` (5 minutes) to reduce system load
   - Enable auto-approve with `--auto-approve` for unattended operation
   - Monitor with `monitor` command in separate terminal

2. **For Large Codebases**:
   - Limit target directories with `--directories`
   - Increase pause time between cycles
   - Use session persistence to resume after interruptions

3. **For Production Use**:
   - Always save results with `--output`
   - Generate JSON reports for analysis
   - Use stress tests to validate system capacity

## API Reference

### New CLI Methods

#### `SelfCompilerCLI.run_session()`
```python
def run_session(
    goal: str,
    max_cycles: int = 1,
    target_directories: Optional[List[str]] = None,
    operator_approval: bool = False,
    continuous: bool = False,
    pause_between_cycles: int = 60
) -> Dict[str, Any]
```

#### `SelfCompilerCLI.run_stress_test()`
```python
def run_stress_test(
    agents: Optional[List[str]] = None,
    concurrent_workers: int = 5,
    duration_seconds: int = 30,
    intent_types: Optional[List[str]] = None
) -> Dict[str, Any]
```

#### `SelfCompilerCLI.save_session_state()`
```python
def save_session_state(
    session_id: str,
    session_data: Dict[str, Any]
) -> str
```

#### `SelfCompilerCLI.generate_enhanced_report()`
```python
def generate_enhanced_report(
    session_id: str,
    output_format: str = "text"
) -> Dict[str, Any]
```

#### `SelfCompilerCLI.show_real_time_progress()`
```python
def show_real_time_progress(
    session_id: str,
    refresh_interval: int = 2
) -> None
```

## Migration Notes

### From Phase 1 to Phase 2

1. **Backward Compatibility**: All Phase 1 features remain functional
2. **New Directories**: `sessions/` directory created automatically
3. **Configuration**: Existing config files work without modification
4. **CLI Changes**: New commands added, existing commands unchanged

### File Structure Changes
```
self_compiler_v2/
├── sessions/           # New: Session persistence directory
├── stress_results/     # New: Stress test results (if run)
├── config/
├── docs/
├── src/
├── staging/
└── traces/
```

## Future Enhancements

Planned for future phases:
1. **Web Dashboard**: Browser-based monitoring interface
2. **Alerting System**: Email/Slack notifications for critical events
3. **Batch Processing**: Run multiple sessions in parallel
4. **Advanced Analytics**: Machine learning insights from session data
5. **Plugin System**: Extensible reporting and monitoring plugins

## Support

For issues or questions:
1. Check the `docs/` directory for additional documentation
2. Review session logs in `sessions/` directory
3. Examine trace files in `traces/` directory
4. Generate enhanced reports for detailed analysis

---

*Last Updated: April 2026*  
*Version: Phase 2.0*  
*Compatibility: Sovereign Self Compiler v2*