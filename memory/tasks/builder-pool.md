# Routing Policy & Builder Pool

## Status
completed

## Goal
Implement intelligent task routing with a builder pool that assigns tasks to agents based on capability, capacity, and fallback rules.

## Current State
Fully implemented. The builder pool reads from a static routing policy JSON and dynamically tracks agent capacity. Supports primary/secondary/support pool hierarchy and task-type-specific routing.

## Key Decisions
- Static routing policy in JSON for easy configuration
- Three-tier pool: primary (claude_cowork), secondary (perplexity_research), support (gemma4_local, kloutbot)
- Task-type routing maps each task type to ordered list of capable agents
- Fallback rules per failure class: next_in_pool, retry_then_fallback, fail_immediately, escalate
- Capacity tracking is dynamic — agents report available/busy/offline status
- Unknown agents assumed available (graceful on first contact)

## Open Questions
- (none)

## Code Locations
- `simp/routing/builder_pool.py` — BuilderPool class with capacity tracking
- `simp/routing/routing_policy.json` — Static routing configuration
- `simp/models/failure_taxonomy.py` — FailureHandler with fallback logic

## Dependencies
- Routing policy JSON file
- Failure taxonomy for fallback decisions

## History
- 2025-03-26 — Task created
- 2025-03-27 — Designed routing policy schema
- 2025-03-28 — Implemented BuilderPool with task-type routing
- 2025-03-29 — Added capacity tracking and fallback rules
- 2025-03-30 — Integrated with broker for automatic fallback on delivery failure
- 2025-03-31 — Completed — all routing and fallback paths working
