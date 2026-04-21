#!/usr/bin/env python3.10
"""
/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/bin/cowork_bridge.py

Robust Claude CoWork SIMP bridge with:
- Canonical intent normalization
- Rotating file + console logging
- Structured JSON-safe responses
- Improved error handling and request validation
- File inbox polling
- Full-path defaults for Kasey's SIMP environment
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
import traceback
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

THIS_FILE = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/bin/cowork_bridge.py")
REPO_PATH_DEFAULT = Path("/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp")
if str(REPO_PATH_DEFAULT) not in sys.path:
    sys.path.insert(0, str(REPO_PATH_DEFAULT))

from simp.models.canonical_intent import CanonicalIntent

CLAUDE_CMD = os.environ.get("CLAUDE_CODE_CMD", "claude")
REPO_PATH = Path(os.environ.get("SIMP_REPO_PATH", str(REPO_PATH_DEFAULT))).expanduser()
PORT = int(os.environ.get("COWORK_PORT", "8767"))
MAX_TIMEOUT = int(os.environ.get("COWORK_TIMEOUT", "300"))
INBOX_DIR = Path(os.environ.get("COWORK_INBOX_DIR", "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/data/inboxes/claude_cowork")).expanduser()
OUTBOX_DIR = Path(os.environ.get("COWORK_OUTBOX_DIR", "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/data/outboxes/claude_cowork")).expanduser()
TMP_DIR = Path(os.environ.get("COWORK_TMP_DIR", "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/data/tmp")).expanduser()
LOG_PATH = Path(os.environ.get("COWORK_LOG_PATH", "/Users/kaseymarcelle/bullbear/logs/cowork_bridge.log")).expanduser()
ERROR_LOG_PATH = Path(os.environ.get("COWORK_ERROR_LOG_PATH", "/Users/kaseymarcelle/bullbear/logs/cowork_bridge_error.log")).expanduser()
POLL_INTERVAL_SECONDS = float(os.environ.get("COWORK_POLL_INTERVAL", "5"))

_work_queue = queue.Queue()
state_lock = threading.Lock()
bridge_state = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "intents_handled": 0,
    "intents_completed": 0,
    "intents_failed": 0,
    "http_requests": 0,
    "http_errors": 0,
    "normalization_failures": 0,
    "file_poll_cycles": 0,
    "file_intents_processed": 0,
    "last_intent_id": None,
    "last_error": None,
}

def ensure_parent_dirs() -> None:
    for path in [INBOX_DIR, OUTBOX_DIR, TMP_DIR, LOG_PATH.parent, ERROR_LOG_PATH.parent]:
        path.mkdir(parents=True, exist_ok=True)

def configure_logging() -> logging.Logger:
    ensure_parent_dirs()
    logger = logging.getLogger("cowork_bridge")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")

    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(ERROR_LOG_PATH, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger

logger = configure_logging()

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def update_state(**kwargs: Any) -> None:
    with state_lock:
        bridge_state.update(kwargs)

def bump_state(key: str, amount: int = 1) -> None:
    with state_lock:
        bridge_state[key] = int(bridge_state.get(key, 0)) + amount

def set_last_error(message: str) -> None:
    logger.error(message)
    update_state(last_error=message)

def short_exc() -> str:
    return traceback.format_exc(limit=5)

def safe_json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)

def normalize_intent(raw_intent: dict) -> dict:
    normalized = CanonicalIntent.from_dict(raw_intent)
    errors = normalized.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return normalized.to_dict()

def build_prompt(intent: dict) -> str:
    intent_type = intent.get("intent_type", "")
    params = intent.get("params", {}) or {}
    intent_id = intent.get("intent_id", "")
    source = intent.get("source_agent", "simp_broker")

    header = (
        f"# SIMP Task — {intent_type}\n"
        f"Task ID: {intent_id}\n"
        f"From: {source}\n"
        f"Repo: {REPO_PATH}\n\n"
    )

    if intent_type in ("code_task", "code_editing", "implementation"):
        body = f"## Task\n{params.get('task', params.get('description', safe_json_dumps(params)))}\n"
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
    elif intent_type == "docs":
        body = f"## Documentation Task\n{params.get('description', params.get('topic', ''))}\n"
    elif intent_type == "scaffolding":
        body = f"## Scaffolding Task\n{params.get('task', params.get('description', ''))}\n"
        if params.get("context"):
            body += f"\n## Context\n{params['context']}\n"
    elif intent_type == "orchestration":
        body = f"## Orchestration Task\n{params.get('task', params.get('description', ''))}\n"
    elif intent_type in ("native_agent_repo_scan", "improve_tree"):
        body = f"## Self-Improvement Task\n{safe_json_dumps(params)}\n"
    else:
        body = f"## Task (type: {intent_type})\n{safe_json_dumps(params)}\n"

    return header + body

def run_claude_code(prompt: str, intent_id: str) -> dict:
    start = time.time()
    prompt_file = TMP_DIR / f"cowork_{intent_id.replace(':', '_')[:64]}.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    cmd = [CLAUDE_CMD, "--dangerously-skip-permissions", "--print", prompt]
    logger.info("Running Claude Code for intent_id=%s cmd=%s", intent_id, cmd[0])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_PATH),
            timeout=MAX_TIMEOUT,
        )
        duration_ms = int((time.time() - start) * 1000)

        try:
            prompt_file.unlink()
        except Exception:
            logger.warning("Could not remove temp prompt file: %s", prompt_file)

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode == 0:
            return {
                "success": True,
                "output": stdout,
                "error": None,
                "duration_ms": duration_ms,
                "returncode": result.returncode,
            }

        return {
            "success": False,
            "output": stdout,
            "error": stderr or f"Claude Code exited with returncode={result.returncode}",
            "duration_ms": duration_ms,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Timed out after {MAX_TIMEOUT}s",
            "duration_ms": int((time.time() - start) * 1000),
            "returncode": None,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": "",
            "error": f"Claude Code CLI not found at '{CLAUDE_CMD}'. Set CLAUDE_CODE_CMD.",
            "duration_ms": int((time.time() - start) * 1000),
            "returncode": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "output": "",
            "error": f"{exc}\n{short_exc()}",
            "duration_ms": int((time.time() - start) * 1000),
            "returncode": None,
        }

def build_response(intent: dict, result: dict) -> dict:
    status = "completed" if result.get("success") else "failed"
    return {
        "type": "response",
        "intent_id": intent.get("intent_id", f"intent:cowork:{uuid.uuid4()}"),
        "agent_id": "claude_cowork",
        "status": status,
        "response": {
            "output": result.get("output", ""),
            "model": "claude-code",
            "duration_ms": result.get("duration_ms", 0),
            "intent_type": intent.get("intent_type", "unknown"),
            "returncode": result.get("returncode"),
        },
        "error": result.get("error"),
        "timestamp": utc_now_iso(),
    }

def process_intent(intent: dict) -> dict:
    intent_id = intent.get("intent_id", f"intent:cowork:{uuid.uuid4()}")
    intent_type = intent.get("intent_type", "unknown")
    update_state(last_intent_id=intent_id)
    bump_state("intents_handled")

    logger.info(
        "Processing intent_id=%s source_agent=%s target_agent=%s intent_type=%s",
        intent_id,
        intent.get("source_agent"),
        intent.get("target_agent"),
        intent_type,
    )

    try:
        prompt = build_prompt(intent)
        result = run_claude_code(prompt, intent_id)
        response = build_response(intent, result)

        if result.get("success"):
            bump_state("intents_completed")
            logger.info("Completed intent_id=%s duration_ms=%s", intent_id, result.get("duration_ms"))
        else:
            bump_state("intents_failed")
            logger.error("Failed intent_id=%s error=%s", intent_id, result.get("error"))

        return response

    except Exception as exc:
        bump_state("intents_failed")
        err = f"Unhandled process_intent error for {intent_id}: {exc}\n{short_exc()}"
        set_last_error(err)
        return {
            "type": "response",
            "intent_id": intent_id,
            "agent_id": "claude_cowork",
            "status": "failed",
            "response": {
                "output": "",
                "model": "claude-code",
                "duration_ms": 0,
                "intent_type": intent_type,
                "returncode": None,
            },
            "error": err,
            "timestamp": utc_now_iso(),
        }

def write_outbox_response(intent_id: str, response: dict) -> Path:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = intent_id.replace(":", "_").replace("/", "_")
    out_path = OUTBOX_DIR / f"{safe_id}_response.json"
    out_path.write_text(safe_json_dumps(response), encoding="utf-8")
    logger.info("Wrote outbox response: %s", out_path)
    return out_path

class CoworkHTTPHandler(BaseHTTPRequestHandler):
    server_version = "CoworkBridge/3.0"
    INTENT_ENDPOINTS = {"/intents/handle", "/intents/receive"}

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("HTTP %s", fmt % args)

    def _respond(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("Empty request body")
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    def do_GET(self) -> None:
        bump_state("http_requests")
        if self.path == "/health":
            with state_lock:
                snapshot = dict(bridge_state)
            self._respond(
                200,
                {
                    "status": "ok",
                    "agent_id": "claude_cowork",
                    "version": "3.0.0",
                    "repo_path": str(REPO_PATH),
                    "inbox": str(INBOX_DIR),
                    "outbox": str(OUTBOX_DIR),
                    "tmp_dir": str(TMP_DIR),
                    "log_path": str(LOG_PATH),
                    "error_log_path": str(ERROR_LOG_PATH),
                    "schema_validation": True,
                    "pending_count": _work_queue.qsize(),
                    "state": snapshot,
                    "timestamp": utc_now_iso(),
                },
            )
            return
        self._respond(404, {"error": "Not found", "path": self.path, "timestamp": utc_now_iso()})

    def do_POST(self) -> None:
        bump_state("http_requests")

        if self.path not in self.INTENT_ENDPOINTS:
            self._respond(404, {"error": "Not found", "path": self.path, "timestamp": utc_now_iso()})
            return

        try:
            raw_intent = self._read_json_body()
            if not isinstance(raw_intent, dict):
                raise ValueError("JSON body must be an object")

            logger.info(
                "Received raw intent path=%s payload_keys=%s",
                self.path,
                sorted(raw_intent.keys()),
            )

            try:
                intent = normalize_intent(raw_intent)
            except Exception as exc:
                bump_state("normalization_failures")
                msg = f"Intent normalization failed: {exc}"
                logger.error("%s payload=%s", msg, safe_json_dumps(raw_intent)[:4000])
                self._respond(
                    422,
                    {
                        "error": msg,
                        "received_keys": sorted(raw_intent.keys()),
                        "timestamp": utc_now_iso(),
                    },
                )
                return

            response = process_intent(intent)
            write_outbox_response(intent["intent_id"], response)
            status_code = 200 if response.get("status") == "completed" else 500
            self._respond(status_code, response)

        except ValueError as exc:
            bump_state("http_errors")
            logger.error("Bad request error: %s", exc)
            self._respond(400, {"error": str(exc), "timestamp": utc_now_iso()})

        except Exception as exc:
            bump_state("http_errors")
            err = f"Unhandled HTTP error: {exc}"
            set_last_error(err)
            logger.error("%s\n%s", err, short_exc())
            self._respond(500, {"error": err, "timestamp": utc_now_iso()})

def poll_inbox() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    processed_dir = INBOX_DIR / "processed"
    failed_dir = INBOX_DIR / "failed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Polling file inbox: %s", INBOX_DIR)

    while True:
        bump_state("file_poll_cycles")
        try:
            for intent_file in sorted(INBOX_DIR.glob("*.json")):
                logger.info("Found inbox file: %s", intent_file)
                try:
                    raw = json.loads(intent_file.read_text(encoding="utf-8"))
                    intent = normalize_intent(raw)
                    response = process_intent(intent)
                    write_outbox_response(intent["intent_id"], response)

                    destination = processed_dir / intent_file.name
                    intent_file.rename(destination)
                    bump_state("file_intents_processed")
                    logger.info("Moved processed inbox file to: %s", destination)

                except Exception as exc:
                    logger.error("Error processing inbox file %s error=%s\n%s", intent_file, exc, short_exc())
                    failed_dest = failed_dir / intent_file.name
                    try:
                        intent_file.rename(failed_dest)
                        logger.info("Moved failed inbox file to: %s", failed_dest)
                    except Exception as move_exc:
                        logger.error("Could not move failed file %s error=%s", intent_file, move_exc)

        except Exception as exc:
            set_last_error(f"Inbox poll error: {exc}")
            logger.error("Inbox poll exception\n%s", short_exc())

        time.sleep(POLL_INTERVAL_SECONDS)

def main() -> None:
    global REPO_PATH, PORT, INBOX_DIR, OUTBOX_DIR, TMP_DIR

    parser = argparse.ArgumentParser(description="Robust SIMP Claude Code Bridge")
    parser.add_argument("--port", type=int, default=PORT, help="Port to listen on (default: 8767)")
    parser.add_argument("--repo-path", default=str(REPO_PATH), help="Absolute path to SIMP repo")
    parser.add_argument("--inbox-dir", default=str(INBOX_DIR), help="Absolute path to file inbox")
    parser.add_argument("--outbox-dir", default=str(OUTBOX_DIR), help="Absolute path to file outbox")
    parser.add_argument("--tmp-dir", default=str(TMP_DIR), help="Absolute path to temp prompt dir")
    args = parser.parse_args()

    REPO_PATH = Path(args.repo_path).expanduser()
    PORT = int(args.port)
    INBOX_DIR = Path(args.inbox_dir).expanduser()
    OUTBOX_DIR = Path(args.outbox_dir).expanduser()
    TMP_DIR = Path(args.tmp_dir).expanduser()

    ensure_parent_dirs()

    logger.info("Starting cowork_bridge")
    logger.info("THIS_FILE=%s", THIS_FILE)
    logger.info("REPO_PATH=%s", REPO_PATH)
    logger.info("PORT=%s", PORT)
    logger.info("INBOX_DIR=%s", INBOX_DIR)
    logger.info("OUTBOX_DIR=%s", OUTBOX_DIR)
    logger.info("TMP_DIR=%s", TMP_DIR)
    logger.info("LOG_PATH=%s", LOG_PATH)
    logger.info("ERROR_LOG_PATH=%s", ERROR_LOG_PATH)
    logger.info("CLAUDE_CMD=%s", CLAUDE_CMD)

    poller = threading.Thread(target=poll_inbox, daemon=True, name="cowork-inbox-poller")
    poller.start()

    server = HTTPServer(("127.0.0.1", PORT), CoworkHTTPHandler)
    logger.info("Listening on http://127.0.0.1:%s", PORT)
    logger.info("Endpoints: GET /health  POST /intents/handle  POST /intents/receive")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down cowork_bridge")
    finally:
        server.server_close()
        logger.info("cowork_bridge stopped cleanly")

if __name__ == "__main__":
    main()
