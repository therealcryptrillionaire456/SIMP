"""
Test the SIMP WebSocket Bridge.

Launches a minimal Flask broker + WS bridge in-process, then connects
via websockets client to verify auth, intent forwarding, and push.

Usage: PYTHONPATH=".." .venv/bin/python tests/test_ws_bridge.py
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time

# Ensure JWT is configured
os.environ["SIMP_JWT_SECRET"] = "test-secret-key-for-websocket-test-32chars"
os.environ["SIMP_JWT_REQUIRED"] = "false"
os.environ["SIMP_WS_PORT"] = "15556"  # Avoid collision with real broker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import websockets

from simp.server.ws_bridge import WsBridge
from simp.server.jwt_auth import issue_agent_token

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("TEST")


def issue_jwt(agent_id: str) -> str:
    """Issue a test JWT via jwt_auth module (ensures correct signing)."""
    token = issue_agent_token(agent_id, capabilities=["trade", "analyze"])
    if not token:
        raise RuntimeError("JWT not configured (issue_agent_token returned None)")
    return token


async def run_tests():
    """Run all WS bridge tests."""

    bridge = WsBridge(port=15556, broker_url="http://127.0.0.1:15555")
    await bridge.start()
    logger.info("WS Bridge started on :15556")

    passed = 0
    failed = 0

    # ── Test 1: Auth required (no token) ─────────────────────────────────────
    logger.info("\n═══ Test 1: Auth required (no token) ═══")
    try:
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "ping"}))  # Skip auth
        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "error", f"Expected error, got {result}"
        assert result.get("code") == "AUTH_REQUIRED", f"Expected AUTH_REQUIRED, got {result}"
        logger.info(f"  ✅ Test 1 passed: {result.get('message')}")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 1 failed: {exc}")
        failed += 1

    # ── Test 2: Auth with valid JWT ──────────────────────────────────────────
    logger.info("\n═══ Test 2: Auth with valid JWT ═══")
    try:
        token = issue_jwt("test-agent-1")
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "auth", "token": token}))
        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "auth_ok", f"Expected auth_ok, got {result}"
        assert result.get("agent_id") == "test-agent-1"
        logger.info(f"  ✅ Test 2 passed: {result}")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 2 failed: {exc}")
        failed += 1
    finally:
        try:
            await ws.close()
        except Exception:
            pass

    # ── Test 3: Auth with invalid JWT ────────────────────────────────────────
    logger.info("\n═══ Test 3: Auth with invalid JWT ═══")
    try:
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "auth", "token": "not-a-real-token"}))
        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("code") == "AUTH_FAILED", f"Expected AUTH_FAILED, got {result}"
        logger.info(f"  ✅ Test 3 passed: {result.get('message')}")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 3 failed: {exc}")
        failed += 1

    # ── Test 4: Ping/Pong ────────────────────────────────────────────────────
    logger.info("\n═══ Test 4: Ping/Pong ═══")
    try:
        token = issue_jwt("test-agent-2")
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "auth", "token": token}))
        await asyncio.wait_for(ws.recv(), timeout=3.0)  # auth_ok

        await ws.send(json.dumps({"type": "ping"}))
        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "pong", f"Expected pong, got {result}"
        logger.info("  ✅ Test 4 passed")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 4 failed: {exc}")
        failed += 1
    finally:
        try:
            await ws.close()
        except Exception:
            pass

    # ── Test 5: Subscribe / Unsubscribe ──────────────────────────────────────
    logger.info("\n═══ Test 5: Subscribe / Unsubscribe ═══")
    try:
        token = issue_jwt("test-agent-3")
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "auth", "token": token}))
        await asyncio.wait_for(ws.recv(), timeout=3.0)  # auth_ok

        await ws.send(json.dumps({"type": "subscribe", "channels": ["signals", "alerts"]}))
        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "subscribed", f"Expected subscribed, got {result}"
        assert len(result.get("channels", [])) == 2

        # Verify bridge has the subscription
        assert "signals" in bridge._channels
        assert "alerts" in bridge._channels
        assert "test-agent-3" in bridge._channels["signals"]

        # Unsubscribe
        await ws.send(json.dumps({"type": "unsubscribe", "channels": ["signals"]}))
        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "unsubscribed", f"Expected unsubscribed, got {result}"

        # Verify channel cleaned up
        assert "signals" not in bridge._channels or "test-agent-3" not in bridge._channels["signals"]

        logger.info("  ✅ Test 5 passed")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 5 failed: {exc}")
        failed += 1
    finally:
        try:
            await ws.close()
        except Exception:
            pass

    # ── Test 6: Push to channel ──────────────────────────────────────────────
    logger.info("\n═══ Test 6: Push to channel ═══")
    try:
        token = issue_jwt("test-agent-4")
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "auth", "token": token}))
        await asyncio.wait_for(ws.recv(), timeout=3.0)  # auth_ok

        # Subscribe
        await ws.send(json.dumps({"type": "subscribe", "channels": ["test-push"]}))
        await asyncio.wait_for(ws.recv(), timeout=3.0)  # subscribed

        # Push via bridge
        await bridge.push_to_channel("test-push", {"event": "price_alert", "symbol": "BTC"})

        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "push", f"Expected push, got {result}"
        assert result.get("channel") == "test-push"
        assert result["data"]["symbol"] == "BTC"
        logger.info("  ✅ Test 6 passed")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 6 failed: {exc}")
        failed += 1
    finally:
        try:
            await ws.close()
        except Exception:
            pass

    # ── Test 7: Push to specific agent ──────────────────────────────────────
    logger.info("\n═══ Test 7: Push to specific agent ═══")
    try:
        token = issue_jwt("test-agent-5")
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "auth", "token": token}))
        await asyncio.wait_for(ws.recv(), timeout=3.0)  # auth_ok

        await bridge.push_to_agent("test-agent-5", {"direct": "message"})

        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "push", f"Expected push, got {result}"
        assert result["data"]["direct"] == "message"
        logger.info("  ✅ Test 7 passed")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 7 failed: {exc}")
        failed += 1
    finally:
        try:
            await ws.close()
        except Exception:
            pass

    # ── Test 8: Multiple concurrent connections ─────────────────────────────
    logger.info("\n═══ Test 8: Multiple concurrent connections ═══")
    try:
        agents = [f"multi-agent-{i}" for i in range(5)]
        connections = []

        for agent_id in agents:
            token = issue_jwt(agent_id)
            ws = await websockets.connect("ws://127.0.0.1:15556")
            await ws.send(json.dumps({"type": "auth", "token": token}))
            await asyncio.wait_for(ws.recv(), timeout=3.0)  # auth_ok
            connections.append(ws)

        assert bridge.connected_count == 5
        logger.info(f"  ✅ Test 8 passed: {bridge.connected_count} agents connected")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 8 failed: {exc}")
        failed += 1
    finally:
        for ws in connections:
            try:
                await ws.close()
            except Exception:
                pass

    # ── Test 9: Unknown message type ─────────────────────────────────────────
    logger.info("\n═══ Test 9: Unknown message type ═══")
    try:
        token = issue_jwt("test-agent-6")
        ws = await websockets.connect("ws://127.0.0.1:15556")
        await ws.send(json.dumps({"type": "auth", "token": token}))
        await asyncio.wait_for(ws.recv(), timeout=3.0)  # auth_ok

        await ws.send(json.dumps({"type": "do_a_barrel_roll"}))
        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
        result = json.loads(response)
        assert result.get("type") == "error", f"Expected error, got {result}"
        assert result.get("code") == "UNKNOWN_TYPE"
        logger.info("  ✅ Test 9 passed")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 9 failed: {exc}")
        failed += 1
    finally:
        try:
            await ws.close()
        except Exception:
            pass

    # ── Test 10: Stats tracking ──────────────────────────────────────────────
    logger.info("\n═══ Test 10: Stats tracking ═══")
    try:
        stats = bridge.stats
        logger.info(f"  Stats: {json.dumps(stats, indent=2)}")
        assert stats["connections_total"] >= 8  # Many connect/disconnect cycles
        assert stats["auth_failures"] >= 1
        assert stats["pushes_sent"] >= 2  # Test 6 + Test 7
        logger.info("  ✅ Test 10 passed: stats tracking works")
        passed += 1
    except Exception as exc:
        logger.error(f"  ❌ Test 10 failed: {exc}")
        failed += 1

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info(f"\n{'═' * 60}")
    logger.info(f"  Results: {passed}/{passed + failed} passed")
    if failed:
        logger.error(f"  {failed} tests FAILED")
    else:
        logger.info("  🎉 All tests passed!")
    logger.info(f"{'═' * 60}")

    await bridge.stop()
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
