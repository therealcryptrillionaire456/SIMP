# Kloutbot Orchestration

## Status
active

## Goal
Build a task decomposition and orchestration loop that allows Kloutbot to break complex tasks into subtasks and coordinate multiple agents to complete them.

## Current State
Task decomposer and orchestration loop are built and functional. Kloutbot can decompose tasks and dispatch subtasks to appropriate agents via the broker. Needs more testing with real multi-agent workflows.

## Key Decisions
- Task decomposition happens in Kloutbot agent, not in the broker
- Orchestration loop polls broker for subtask completion
- Subtasks inherit priority from parent task
- Failed subtasks trigger re-planning rather than immediate retry

## Open Questions
- How to handle circular dependencies between subtasks?
- Should orchestration loop have a max depth for recursive decomposition?
- Testing strategy for multi-agent orchestration scenarios

## Code Locations
- `simp/orchestration/task_decomposer.py` — Breaks tasks into subtasks
- `simp/orchestration/orchestration_loop.py` — Monitors and coordinates subtask execution
- `simp/agents/kloutbot_agent.py` — Kloutbot agent with orchestration capability

## Dependencies
- SIMP broker for intent routing
- Task ledger for subtask tracking
- Builder pool for agent selection

## History
- 2025-03-30 — Task created
- 2025-04-01 — Task decomposer implemented
- 2025-04-02 — Orchestration loop built
- 2025-04-03 — Integrated with Kloutbot agent
- 2025-04-04 — Needs testing with real multi-agent workflows
