# Ownership Matrix

Write = may mutate. Read = may inspect and report. Propose = may open a change but another lane must approve.

| Subsystem / Path                                  | Owner (write) | Read | Propose-only |
|---------------------------------------------------|---------------|------|--------------|
| `startall.sh`, `scripts/start_*.sh`               | A1            | all  | A7           |
| `simp/server/broker.py`                           | A1            | all  | A3, A4       |
| `simp/server/http_server.py`                      | A4            | all  | A1, A5       |
| `simp/server/agent_registry.py`                   | A4            | all  | A1           |
| `simp/task_ledger.py`                             | A3            | all  | A2           |
| `simp/models/canonical_intent.py`                 | A4            | all  | A3           |
| `simp/routing/builder_pool.py`                    | A3            | all  | A4           |
| `simp/routing/signal_router.py`                   | A3            | all  | A2           |
| `simp/orchestration/orchestration_loop.py`        | A1            | all  | A3           |
| `simp/organs/quantum*/**`                         | A3            | all  | A2           |
| `simp/organs/gate4/**` (execution)                | A2            | all  | A5           |
| `quantum_signal_bridge*`                          | A2            | all  | A3           |
| `gate4_inbox_consumer*`                           | A2            | all  | A1           |
| `scripts/verify_revenue_path.py`                  | A2 + A9*      | all  | —            |
| `scripts/runtime_snapshot.py`                     | A6            | all  | A1           |
| Policy gate, kill switch, budget caps             | A5            | all  | **no one**   |
| `.env*`, secrets, key stores                      | A5            | —    | **no one**   |
| A2A endpoints, agent cards, events                | A4            | all  | A5           |
| `simp/projectx/**`                                | A4            | all  | A1           |
| `dashboard/**`                                    | A6            | all  | A8           |
| `docs/**`, Obsidian vault projection, AGENTS.md   | A8            | all  | owning lane  |
| Repo layout, archive moves, tracked boundaries    | A7            | all  | all          |
| Tests under `tests/` touching owned subsystem     | owner         | all  | —            |
| `state/status_board.json`                         | A6 writes; all append events via harness | all | — |
| `state/decision_journal.ndjson`                   | A3 writes; A2 appends fills              | all | — |
| `state/incidents/*.md`                            | A9 writes; any agent opens               | all | — |

*A9 may write to `verify_revenue_path.py` only to add assertions, never to relax them. Any relaxation requires commander approval and is journaled as a policy event.

## Conflict rule
If two lanes need to mutate the same file in the same cycle, A0 serializes them. Simultaneous writes are a Sev3 automatically.

## Live-trading permission rule
No agent except A5 may edit files matching: `policy_guard*`, `kill_switch*`, `budget*`, `risk_caps*`, `live_mode*`. A5 cannot unilaterally widen these either — widening is a human-in-loop action.
