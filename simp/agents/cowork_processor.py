"""
cowork_processor.py
===================
CoWork Inbox Processor — run at the start of each CoWork session (or via scheduled task).

This script reads pending intents from the cowork_inbox, prints them in a structured
format for Claude CoWork to process, then marks them as read.

Usage:
    python -m simp.agents.cowork_processor           # Show pending intents
    python -m simp.agents.cowork_processor --mark-read <queue_id>  # Mark one as read
    python -m simp.agents.cowork_processor --summary  # One-line count only

CoWork workflow:
    1. At session start, run: python -m simp.agents.cowork_processor
    2. Read and process each pending intent
    3. For each processed intent, write a response using write_response() from cowork_bridge
    4. Run: python -m simp.agents.cowork_processor --mark-read <queue_id>

This file has NO network dependencies — it only reads/writes local files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

INBOX_DIR  = os.environ.get("COWORK_INBOX",  os.path.expanduser("~/bullbear/signals/cowork_inbox"))
OUTBOX_DIR = os.environ.get("COWORK_OUTBOX", os.path.expanduser("~/bullbear/signals/cowork_outbox"))


def list_pending() -> list[dict]:
    results = []
    inbox = Path(INBOX_DIR)
    if not inbox.exists():
        return results
    for fpath in sorted(inbox.glob("intent_cowork-*.json")):
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("_status") == "pending":
                data["_file"] = str(fpath)
                results.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return results


def mark_read(queue_id: str) -> bool:
    inbox = Path(INBOX_DIR)
    for fpath in inbox.glob(f"intent_{queue_id}.json"):
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            data["_status"] = "processed"
            data["_processed_at"] = datetime.now(timezone.utc).isoformat()
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Marked {queue_id} as processed")
            return True
        except (json.JSONDecodeError, OSError) as e:
            print(f"❌ Could not mark {queue_id}: {e}")
    print(f"⚠️  Queue ID not found: {queue_id}")
    return False


def write_response(queue_id: str, result: dict, source_intent: dict) -> str:
    """Write a CoWork response intent to the outbox."""
    import uuid
    Path(OUTBOX_DIR).mkdir(parents=True, exist_ok=True)
    response = {
        "intent_id": f"resp-{uuid.uuid4().hex[:12]}",
        "intent_type": "cowork_response",
        "source_agent": "claude_cowork",
        "target_agent": source_intent.get("source_agent", "simp_router"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "_queue_id": queue_id,
        "_in_response_to": source_intent.get("intent_type"),
        "params": result,
    }
    path = os.path.join(OUTBOX_DIR, f"response_{queue_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2)
    mark_read(queue_id)
    return path


def print_pending(intents: list[dict]):
    if not intents:
        print("📭 No pending intents in CoWork inbox.")
        return
    print(f"\n{'='*60}")
    print(f"📬 CoWork Inbox — {len(intents)} pending intent(s)")
    print(f"{'='*60}")
    for i, intent in enumerate(intents, 1):
        print(f"\n[{i}] Queue ID   : {intent.get('_queue_id')}")
        print(f"     Intent Type: {intent.get('intent_type')}")
        print(f"     From       : {intent.get('source_agent')}")
        print(f"     Queued At  : {intent.get('_queued_at')}")
        params = intent.get("params", {})
        if params:
            print(f"     Params     :")
            for k, v in params.items():
                v_str = str(v)[:120] + "..." if len(str(v)) > 120 else str(v)
                print(f"       {k}: {v_str}")
        raw_file = intent.get("_file", "")
        if raw_file:
            print(f"     File       : {raw_file}")
    print(f"\n{'='*60}")
    print("To mark an intent as processed after handling:")
    print("  python -m simp.agents.cowork_processor --mark-read <queue_id>")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="CoWork inbox processor")
    parser.add_argument("--mark-read", metavar="QUEUE_ID", help="Mark intent as processed")
    parser.add_argument("--summary", action="store_true", help="Print count only")
    args = parser.parse_args()

    if args.mark_read:
        sys.exit(0 if mark_read(args.mark_read) else 1)

    pending = list_pending()

    if args.summary:
        print(f"CoWork inbox: {len(pending)} pending intent(s) in {INBOX_DIR}")
        sys.exit(0)

    print_pending(pending)


if __name__ == "__main__":
    main()
