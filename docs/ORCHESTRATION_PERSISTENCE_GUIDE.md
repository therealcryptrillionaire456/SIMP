# OrchestrationManager Persistence Guide

## Overview

The OrchestrationManager now supports full plan state persistence across process restarts. This guide covers the persistence architecture, configuration, and recovery procedures.

## Architecture

### Files
- `data/orchestration_plans.jsonl` - Plan state persistence (new)
- `data/orchestration_log.jsonl` - Event logging (existing)

### Data Flow
1. **Plan Creation**: `create_plan()` → `_save_plan()` → Append to JSONL
2. **Plan Execution**: State changes → `_update_plan_in_storage()` → Rewrite entire file
3. **Manager Initialization**: `_load_plans()` → Reconstruct all plans from JSONL

## Configuration

### OrchestrationManagerConfig
```python
@dataclass
class OrchestrationManagerConfig:
    log_path: Path = Path("data/orchestration_log.jsonl")
    plans_path: Path = Path("data/orchestration_plans.jsonl")
    max_plans: int = 1000
    persistence_enabled: bool = True  # Disable for tests
```

### Usage Examples

#### Default Configuration (Production)
```python
manager = OrchestrationManager()  # Uses default config with persistence
```

#### Custom Configuration
```python
config = OrchestrationManagerConfig(
    plans_path=Path("/custom/path/plans.jsonl"),
    persistence_enabled=True
)
manager = OrchestrationManager(config=config)
```

#### Disable Persistence (Testing)
```python
config = OrchestrationManagerConfig(persistence_enabled=False)
manager = OrchestrationManager(config=config)
```

## Plan Serialization

### To Dictionary
```python
plan = manager.create_plan("Test", "Description", steps=[...])
plan_dict = plan.to_dict()
# Returns: {
#   "plan_id": "...",
#   "name": "Test",
#   "description": "Description",
#   "steps": [...],
#   "status": "pending",
#   "created_at": "...",
#   "completed_at": "",
#   "error": ""
# }
```

### From Dictionary
```python
plan_data = {...}  # Serialized plan
plan = OrchestrationPlan.from_dict(plan_data)
```

## Recovery Procedures

### Manual Plan Recovery
```python
import json
from simp.orchestration.orchestration_manager import OrchestrationPlan

def recover_plans(file_path: str):
    """Recover plans from JSONL file."""
    plans = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                plan_data = json.loads(line)
                plan = OrchestrationPlan.from_dict(plan_data)
                plans.append(plan)
            except json.JSONDecodeError:
                print(f"Skipping corrupt line: {line[:50]}...")
    return plans

# Usage
plans = recover_plans("data/orchestration_plans.jsonl")
print(f"Recovered {len(plans)} plans")
for plan in plans:
    print(f"  - {plan.name} ({plan.status})")
```

### Plan State Analysis
```bash
# Count plans by status
cat data/orchestration_plans.jsonl | jq -r '.status' | sort | uniq -c

# List all plan names
cat data/orchestration_plans.jsonl | jq -r '.name'

# Find failed plans
cat data/orchestration_plans.jsonl | jq -c 'select(.status == "failed")'

# Count steps per plan
cat data/orchestration_plans.jsonl | jq -r '.steps | length' | sort -n | uniq -c
```

### File Corruption Recovery
```bash
# Validate JSONL file
cat data/orchestration_plans.jsonl | jq . > /dev/null

# If corrupted, recover valid lines
cat data/orchestration_plans.jsonl | while read line; do
    if echo "$line" | jq . > /dev/null 2>&1; then
        echo "$line"
    else
        echo "Skipping corrupt line: ${line:0:50}..." >&2
    fi
done > data/orchestration_plans_recovered.jsonl
```

## Migration from Legacy System

### Before Session 3
- Only event logging (`orchestration_log.jsonl`)
- Plan state lost on restart
- No plan persistence

### After Session 3
- Full plan state persistence (`orchestration_plans.jsonl`)
- Plans survive process restarts
- Event logging continues separately

### Migration Script
```python
import json
from datetime import datetime, timezone
from pathlib import Path

def migrate_legacy_plans():
    """
    Migrate from event log to plan persistence.
    This is a conceptual example - actual migration depends on legacy data.
    """
    log_path = Path("data/orchestration_log.jsonl")
    plans_path = Path("data/orchestration_plans.jsonl")
    
    if not log_path.exists():
        print("No legacy log file found")
        return
    
    # Parse events to reconstruct plans
    plans_by_id = {}
    
    with open(log_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                event = json.loads(line)
                plan_id = event.get("plan_id")
                if not plan_id:
                    continue
                
                # Reconstruct plan from events
                # This is simplified - actual reconstruction would be more complex
                if plan_id not in plans_by_id:
                    plans_by_id[plan_id] = {
                        "plan_id": plan_id,
                        "name": event.get("plan_name", "Legacy Plan"),
                        "description": "Migrated from legacy log",
                        "steps": [],
                        "status": "completed",  # Assume completed
                        "created_at": event.get("timestamp"),
                        "completed_at": event.get("timestamp"),
                        "error": ""
                    }
            except json.JSONDecodeError:
                continue
    
    # Save reconstructed plans
    with open(plans_path, 'w') as f:
        for plan_data in plans_by_id.values():
            f.write(json.dumps(plan_data) + "\n")
    
    print(f"Migrated {len(plans_by_id)} plans from legacy log")

if __name__ == "__main__":
    migrate_legacy_plans()
```

## Performance Considerations

### File Size Management
- Default limit: 1000 plans
- File rotation at 10MB
- Append-only for new plans, rewrite for updates

### Memory Usage
- All plans loaded into memory on initialization
- Consider disabling persistence for high-volume systems
- Use `persistence_enabled=False` for memory-constrained environments

### Concurrency
- Thread-safe file operations using locking
- Safe for multiple threads reading/writing plans
- Rewrite entire file on updates (simple but inefficient for large files)

## Testing

### Unit Tests
```python
# tests/test_orchestration_persistence.py
# Comprehensive persistence tests

# tests/test_orchestration.py
# Updated to disable persistence for isolation
```

### Test Fixtures
```python
# tests/conftest.py
@pytest.fixture
def isolated_orchestration_manager():
    """Create manager with temporary files for test isolation."""
    # Uses temporary files to prevent test interference
```

## Troubleshooting

### Plans Not Persisting
1. Check `persistence_enabled=True` in config
2. Verify file permissions on `data/orchestration_plans.jsonl`
3. Check disk space
4. Review logs for write errors

### High Disk Usage
1. Implement file rotation for > 10MB files
2. Archive completed plans
3. Consider disabling persistence for transient plans

### Performance Issues
1. Reduce `max_plans` limit
2. Implement more efficient update strategy
3. Consider database backend for high-volume systems

## API Reference

### OrchestrationManager
- `__init__(config: Optional[OrchestrationManagerConfig] = None)`
- `create_plan()` - Saves plan to disk
- `execute_plan()` - Updates plan state on disk
- `_save_plan()` - Internal: Append plan to JSONL
- `_update_plan_in_storage()` - Internal: Rewrite all plans
- `_load_plans()` - Internal: Load plans on initialization

### OrchestrationPlan
- `to_dict()` - Serialize plan to dictionary
- `from_dict()` - Class method to deserialize
- All fields preserved: steps, status, timestamps, errors

### OrchestrationStep  
- `to_dict()` - Serialize step to dictionary
- `from_dict()` - Class method to deserialize
- Includes: status, result, error, timestamps