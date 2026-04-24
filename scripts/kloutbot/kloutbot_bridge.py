#!/usr/bin/env python3.10
"""
kloutbot_bridge.py
Goose-side bridge for the KLOUTBOT ↔ Goose two-layer architecture.

KLOUTBOT (Claude) writes instructions to the mesh channel 'kloutbot_instructions'.
This script (run by Goose as a tool) polls that channel, executes the instructions,
and posts results back to 'kloutbot_results'.

Goose tool usage:
    python3.10 scripts/kloutbot/kloutbot_bridge.py --poll           # check for new instructions
    python3.10 scripts/kloutbot/kloutbot_bridge.py --poll --execute # check AND execute what's found
    python3.10 scripts/kloutbot/kloutbot_bridge.py --status         # show pending + completed count
    python3.10 scripts/kloutbot/kloutbot_bridge.py --results        # print last N results
    python3.10 scripts/kloutbot/kloutbot_bridge.py --loop           # continuous poll loop (daemon mode)
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
BROKER_URL        = "http://127.0.0.1:5555"
AGENT_ID          = "goose_kloutbot_bridge"
AGENT_NAME        = "Goose KLOUTBOT Bridge"
IN_CHANNEL        = "kloutbot_instructions"
OUT_CHANNEL       = "kloutbot_results"
LOG_DIR           = Path("data/logs/goose")
RESULTS_LOG       = LOG_DIR / "kloutbot_results.jsonl"
POLL_INTERVAL     = 5    # seconds in loop mode
HEARTBEAT_EVERY   = 30
EXEC_TIMEOUT      = 120  # max seconds per command

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BRIDGE] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "kloutbot_bridge.log"),
    ],
)
log = logging.getLogger("bridge")

# ── Allowed command types (safety gate) ──────────────────────────────────────
ALLOWED_TYPES = {
    "bash",        # run a shell command
    "python",      # run an inline python snippet
    "file_write",  # write a file
    "diagnostic",  # run a named diagnostic (safe preset)
    "status",      # return system status (read-only)
}

DIAGNOSTIC_PRESETS = {
    "broker_status": "curl -s http://127.0.0.1:5555/status | python3.10 -m json.tool",
    "mesh_status":   "curl -s http://127.0.0.1:5555/mesh/routing/status | python3.10 -m json.tool",
    "mesh_agents":   "curl -s http://127.0.0.1:5555/mesh/routing/agents | python3.10 -m json.tool",
    "qip_log":       "tail -30 data/logs/goose/qip.log",
    "signals":       "ls -lt data/inboxes/gate4_real/*.json 2>/dev/null | head -5",
    "processes":     "ps aux | grep -E '(quantum|signal_bridge|projectx)' | grep -v grep",
    "trust_scores":  "python3.10 simp/mesh/trust_scorer.py --json 2>/dev/null || echo 'trust scorer unavailable'",
}


# ── Broker helpers ────────────────────────────────────────────────────────────

def _post(path, payload):
    try:
        r = requests.post(f"{BROKER_URL}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json() if r.content else {}
    except Exception as e:
        log.warning(f"POST {path}: {e}")
        return None


def _setup():
    _post("/agents/register", {
        "agent_id":   AGENT_ID,
        "agent_type": "bridge",
        "endpoint":   "",
        "metadata": {
            "name":         AGENT_NAME,
            "version":      "1.0.0",
            "capabilities": ["execute_kloutbot_instructions", "report_results"],
        },
    })
    _post("/mesh/subscribe", {"agent_id": AGENT_ID, "channel": IN_CHANNEL})
    _post("/mesh/subscribe", {"agent_id": AGENT_ID, "channel": OUT_CHANNEL})


def _heartbeat():
    try:
        r = requests.post(f"{BROKER_URL}/agents/{AGENT_ID}/heartbeat", json={}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"heartbeat failed: {e}")


def _poll_instructions() -> list[dict]:
    """GET /mesh/poll?agent_id=<id> — pulls queued messages for subscribed channels."""
    try:
        r = requests.get(
            f"{BROKER_URL}/mesh/poll",
            params={"agent_id": AGENT_ID, "max_messages": 10},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json() if r.content else {}
        if isinstance(data.get("messages"), list):
            # Filter to IN_CHANNEL only (in case receive returns other subscribed channels)
            msgs = [m for m in data["messages"] if m.get("channel") == IN_CHANNEL or not m.get("channel")]
            return msgs
    except Exception as e:
        log.warning(f"poll failed: {e}")
    return []


def _post_result(instruction_id: str, result: dict):
    envelope = {
        "instruction_id": instruction_id,
        "from":           AGENT_ID,
        "timestamp":      datetime.utcnow().isoformat(),
        "result":         result,
    }
    _post("/mesh/send", {
        "sender_id":    AGENT_ID,
        "recipient_id": "kloutbot",
        "channel":      OUT_CHANNEL,
        "payload":      envelope,
    })
    # Also append to local results log for --results command
    with open(RESULTS_LOG, "a") as f:
        f.write(json.dumps(envelope) + "\n")
    log.info(f"Result posted for instruction {instruction_id}")


# ── Executor ──────────────────────────────────────────────────────────────────

def _run_bash(cmd: str) -> dict:
    log.info(f"Running bash: {cmd[:100]}")
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=EXEC_TIMEOUT,
            cwd=os.getcwd(),
        )
        return {
            "exit_code": proc.returncode,
            "stdout":    proc.stdout[-4000:],  # cap at 4k chars
            "stderr":    proc.stderr[-2000:],
            "success":   proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "TIMEOUT", "success": False}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}


def _run_python(script: str) -> dict:
    log.info(f"Running python snippet ({len(script)} chars)")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        tmp = f.name
    try:
        proc = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True, timeout=EXEC_TIMEOUT,
            cwd=os.getcwd(),
        )
        return {
            "exit_code": proc.returncode,
            "stdout":    proc.stdout[-4000:],
            "stderr":    proc.stderr[-2000:],
            "success":   proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "TIMEOUT", "success": False}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}
    finally:
        Path(tmp).unlink(missing_ok=True)


def _write_file(path: str, content: str) -> dict:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"success": True, "path": str(p), "bytes": len(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_diagnostic(name: str) -> dict:
    cmd = DIAGNOSTIC_PRESETS.get(name)
    if not cmd:
        return {"success": False, "error": f"Unknown diagnostic: {name}. "
                f"Available: {list(DIAGNOSTIC_PRESETS.keys())}"}
    return _run_bash(cmd)


def _system_status() -> dict:
    status = {}
    # Broker
    try:
        r = requests.get(f"{BROKER_URL}/health", timeout=5)
        status["broker"] = r.json() if r.content else {"status": r.status_code}
    except Exception as e:
        status["broker"] = {"error": str(e)}
    # Processes
    proc = subprocess.run(
        "ps aux | grep -E '(quantum|signal_bridge|projectx)' | grep -v grep",
        shell=True, capture_output=True, text=True
    )
    status["processes"] = proc.stdout.strip().split("\n") if proc.stdout.strip() else []
    # Gate4 signals
    signals = list(Path("data/inboxes/gate4_real").glob("*.json"))
    status["gate4_signals"] = len(signals)
    status["timestamp"] = datetime.utcnow().isoformat()
    return status


def execute_instruction(instruction: dict) -> dict:
    """
    Execute a single instruction from KLOUTBOT.
    Instruction format:
    {
        "instruction_id": "uuid",
        "type": "bash" | "python" | "file_write" | "diagnostic" | "status",
        "cmd": "...",           # for bash
        "script": "...",        # for python
        "path": "...",          # for file_write
        "content": "...",       # for file_write
        "name": "...",          # for diagnostic
        "commands": [...]       # list of sub-commands (multi-step)
    }
    """
    cmd_type = instruction.get("type", "bash")

    if cmd_type not in ALLOWED_TYPES:
        return {"success": False, "error": f"Blocked type: {cmd_type}. Allowed: {ALLOWED_TYPES}"}

    # Multi-command instruction
    if "commands" in instruction:
        results = []
        for sub in instruction["commands"]:
            r = execute_instruction(sub)
            results.append(r)
            if not r.get("success") and instruction.get("stop_on_failure", False):
                break
        return {"success": all(r.get("success") for r in results), "results": results}

    # Single command
    if cmd_type == "bash":
        return _run_bash(instruction.get("cmd", "echo 'no cmd'"))
    elif cmd_type == "python":
        return _run_python(instruction.get("script", "print('no script')"))
    elif cmd_type == "file_write":
        return _write_file(instruction.get("path", "/tmp/kloutbot_tmp.txt"),
                           instruction.get("content", ""))
    elif cmd_type == "diagnostic":
        return _run_diagnostic(instruction.get("name", "broker_status"))
    elif cmd_type == "status":
        return _system_status()
    else:
        return {"success": False, "error": f"Unknown type: {cmd_type}"}


# ── Poll & execute cycle ──────────────────────────────────────────────────────

def poll_and_execute(dry_run: bool = False) -> list[dict]:
    _setup()
    messages = _poll_instructions()

    if not messages:
        print("No pending KLOUTBOT instructions.")
        return []

    print(f"Found {len(messages)} instruction(s).")
    executed = []

    for msg in messages:
        payload        = msg.get("payload", msg)
        instruction_id = payload.get("instruction_id", str(uuid.uuid4()))
        from_id        = payload.get("from", "kloutbot")
        cmd_type       = payload.get("type", "unknown")
        description    = payload.get("description", "")

        print(f"\n── Instruction {instruction_id} ─────────────────")
        print(f"  From:        {from_id}")
        print(f"  Type:        {cmd_type}")
        if description:
            print(f"  Description: {description}")

        if dry_run:
            print("  [DRY RUN — not executing]")
            continue

        print("  Executing...")
        result = execute_instruction(payload)

        # Print result summary
        if result.get("success"):
            print(f"  ✅ Success")
        else:
            print(f"  ❌ Failed: {result.get('error', result.get('stderr', '?'))[:200]}")

        if result.get("stdout"):
            print(f"  Output:\n{result['stdout'][:1000]}")

        _post_result(instruction_id, result)
        executed.append({"instruction_id": instruction_id, "result": result})

    return executed


# ── Show results ──────────────────────────────────────────────────────────────

def show_results(n: int = 10):
    if not RESULTS_LOG.exists():
        print("No results logged yet.")
        return
    lines = RESULTS_LOG.read_text().strip().split("\n")
    recent = lines[-n:]
    print(f"Last {len(recent)} KLOUTBOT results:\n")
    for line in recent:
        try:
            entry = json.loads(line)
            ts  = entry.get("timestamp", "?")
            iid = entry.get("instruction_id", "?")
            ok  = entry.get("result", {}).get("success", "?")
            print(f"  [{ts}] {iid} → success={ok}")
        except Exception:
            print(f"  {line[:100]}")


# ── Continuous loop ───────────────────────────────────────────────────────────

def run_loop():
    _setup()
    log.info(f"KLOUTBOT bridge loop started. Polling every {POLL_INTERVAL}s.")
    last_heartbeat = 0

    while True:
        try:
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_EVERY:
                _heartbeat()
                last_heartbeat = now

            messages = _poll_instructions()
            for msg in messages:
                payload        = msg.get("payload", msg)
                instruction_id = payload.get("instruction_id", str(uuid.uuid4()))
                log.info(f"Executing instruction {instruction_id}...")
                result = execute_instruction(payload)
                _post_result(instruction_id, result)

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log.info("Bridge stopped.")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(10)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KLOUTBOT ↔ Goose mesh bridge")
    parser.add_argument("--poll",    action="store_true", help="Poll for instructions (dry run)")
    parser.add_argument("--execute", action="store_true", help="Poll AND execute instructions")
    parser.add_argument("--results", action="store_true", help="Show recent results")
    parser.add_argument("--status",  action="store_true", help="Show system status")
    parser.add_argument("--loop",    action="store_true", help="Continuous poll+execute loop")
    parser.add_argument("--n",       type=int, default=10, help="Number of results to show")
    args = parser.parse_args()

    if args.loop:
        run_loop()
    elif args.execute:
        poll_and_execute(dry_run=False)
    elif args.poll:
        poll_and_execute(dry_run=True)
    elif args.results:
        show_results(args.n)
    elif args.status:
        print(json.dumps(_system_status(), indent=2))
    else:
        parser.print_help()
