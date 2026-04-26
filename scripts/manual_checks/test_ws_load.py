#!/usr/bin/env python3.10
"""
WS Bridge Load Test — 100+ concurrent agents.

Usage:
    SIMP_JWT_SECRET=test-secret SIMP_WS_PORT=15556 python3.10 scripts/manual_checks/test_ws_load.py
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("LOAD_TEST")


# ── Config ──────────────────────────────────────────────────────────────────
WS_PORT = int(os.environ.get("SIMP_WS_PORT", 15556))
WS_HOST = os.environ.get("SIMP_WS_HOST", "127.0.0.1")
NUM_AGENTS = int(os.environ.get("WS_LOAD_AGENTS", 100))
INTENTS_PER_AGENT = int(os.environ.get("WS_LOAD_INTENTS", 10))
BROKER_URL = os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:15555")
os.environ.setdefault("SIMP_JWT_SECRET", "test-secret")

# ── JWT issuance ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from simp.server.jwt_auth import issue_agent_token


def make_token(agent_id: str) -> str:
    token = issue_agent_token(agent_id, capabilities=["trade", "analyze"])
    if not token:
        raise RuntimeError("JWT not configured")
    return token


# ── Agent worker ─────────────────────────────────────────────────────────────
async def agent_worker(agent_id: str, stats: dict, lock: asyncio.Lock):
    uri = f"ws://{WS_HOST}:{WS_PORT}"
    connect_start = time.time()
    connected = False

    try:
        async with websockets.connect(uri, ping_interval=30) as ws:
            await ws.send(json.dumps({"type": "auth", "token": make_token(agent_id)}))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
            if resp.get("type") != "auth_ok":
                async with lock:
                    stats["auth_failures"] += 1
                return

            connect_time = time.time() - connect_start
            async with lock:
                stats["connections"].append((agent_id, connect_time))
                connected = True

            # Subscribe to a channel
            channel = random.choice(["alerts", "intent.routed", f"signals.{random.randint(1,3)}"])
            await ws.send(json.dumps({"type": "subscribe", "channels": [channel]}))

            # Wait for subscribed confirmation
            try:
                sub_resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

            # Send intents
            for i in range(INTENTS_PER_AGENT):
                intent = {
                    "intent_type": "test.load",
                    "target_agent": f"target-{random.randint(1, 10)}",
                    "payload": {"msg": f"load-test-{i}", "agent": agent_id},
                }
                await ws.send(json.dumps({"type": "intent", "intent": intent}))

                # Expect intent_result or push
                try:
                    resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg = json.loads(resp)
                    if msg.get("type") == "intent_result":
                        async with lock:
                            stats["intent_results"] += 1
                    elif msg.get("type") == "push":
                        async with lock:
                            stats["pushes_received"] += 1
                except asyncio.TimeoutError:
                    async with lock:
                        stats["timeouts"] += 1

                # Small random delay
                await asyncio.sleep(random.uniform(0.01, 0.05))

            # Send close
            await ws.send(json.dumps({"type": "close"}))

    except Exception as exc:
        async with lock:
            stats["errors"] += 1
            if not connected:
                stats["auth_failures"] += 1


# ── Main ─────────────────────────────────────────────────────────────────────
async def run_load_test():
    stats = {
        "connections": [],  # (agent_id, connect_time)
        "auth_failures": 0,
        "intent_results": 0,
        "pushes_received": 0,
        "timeouts": 0,
        "errors": 0,
    }
    lock = asyncio.Lock()

    logger.info(f"🚀 Starting load test: {NUM_AGENTS} agents × {INTENTS_PER_AGENT} intents")
    logger.info(f"   Target: ws://{WS_HOST}:{WS_PORT}")

    start_time = time.time()

    # Launch all agents concurrently
    tasks = [
        agent_worker(f"load-agent-{i:03d}", stats, lock)
        for i in range(NUM_AGENTS)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    total_time = time.time() - start_time

    # ── Report ────────────────────────────────────────────────────────────────
    connect_times = [ct for _, ct in stats["connections"]]
    logger.info(f"\n{'═' * 60}")
    logger.info(f"  Load Test Results ({NUM_AGENTS} agents)")
    logger.info(f"{'═' * 60}")
    logger.info(f"  Total time:         {total_time:.2f}s")
    logger.info(f"  Throughput:         {NUM_AGENTS * INTENTS_PER_AGENT / total_time:.1f} intents/sec")
    logger.info(f"  Auth failures:      {stats['auth_failures']}")
    logger.info(f"  Intent results:     {stats['intent_results']}")
    logger.info(f"  Pushes received:    {stats['pushes_received']}")
    logger.info(f"  Timeouts:           {stats['timeouts']}")
    logger.info(f"  Errors:             {stats['errors']}")

    if connect_times:
        logger.info(f"  Connect time avg:   {sum(connect_times)/len(connect_times)*1000:.1f}ms")
        logger.info(f"  Connect time p99:   {sorted(connect_times)[int(len(connect_times)*0.99)]*1000:.1f}ms")
        logger.info(f"  Connect time max:   {max(connect_times)*1000:.1f}ms")

    logger.info(f"{'═' * 60}")

    # Success criteria
    success = (
        stats["auth_failures"] == 0 and
        stats["errors"] == 0 and
        total_time < 60
    )
    logger.info(f"  Result: {'✅ PASS' if success else '❌ FAIL'}")
    return success


if __name__ == "__main__":
    success = asyncio.run(run_load_test())
    sys.exit(0 if success else 1)
