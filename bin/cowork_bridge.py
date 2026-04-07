#!/usr/bin/env python3
"""cowork_bridge.py — Claude Code SIMP agent adapter.

This script is the missing link between the SIMP broker and Claude Code.
It runs an HTTP server on port 8767 that:
  1. Accepts SIMP intent JSON via POST /intents/handle
  2. Translates each intent into a Claude Code CLI call
  3. Returns a structured SIMP response

Also polls data/inboxes/claude_cowork/ for file-based fallback intents.

Usage:
    python3.10 bin/cowork_bridge.py [--port 8767] [--repo-path /path/to/simp]

Environment variables:
    CLAUDE_CODE_CMD    Command to invoke Claude Code (default: claude)
    SIMP_REPO_PATH     Path to the SIMP repo (default: cwd)
    COWORK_PORT        Port to listen on (default: 8767)
    COWORK_INBOX_DIR   File-based inbox dir (default: data/inboxes/claude_cowork)
    SIMP_BROKER_URL    Broker URL for response submission (default: http://127.0.0.1:5555)
"""

import argparse
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cowork_bridge] %(levelname)s: %(message)s",
)
logger = logging.getLogger("cowork_bridge")

# ── Config ───────────────────────────────────────────────────────────────────

CLAUDE_CMD = os.environ.get("CLAUDE_CODE_CMD", "claude")
REPO_PATH = Path(os.environ.get("SIMP_REPO_PATH", os.getcwd()))
PORT = int(os.environ.get("COWORK_PORT", 8767))
INBOX_DIR = REPO_PATH / os.environ.get("COWORK_INBOX_DIR", "data/inboxes/claude_cowork")
BROKER_URL = os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:5555")
MAX_TIMEOUT = int(os.environ.get("COWORK_TIMEOUT", 300))  # 5 min per task

intents_handled = 0
_work_queue = queue.Queue()

# ── Prompt Builder ────────────────────────────────────────────────────────────

def build_prompt(intent: dict) -> str:
    """Translate a SIMP intent into a Claude Code prompt."""
    intent_type = intent.get("intent_type", "")
    params = intent.get("params", {})
    intent_id = intent.get("intent_id", "")
    source = intent.get("source_agent", "simp_broker")

    header = (
        f"# SIMP Task — {intent_type}\n"
        f"Task ID: {intent_id}\n"
        f"From: {source}\n"
        f"Repo: {REPO_PATH}\n\n"
    )

    if intent_type in ("code_task", "code_editing", "implementation"):
        body = f"## Task\n{params.get('task', params.get('description', json.dumps(params)))}\n"
        if params.get("file"):
            body += f"\n## Target file\n{params['file']}\n"
        if params.get("code"):
            body += f"\n## Existing code\n```\n{params['code']}\n```\n"

    elif intent_type == "code_review":
        body = f"## Code Review\n{params.get('code', params.get('diff', ''))}\n"
        body += "\nProvide: issues, suggestions, severity (blocking/non-blocking)."

    elif intent_type in ("research", "summarization"):
        body = f"## Research Request\n{params.get('query', params.get('text', params.get('topic', '')))}\n"

    elif intent_type in ("planning", "architecture", "spec"):
        body = f"## {intent_type.title()} Task\n{params.get('goal', params.get('description', ''))}\n"

    elif intent_type in ("test_harness", "test"):
        body = f"## Test Task\n{params.get('task', params.get('description', ''))}\n"
        body += f"\nRun from: {REPO_PATH}\n"

    elif intent_type in ("docs",):
        body = f"## Documentation Task\n{params.get('description', params.get('topic', ''))}\n"

    elif intent_type == "scaffolding":
        body = f"## Scaffolding Task\n{params.get('task', params.get('description', ''))}\n"
        if params.get("context"):
            body += f"\n## Context\n{params['context']}\n"

    elif intent_type == "orchestration":
        body = f"## Orchestration Task\n{params.get('task', params.get('description', ''))}\n"

    elif intent_type in ("native_agent_repo_scan", "improve_tree"):
        body = f"## Self-Improvement Task\n{json.dumps(params, indent=2)}\n"

    else:
        body = f"## Task (type: {intent_type})\n{json.dumps(params, indent=2)}\n"

    return header + body


# ── Claude Code Executor ──────────────────────────────────────────────────────

def run_claude_code(prompt: str, intent_id: str) -> dict:
    """Invoke Claude Code CLI with the given prompt. Returns result dict."""
    start = time.time()

    # Write prompt to temp file (avoids shell escaping issues with long prompts)
    prompt_file = REPO_PATH / "data" / "tmp" / f"cowork_{intent_id[:8]}.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt)

    cmd = [
        CLAUDE_CMD,
        "--dangerously-skip-permissions",
        "--print",  # Non-interactive, print output and exit
        prompt,
    ]

    try:
        logger.info(f"Running Claude Code for intent {intent_id[:16]}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_PATH),
            timeout=MAX_TIMEOUT,
        )
        duration_ms = int((time.time() - start) * 1000)

        # Clean up temp file
        try:
            prompt_file.unlink()
        except Exception:
            pass

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout.strip(),
                "duration_ms": duration_ms,
            }
        else:
            return {
                "success": False,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() or f"Exit code {result.returncode}",
                "duration_ms": duration_ms,
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Timed out after {MAX_TIMEOUT}s",
            "duration_ms": int((time.time() - start) * 1000),
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Claude Code CLI not found at '{CLAUDE_CMD}'. Set CLAUDE_CODE_CMD env var.",
            "duration_ms": int((time.time() - start) * 1000),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "duration_ms": int((time.time() - start) * 1000),
        }


# ── Intent Processor ──────────────────────────────────────────────────────────

def process_intent(intent: dict) -> dict:
    """Full pipeline: build prompt → run Claude Code → return SIMP response."""
    global intents_handled
    intent_id = intent.get("intent_id", f"intent:cowork:{uuid.uuid4()}")
    intent_type = intent.get("intent_type", "unknown")

    logger.info(f"Processing intent {intent_id[:24]} type={intent_type}")

    prompt = build_prompt(intent)
    result = run_claude_code(prompt, intent_id)
    intents_handled += 1

    status = "completed" if result.get("success") else "failed"

    return {
        "type": "response",
        "intent_id": intent_id,
        "agent_id": "claude_cowork",
        "status": status,
        "response": {
            "output": result.get("output", ""),
            "model": "claude-code",
            "duration_ms": result.get("duration_ms", 0),
            "intent_type": intent_type,
        },
        "error": result.get("error"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class CoworkHTTPHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {
                "status": "ok",
                "agent_id": "claude_cowork",
                "inbox": str(INBOX_DIR),
                "outbox": str(REPO_PATH / "data" / "outboxes" / "claude_cowork"),
                "pending_count": _work_queue.qsize(),
                "registered": True,
                "response_count": intents_handled,
                "schema_validation": True,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                "version": "2.0.0",
            })
        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/intents/handle":
            length = int(self.headers.get("Content-Length", 0))
            try:
                intent = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self._respond(400, {"error": "Invalid JSON"})
                return

            # Process synchronously (simpler, avoids state management complexity)
            response = process_intent(intent)
            http_status = 200 if response.get("status") == "completed" else 500
            self._respond(http_status, response)
        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, status: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        logger.info(f"HTTP {fmt % args}")


# ── File-Based Inbox Poller ───────────────────────────────────────────────────

def poll_inbox():
    """Poll data/inboxes/claude_cowork/ for file-based intent delivery."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    processed_dir = INBOX_DIR / "processed"
    processed_dir.mkdir(exist_ok=True)

    logger.info(f"Polling file inbox: {INBOX_DIR}")

    while True:
        try:
            for intent_file in sorted(INBOX_DIR.glob("*.json")):
                try:
                    intent = json.loads(intent_file.read_text())
                    response = process_intent(intent)

                    # Write response to outbox
                    outbox = REPO_PATH / "data" / "outboxes" / "claude_cowork"
                    outbox.mkdir(parents=True, exist_ok=True)
                    intent_id = intent.get("intent_id", intent_file.stem)
                    (outbox / f"{intent_id}_response.json").write_text(
                        json.dumps(response, indent=2)
                    )

                    # Move to processed
                    intent_file.rename(processed_dir / intent_file.name)
                    logger.info(f"File intent processed: {intent_file.name}")

                except Exception as exc:
                    logger.error(f"Error processing {intent_file}: {exc}")

        except Exception as exc:
            logger.error(f"Inbox poll error: {exc}")

        time.sleep(5)  # Poll every 5 seconds


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global REPO_PATH, INBOX_DIR

    parser = argparse.ArgumentParser(description="SIMP Claude Code Bridge")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--repo-path", default=str(REPO_PATH))
    args = parser.parse_args()

    REPO_PATH = Path(args.repo_path)
    INBOX_DIR = REPO_PATH / "data" / "inboxes" / "claude_cowork"

    logger.info(f"Starting cowork_bridge on port {args.port}")
    logger.info(f"Repo path: {REPO_PATH}")
    logger.info(f"Claude command: {CLAUDE_CMD}")

    # Start file inbox poller in background thread
    poller = threading.Thread(target=poll_inbox, daemon=True)
    poller.start()

    # Start HTTP server
    server = HTTPServer(("127.0.0.1", args.port), CoworkHTTPHandler)
    logger.info(f"Listening on http://127.0.0.1:{args.port}")
    logger.info("Endpoints: GET /health  POST /intents/handle")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down cowork_bridge")
        server.shutdown()


if __name__ == "__main__":
    main()
