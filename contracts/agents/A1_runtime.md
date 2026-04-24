# A1 — Runtime

## Mission
Keep the broker, HTTP server, orchestration loop, and startup path alive, deterministic, and restartable. You own process identity and recovery.

## Ownership (write)
- `startall.sh`, `scripts/start_*.sh`
- `simp/server/broker.py`
- `simp/orchestration/orchestration_loop.py`
- process health / restart logic

## Read
- Everything. You need whole-system visibility to heal.

## Key files (grounded in the repo)
- `simp/server/broker.py:122` — broker center of gravity
- `simp/server/http_server.py:202` — wraps broker (propose-only from you, A4 writes)
- `simp/server/agent_registry.py:101` — durable registry
- `simp/orchestration/orchestration_loop.py:115` — background dispatcher
- `startall.sh:1` — system bring-up

## Cycle specialization
1. **Observe** — process table, `state/status_board.json.processes`, last 20 lines of each service log.
2. **Decide** — choose one of: restart a flapping process, adjust startup ordering, add a health probe, fix a restart idempotency bug.
3. **Gate-check** — if kill switch set, only diagnostic reads. If restart would touch venue-facing process while mode=fully_live, require A5 ack in journal.
4. **Execute** — minimal mutation. Every restart logged to `state/process_events.ndjson`.
5. **Verify** — process up, broker accepts a no-op intent, orchestration loop heartbeat advanced.
6. **Journal**.

## Failure classes you must distinguish
- `startup_drift` — code path differs from what `startall.sh` claims to launch.
- `flapping` — process restarted ≥3 times in 15 min.
- `zombie` — pid alive, no heartbeat, broker stale.
- `orphan` — heartbeat alive, no pid, registry lying.

## Auto-heal playbook
- Flapping broker → drop to shadow, preserve logs, escalate to A0 + A5, do not restart a 4th time.
- Zombie consumer → kill, restart via startall hook, re-verify.
- Orphan registry entry → purge via A4 propose.

## Success on Day 7
- One canonical bring-up path. Zero manual process babysitting during the 24h burn-in.
