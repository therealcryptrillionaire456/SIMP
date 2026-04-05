# Task Ledger

## Status
completed

## Goal
Implement a persistent task tracking system with JSONL storage, claim/lock semantics, priority queuing, and failure classification.

## Current State
Fully implemented and integrated with the broker. Tasks are persisted to JSONL, support claim/lock semantics to prevent duplicate processing, and failures are classified using the failure taxonomy.

## Key Decisions
- JSONL chosen for append-only persistence (simple, reliable, git-friendly diffs)
- Claim/lock semantics prevent two agents from working the same task
- Priority levels: critical, high, normal, low
- Failure taxonomy integrated: rate_limited, agent_unavailable, timeout, execution_failed, schema_invalid, policy_denied
- Status flow: queued -> claimed -> in_progress -> completed/failed/deferred_by_capacity

## Open Questions
- (none)

## Code Locations
- `simp/task_ledger.py` — Core TaskLedger class with JSONL persistence
- `simp/models/failure_taxonomy.py` — FailureHandler and FailureClass definitions
- `data/task_ledger.jsonl` — Persistent task data (gitignored)

## Dependencies
- File system for JSONL storage
- `simp/models/failure_taxonomy.py` for failure classification

## History
- 2025-03-25 — Task created
- 2025-03-26 — Implemented core TaskLedger with JSONL persistence
- 2025-03-27 — Added claim/lock semantics
- 2025-03-28 — Integrated failure taxonomy
- 2025-03-29 — Added priority queuing and status counts
- 2025-03-30 — Completed — fully integrated with broker
