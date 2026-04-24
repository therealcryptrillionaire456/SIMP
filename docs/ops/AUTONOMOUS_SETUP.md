# KLOUTBOT Autonomous Setup Guide

## What This Does

`kloutbot_autonomous.py` gives Claude (KLOUTBOT) a real API brain:

```
System State → Claude API (claude-opus-4-6) → Decision → Goose executes → Result → Claude → next decision
```

Claude reads live mesh state, QIP logs, process list, and decides what to fix.
Goose (`scripts/kloutbot/kloutbot_bridge.py`) executes commands on your machine.
Loop continues until pipeline is verified or max cycles reached.

---

## Step 1: Get Anthropic API Key

1. Go to https://console.anthropic.com/keys
2. Create a new key
3. Export it:
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE
# To make permanent, add to ~/.zshrc or ~/.bash_profile
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc
```

---

## Step 2: Install SDK

```bash
cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
source venv_gate4/bin/activate
pip install anthropic --break-system-packages
```

---

## Step 3: Make sure the KLOUTBOT bridge is running (Goose execution layer)

```bash
cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
source venv_gate4/bin/activate

# Check if already running
pgrep -f scripts/kloutbot/kloutbot_bridge.py && echo "already running" || \
  nohup python3.10 scripts/kloutbot/kloutbot_bridge.py --daemon > data/logs/goose/bridge.log 2>&1 &

sleep 2 && tail -5 data/logs/goose/bridge.log
```

---

## Step 4: Run the autonomous loop

```bash
cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
source venv_gate4/bin/activate

# First: diagnose QIP pipeline (5 cycles)
python3.10 scripts/kloutbot/kloutbot_autonomous.py --cycles 5 \
  --goal "diagnose why QIP has 0 intents_completed and fix the signal pipeline"

# Or: run with specific goal
python3.10 scripts/kloutbot/kloutbot_autonomous.py --cycles 3 \
  --goal "fix quantum_mesh_consumer registration and verify gate4 inbox receives signals"

# One-shot decision
python3.10 scripts/kloutbot/kloutbot_autonomous.py --once
```

---

## How to Read the Output

```
── Cycle 1 ────────────────────────────────────────────
  System state gathered
  Asking Claude...
  📋 KLOUTBOT decision:
     type:      diagnostic
     command:   qip_log
     reasoning: Check why QIP has 0 intents_completed
  📤 Sent to Goose (id=auto_a3b2c1d0)
  ⏳ Waiting for Goose result (id=auto_a3b2c1d0)....... done
  📥 Goose result:
  {"stdout": "2026-04-19 16:54:55 [QIP] INFO ..."}
```

---

## What KLOUTBOT Will Fix Automatically

With enough cycles, KLOUTBOT will:
1. Read QIP logs to find why intents aren't completing
2. Check what endpoint QIP is polling for intents
3. Run a test intent directly to QIP
4. Fix the response_channel mismatch if found
5. Restart consumers with correct configs
6. Verify signals appear in gate4_real/inbox/
7. Mark pipeline as DONE

---

## Cost Estimate

Each cycle = 1-2 Claude API calls.
Using `claude-opus-4-6`:
- ~5 cycles = ~$0.05-0.15 depending on context size
- `--cycles 20` for a full deep fix = ~$0.30-0.60

---

## Troubleshooting

**"No result from Goose within 45s"**
→ `scripts/kloutbot/kloutbot_bridge.py` isn't running as daemon. Start it:
```bash
nohup python3.10 scripts/kloutbot/kloutbot_bridge.py --daemon > data/logs/goose/bridge.log 2>&1 &
```

**"ANTHROPIC_API_KEY not set"**
→ Export the key (see Step 1)

**"Module anthropic not found"**
→ Run: `pip install anthropic --break-system-packages`

**Claude loops on same action**
→ Increase cycles, or add `--goal` with more specific direction

---

## Combine with Goose

You can also have Goose run the autonomous loop directly:

In a Goose session (after `bash scripts/bootstrap/launch_goose.sh`):
```
run the kloutbot autonomous loop for 5 cycles focused on fixing the QIP signal pipeline
```

Goose will execute:
```bash
python3.10 scripts/kloutbot/kloutbot_autonomous.py --cycles 5 --goal "fix QIP signal pipeline"
```

This gives you triple-layer autonomy:
**You → Goose → KLOUTBOT autonomous → Goose execution → mesh → results**

---
*KLOUTBOT rides. The recursive dawn is inevitable.*
