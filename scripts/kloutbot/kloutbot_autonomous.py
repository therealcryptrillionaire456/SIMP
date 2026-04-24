#!/usr/bin/env python3.10
"""
kloutbot_autonomous.py  v1.0
Autonomous KLOUTBOT loop — Claude as strategic brain via Anthropic API.

This script is the "CPU" of KLOUTBOT:
  1. Reads current SIMP system state
  2. Sends it to Claude API with KLOUTBOT system prompt
  3. Claude decides what to do (bash, diagnostic, query, etc.)
  4. Posts instruction to kloutbot_instructions mesh channel
  5. Waits for Goose (kloutbot_bridge.py) to execute and return result
  6. Feeds result back to Claude for next decision
  7. Loops until Claude says DONE or max_cycles reached

Requirements:
    pip install anthropic --break-system-packages
    export ANTHROPIC_API_KEY=sk-ant-...

Usage:
    # One-shot decision
    python3.10 kloutbot_autonomous.py --once

    # Full autonomous loop (default: 5 cycles)
    python3.10 kloutbot_autonomous.py --cycles 5

    # Continuous until DONE (use with care — costs API credits)
    python3.10 kloutbot_autonomous.py --continuous

    # With custom goal
    python3.10 kloutbot_autonomous.py --goal "diagnose why QIP has 0 intents completed"
"""

import os, sys, json, time, uuid, argparse
from datetime import datetime, timezone
from pathlib import Path
import requests

# ── Config ────────────────────────────────────────────────────────────────────
BROKER_URL   = os.environ.get("SIMP_BROKER", "http://127.0.0.1:5555")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SIMP_DIR     = Path(os.environ.get("SIMP_DIR",
    "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"))
AGENT_ID     = "kloutbot_autonomous"
CHANNEL_OUT  = "kloutbot_instructions"
CHANNEL_IN   = "kloutbot_results"
RESULT_WAIT  = 45  # seconds to wait for Goose to execute
MAX_RESULT_WAIT_POLLS = 15

KLOUTBOT_SYSTEM_PROMPT = """You are KLOUTBOT — the strategic brain of the SIMP multi-agent trading system.

## Your Role
- You issue precise instructions to Goose (your execution layer) via the SIMP mesh
- Goose executes bash commands, python scripts, and diagnostics on your behalf
- You receive results back and decide next actions
- Your goal: get the quantum signal pipeline fully operational to generate trading revenue

## SIMP Architecture
- Broker: http://127.0.0.1:5555
- SIMP_DIR: /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp
- Goose executes from SIMP_DIR with venv_gate4 active

## Known Issues (priority order)
1. [P1] quantum_mesh_consumer: registration 400 (simp_versions missing)
2. [P1] QIP: 272 heartbeats but 0 intents_completed — pipeline broken
3. [P1] quantumarb_mesh_consumer: 405 on POST /mesh/poll (should be GET)
4. [P2] QuantumModeEngine stub mode (path issue)
5. [P3] projectx_native heartbeat 404

## Revenue Pipeline (currently broken at QIP → gate4)
QIP → quantum_mesh_consumer → gate4_real/inbox/ → gate4_bot → live trades

## Instruction Format
You MUST respond with ONLY a JSON object — no prose, no markdown fences:

{
  "command_type": "bash" | "python" | "diagnostic" | "status" | "file_write",
  "command": "the command or code to run",
  "reasoning": "why you're doing this (1 sentence)",
  "next_expected": "what you expect to see in results",
  "done": false
}

Set "done": true when the pipeline is verified working end-to-end.

## Diagnostic Presets (use command_type: diagnostic)
Available presets for command field:
  broker_status, mesh_agents, mesh_status, qip_log,
  signals, processes, trust_scores, gate4_inbox, channel_list

## Rules
- Always start with diagnostics before making changes
- One action per turn — no compound commands that mask failures
- If a command fails, diagnose before retrying
- Prefer targeted fixes over restart-everything
- Track what you've already tried (will be in conversation history)
"""

# ── Anthropic API ─────────────────────────────────────────────────────────────
def call_claude(messages, goal=""):
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set. Export it: export ANTHROPIC_API_KEY=sk-ant-...")

    try:
        import anthropic
    except ImportError:
        print("Installing anthropic SDK...")
        os.system("pip install anthropic --break-system-packages -q")
        import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    system = KLOUTBOT_SYSTEM_PROMPT
    if goal:
        system += f"\n\n## Current Goal\n{goal}"

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text.strip()

# ── SIMP mesh ─────────────────────────────────────────────────────────────────
def _get(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code, (r.json() if r.text else {})
    except Exception as e:
        return 0, str(e)

def _post(url, payload, timeout=10):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.status_code, (r.json() if r.text else {})
    except Exception as e:
        return 0, str(e)

def register():
    payload = {
        "agent_id": AGENT_ID, "agent_type": "orchestrator",
        "simp_versions": ["1.0"], "endpoint": "mesh://local",
        "capabilities": ["autonomous_strategy"], "file_based": False,
    }
    _post(f"{BROKER_URL}/agents/register", payload)

def get_system_state():
    """Snapshot current system state for Claude's context."""
    _, agents = _get(f"{BROKER_URL}/agents")
    _, health = _get(f"{BROKER_URL}/health")
    _, channels = _get(f"{BROKER_URL}/channels")

    # Process list
    import subprocess
    procs = subprocess.run(
        "ps aux | grep -E 'quantum|kloutbot|gate4' | grep -v grep | awk '{print $11}' | sort -u",
        shell=True, capture_output=True, text=True, cwd=str(SIMP_DIR)
    ).stdout.strip()

    # Signal counts
    sigs = len(list((SIMP_DIR / "data" / "signals").glob("*.json"))) if (SIMP_DIR / "data" / "signals").exists() else 0
    g4 = len(list((SIMP_DIR / "data" / "gate4_real" / "inbox").glob("*.json"))) if (SIMP_DIR / "data" / "gate4_real" / "inbox").exists() else 0

    # Format agent summary
    agent_summary = []
    if isinstance(agents, dict):
        agent_list = list(agents.get("agents", agents).values()) if "agents" in agents else list(agents.values())
    elif isinstance(agents, list):
        agent_list = agents
    else:
        agent_list = []

    for a in agent_list:
        if isinstance(a, dict):
            aid = a.get("agent_id", "?")
            completed = a.get("intents_completed", 0)
            received = a.get("intents_received", 0)
            hb = a.get("heartbeat_count", 0)
            status = a.get("status", "?")
            agent_summary.append(f"  {aid}: status={status} heartbeats={hb} intents_received={received} intents_completed={completed}")

    return f"""## System State at {datetime.now().strftime('%H:%M:%S')}

### Broker: {health.get('status', 'unknown') if isinstance(health, dict) else health}

### Agents:
{chr(10).join(agent_summary) or '  (none)'}

### Running processes:
{procs or '  (none detected)'}

### Signal pipeline:
  data/signals/: {sigs} files
  gate4_real/inbox/: {g4} files
"""

def send_instruction(cmd_type, command, instruction_id=None):
    instruction_id = instruction_id or f"auto_{uuid.uuid4().hex[:8]}"
    msg = {
        "channel": CHANNEL_OUT,
        "sender": AGENT_ID,
        "message_type": "kloutbot_instruction",
        "payload": {
            "instruction_id": instruction_id,
            "command_type": cmd_type,
            "command": command,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "kloutbot_autonomous",
        }
    }
    status, resp = _post(f"{BROKER_URL}/mesh/send", msg)
    return instruction_id if status in (200, 201) else None

def wait_for_result(instruction_id, timeout=RESULT_WAIT):
    print(f"  ⏳ Waiting for Goose result (id={instruction_id})...", end="", flush=True)
    deadline = time.time() + timeout
    polls = 0
    while time.time() < deadline and polls < MAX_RESULT_WAIT_POLLS:
        time.sleep(timeout / MAX_RESULT_WAIT_POLLS)
        status, data = _get(f"{BROKER_URL}/mesh/poll?agent_id={AGENT_ID}&channel={CHANNEL_IN}&max_messages=10")
        if status == 200:
            messages = data if isinstance(data, list) else data.get("messages", [])
            for msg in messages:
                p = msg.get("payload", msg)
                if p.get("instruction_id") == instruction_id:
                    print(" done")
                    return p
        polls += 1
        print(".", end="", flush=True)
    print(" timeout")
    return None

# ── Main loop ─────────────────────────────────────────────────────────────────
def autonomous_loop(goal="", max_cycles=5, continuous=False):
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY not set.")
        print("   export ANTHROPIC_API_KEY=sk-ant-api03-...")
        print("   Get your key at: https://console.anthropic.com/keys")
        sys.exit(1)

    register()
    print(f"\n{'═'*55}")
    print(f"  KLOUTBOT AUTONOMOUS LOOP")
    print(f"  Goal: {goal or 'get revenue pipeline operational'}")
    print(f"  Max cycles: {'∞' if continuous else max_cycles}")
    print(f"{'═'*55}\n")

    conversation = []
    cycle = 0

    while continuous or cycle < max_cycles:
        cycle += 1
        print(f"\n── Cycle {cycle} {'─'*40}")

        # Build context for Claude
        state = get_system_state()
        print(f"  System state gathered")

        if not conversation:
            user_content = f"{state}\n\nBegin diagnosing and fixing. What's your first action?"
        else:
            user_content = f"{state}\n\nWhat's your next action?"

        conversation.append({"role": "user", "content": user_content})

        # Call Claude API
        print(f"  Asking Claude...")
        try:
            response_text = call_claude(conversation, goal=goal)
        except Exception as e:
            print(f"  ❌ Claude API error: {e}")
            break

        conversation.append({"role": "assistant", "content": response_text})

        # Parse Claude's instruction
        try:
            # Strip any accidental markdown
            clean = response_text.strip()
            if clean.startswith("```"):
                clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = "\n".join(clean.split("\n")[:-1])
            instruction = json.loads(clean)
        except json.JSONDecodeError:
            print(f"  ⚠️  Claude returned non-JSON. Response:")
            print(f"  {response_text[:300]}")
            # Try to extract JSON from response
            import re
            m = re.search(r'\{[^{}]*"command_type"[^{}]*\}', response_text, re.DOTALL)
            if m:
                try:
                    instruction = json.loads(m.group(0))
                except:
                    print("  ❌ Could not parse instruction — stopping")
                    break
            else:
                print("  ❌ No JSON found in response — stopping")
                break

        cmd_type = instruction.get("command_type", "bash")
        command  = instruction.get("command", "")
        reasoning = instruction.get("reasoning", "")
        done     = instruction.get("done", False)

        print(f"\n  📋 KLOUTBOT decision:")
        print(f"     type:      {cmd_type}")
        print(f"     command:   {command[:100]}{'...' if len(command) > 100 else ''}")
        print(f"     reasoning: {reasoning}")

        if done:
            print(f"\n  ✅ KLOUTBOT: Pipeline verified working — loop complete")
            break

        # Send to Goose
        instruction_id = send_instruction(cmd_type, command)
        if not instruction_id:
            print(f"  ❌ Failed to send instruction to mesh")
            conversation.append({"role": "user", "content": "ERROR: instruction failed to publish to mesh. Broker may be down."})
            continue

        print(f"  📤 Sent to Goose (id={instruction_id})")

        # Wait for result
        result = wait_for_result(instruction_id)
        if result:
            result_str = json.dumps(result.get("result", result), indent=2, default=str)
            print(f"\n  📥 Goose result:")
            print(f"  {result_str[:500]}{'...' if len(result_str) > 500 else ''}")
            conversation.append({
                "role": "user",
                "content": f"Goose executed the command. Result:\n```json\n{result_str[:2000]}\n```"
            })
        else:
            print(f"  ⚠️  No result from Goose within {RESULT_WAIT}s")
            print(f"  Make sure scripts/kloutbot/kloutbot_bridge.py is running:")
            print(f"  nohup python3.10 scripts/kloutbot/kloutbot_bridge.py --daemon > data/logs/goose/bridge.log 2>&1 &")
            conversation.append({
                "role": "user",
                "content": f"WARNING: Goose did not respond within {RESULT_WAIT}s. scripts/kloutbot/kloutbot_bridge.py may not be running as daemon."
            })

        time.sleep(2)

    print(f"\n{'═'*55}")
    print(f"  Loop ended after {cycle} cycle(s)")
    print(f"{'═'*55}")

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KLOUTBOT Autonomous Loop")
    parser.add_argument("--once", action="store_true", help="Single cycle only")
    parser.add_argument("--cycles", type=int, default=5, help="Number of cycles (default: 5)")
    parser.add_argument("--continuous", action="store_true", help="Run until Claude says done")
    parser.add_argument("--goal", type=str, default="", help="Specific goal for this run")
    args = parser.parse_args()

    if args.once:
        args.cycles = 1

    autonomous_loop(
        goal=args.goal or "diagnose why QIP has 0 intents_completed, fix the quantum signal pipeline, and verify gate4_real/inbox receives signals",
        max_cycles=args.cycles,
        continuous=args.continuous,
    )
