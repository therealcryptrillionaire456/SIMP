# Agent Runner (how to actually spawn the 10 lanes)

This kit is runner-agnostic. Any framework works as long as each lane obeys:

1. Loads its role card: `contracts/agents/Ax_*.md` + `contracts/agents/_preamble.md`.
2. Loads the contracts: charter, ownership, cycle, decision, status-board schema.
3. Uses `harness/cycle_runner.py::Cycle` for every mutation.
4. Writes to `state/cycle_journal.ndjson` (automatic via `Cycle`).
5. Does not exceed its ownership per `contracts/ownership_matrix.md`.

## Reference: one lane as a persistent loop (pseudocode)

```python
# run_lane.py  (per-agent process)
import time
from harness.cycle_runner import Cycle
from pathlib import Path

LANE = os.environ["LANE"]  # "A2" etc.

# Your LLM runner of choice: Claude, OpenAI, local — does not matter.
agent = YourRunner(
    system_prompt=Path(f"contracts/agents/{LANE}_*.md").read_text() +
                  Path("contracts/agents/_preamble.md").read_text(),
    tools=[read_file, write_file, shell, git_diff, python_exec],
)

while True:
    with Cycle(lane=LANE) as cyc:
        board = read_status_board()
        queue = read_queue(lane=LANE)
        a9 = read_latest_truth_report()
        plan = agent.ask(
            f"Run one cycle. Status: {board}. Queue: {queue}. "
            f"A9 truth: {a9}. Follow contracts/cycle_contract.md strictly."
        )
        # plan is expected to produce: observed, decided, touches, revert_cmd,
        # execute_commands, verify_command. The runner validates the plan's
        # touches against ownership via cyc.gate_check before execution.
        cyc.observe(plan.observed)
        cyc.decide(plan.decided)
        ok, why = cyc.gate_check(touches=plan.touches,
                                 needs_a5=plan.needs_a5, needs_a0=plan.needs_a0)
        if not ok:
            cyc.block(why)
            continue
        execute(plan.execute_commands)
        cyc.execute(touches=plan.touches, revert_cmd=plan.revert_cmd)
        v = run(plan.verify_command)
        cyc.verify("green" if v.ok else "red")
        if not v.ok:
            rollback(plan.revert_cmd)
            cyc.open_sev(f"verif_regress_{LANE}_{int(time.time())}")
        cyc.note(plan.note)
        cyc.enqueue_next(plan.next_candidates)
    time.sleep(os.environ.get("SIMP_CYCLE_S", "1800"))  # 30 min
```

## Concurrency model

- 10 processes, one per lane. Stable for the full week.
- A0 supervisor runs separately and mutates queue only.
- A9 runs on a slightly offset schedule (e.g. +5 min) so it audits fresh journal entries.
- Burn-in (Day 7) shortens interval to 5 min; everyone else stays at 30 min.

## Failure modes the runner must handle

- LLM timeout → fall through to `cyc.block("llm_timeout")`.
- Agent proposes write outside ownership → gate_check refuses; journal as `owner_conflict`.
- Agent proposes no revert command → runner substitutes `cyc.block("no_revert")`.
- Kill switch appears mid-cycle → finish current write, call `cyc.halt("kill observed")`, exit lane loop.

## Human control points

- Kill switch: `touch state/KILL` halts every lane next cycle.
- Mode: edit `state/mode.json` (or let A0 do it via supervisor escalations).
- Budget: edit `contracts/live_limits.json` (humans only).
- Stop a single lane: kill its process. A0 will note the absence but not respawn without human.
