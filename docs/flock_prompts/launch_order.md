# SIMP Flock Launch Order

## Standard Launch Sequence
Use this order every time to ensure proper system bring-up:

### Step 1: Start tmux session
```bash
./scripts/start_mother_goose_tmux.sh
tmux attach -t mothergoose
```

### Step 2: Start infrastructure (in control window, pane 1)
```bash
# Start broker
./bin/start_broker.sh

# Wait for broker to be ready (check health endpoint)
sleep 5
curl http://127.0.0.1:5555/health

# Start dashboard if needed (usually auto-starts with broker)
# Check if dashboard is running
curl http://127.0.0.1:8050/ 2>/dev/null || echo "Dashboard may need manual start"
```

### Step 3: Start Watchtower checks (in observability window)
```bash
# Pane 0: Run health checks every 30 seconds
watch -n 30 ./scripts/watchtower.sh

# Pane 1: Tail broker logs
if [ -f "$HOME/bullbear/logs/simp_broker.log" ]; then
    tail -f "$HOME/bullbear/logs/simp_broker.log"
else
    echo "No broker log found. Broker may not be running."
fi
```

### Step 4: Launch Mother Goose
In control window, pane 0, paste the Mother Goose prompt:
```text
You are Mother Goose, the orchestrator for today's SIMP flock.

Mission: Run the day as a controlled flight operation...

[Full prompt from docs/flock_prompts/mother_goose_prompt.md]
```

### Step 5: Launch SIMP Goose
In geese window, pane 0, paste the SIMP Goose prompt:
```text
You are SIMP Goose operating inside the SIMP repo.

Charter: Implement bounded, low-risk changes...

[Full prompt from docs/flock_prompts/simp_goose_prompt.md]
```

### Step 6: Launch Stray Goose
In geese window, pane 1, paste the Stray Goose prompt:
```text
You are Stray Goose, the planner and systems cartographer.

Charter: Read and synthesize the system...

[Full prompt from docs/flock_prompts/stray_goose_prompt.md]
```

## Why This Order Matters:
1. **tmux session first**: Provides stable container for all processes
2. **proxy and broker second**: Infrastructure must be up before agents
3. **Watchtower third**: Confirms runway is clear before launching geese
4. **Mother Goose fourth**: Assigns work only after system is actually up
5. **SIMP Goose fifth**: Waits for specific implementation tasks
6. **Stray Goose sixth**: Provides planning support as needed

## Quick Start Commands:
```bash
# One-command launch (run from SIMP repo root)
./scripts/start_mother_goose_tmux.sh && tmux attach -t mothergoose

# Then in tmux panes:
# Control pane 1: ./bin/start_broker.sh
# Observability pane 0: watch -n 30 ./scripts/watchtower.sh
# Observability pane 1: tail -f ~/bullbear/logs/simp_broker.log
```

## Health Verification:
Before launching geese, verify:
1. Broker responds: `curl -s http://127.0.0.1:5555/health`
2. Dashboard responds: `curl -s http://127.0.0.1:8050/`
3. Watchtower script runs: `./scripts/watchtower.sh`

## Troubleshooting:
If broker fails to start:
1. Check logs: `tail -20 ~/bullbear/logs/simp_broker.log`
2. Check port conflicts: `lsof -i :5555`
3. Kill old process: `pkill -f "python.*broker"`

If tmux session already exists:
```bash
tmux attach -t mothergoose
# Or kill and recreate:
tmux kill-session -t mothergoose
./scripts/start_mother_goose_tmux.sh
```

## Daily Flow:
1. Start tmux session
2. Start broker + dashboard
3. Start Watchtower monitoring
4. Launch Mother Goose with mission board
5. Mother Goose assigns tasks to SIMP Goose and Stray Goose
6. Run maintenance loop (30-60 minute check-ins)
7. End with landing protocol