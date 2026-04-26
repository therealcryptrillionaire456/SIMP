"""
SIMP WebSocket Client — Resilient agent-side WebSocket with auto-reconnect.

Usage:
    client = WsClient("ws://127.0.0.1:5556", token_generator_fn)
    await client.connect()
    async for msg in client:
        print(msg)
    await client.close()
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

import websockets
from websockets.client import connect
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger("SIMP.WS.Client")

# ── Reconnect config ──────────────────────────────────────────────────────────
DEFAULT_MAX_RETRIES = 0  # 0 = infinite
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 30.0  # seconds
DEFAULT_BACKOFF_FACTOR = 2.0


class WsConnectionError(Exception):
    """Raised when connection cannot be established."""
    pass


class WsClient:
    """
    Resilient WebSocket client for SIMP agents.

    Handles JWT auth, auto-reconnect with exponential backoff,
    message queuing during reconnection, and heartbeat.
    """

    def __init__(
        self,
        uri: str,
        token_provider: Callable[[], str],
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        ping_interval: float = 30.0,
        reconnect_on_close: bool = True,
    ):
        self.uri = uri
        self.token_provider = token_provider
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.ping_interval = ping_interval
        self.reconnect_on_close = reconnect_on_close

        self._ws: Optional["websockets.WebSocketClientProtocol"] = None
        self._connected = False
        self._closing = False
        self._agent_id: Optional[str] = None
        self._capabilities: List[str] = []
        self._retry_count = 0
        self._queue: asyncio.Queue = asyncio.Queue()
        self._recv_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    @property
    def agent_id(self) -> Optional[str]:
        return self._agent_id

    @property
    def capabilities(self) -> List[str]:
        return self._capabilities

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def connect(self) -> Dict[str, Any]:
        """Connect and authenticate. Returns auth_ok response or raises."""
        if self._closing:
            raise WsConnectionError("Client is closing")

        self._ws = await connect(
            self.uri,
            ping_interval=self.ping_interval,
            ping_timeout=10.0,
            max_size=10 * 1024 * 1024,  # 10MB
        )

        token = self.token_provider()
        await self._ws.send(json.dumps({"type": "auth", "token": token}))

        raw = await asyncio.wait_for(self._ws.recv(), timeout=15.0)
        resp = json.loads(raw)

        if resp.get("type") != "auth_ok":
            raise WsConnectionError(f"Auth failed: {resp}")

        self._agent_id = resp.get("agent_id")
        self._capabilities = resp.get("capabilities", [])
        self._connected = True
        self._retry_count = 0

        self._recv_task = asyncio.create_task(self._recv_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

        logger.info(f"WS connected: agent_id={self._agent_id}")
        return resp

    async def close(self, code: int = 1000, reason: str = "Normal close"):
        """Gracefully close the connection."""
        self._closing = True
        self._connected = False

        if self._recv_task:
            self._recv_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()

        if self._ws:
            try:
                await self._ws.close(code, reason)
            except Exception:
                pass
            self._ws = None

        logger.info(f"WS closed: agent_id={self._agent_id}")

    # ── Message sending ───────────────────────────────────────────────────────

    async def send(self, msg: Dict[str, Any]):
        """Send a message. Queues during reconnection."""
        if not self.is_connected:
            await self._reconnect_loop()
            if not self.is_connected:
                self._queue.put_nowait(msg)
                return

        try:
            await self._ws.send(json.dumps(msg))
        except (ConnectionClosed, OSError):
            self._queue.put_nowait(msg)
            await self._reconnect_loop()

    async def subscribe(self, channels: List[str]):
        """Subscribe to channel(s)."""
        await self.send({"type": "subscribe", "channels": channels})

    async def unsubscribe(self, channels: List[str]):
        """Unsubscribe from channel(s)."""
        await self.send({"type": "unsubscribe", "channels": channels})

    async def send_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Send an intent and wait for result."""
        if not self.is_connected:
            raise WsConnectionError("Not connected")

        future = asyncio.Future()

        async def listener():
            async for raw in self._ws:
                msg = json.loads(raw)
                if msg.get("type") == "intent_result" and msg.get("result", {}).get("intent_id") == intent.get("intent_id"):
                    future.set_result(msg)
                    return

        listener_task = asyncio.create_task(listener())
        await self.send({"type": "intent", "intent": intent})
        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            listener_task.cancel()
            raise
        finally:
            listener_task.cancel()

    # ── Message receiving ────────────────────────────────────────────────────

    async def _recv_loop(self):
        """Background receive loop that enqueues incoming messages."""
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._queue.put(msg)
        except ConnectionClosed:
            pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Recv loop error: {exc}")

    async def _ping_loop(self):
        """Send periodic ping to keep connection alive."""
        while self._connected and not self._closing:
            await asyncio.sleep(self.ping_interval)
            if self.is_connected:
                try:
                    await self._ws.send(json.dumps({"type": "ping"}))
                except Exception:
                    pass

    async def __aiter__(self):
        """Async iterator for incoming messages."""
        while self._connected or not self._queue.empty():
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

    # ── Reconnection ─────────────────────────────────────────────────────────

    async def _reconnect_loop(self):
        """Retry connection with exponential backoff until success or max_retries."""
        if not self.reconnect_on_close or self._closing:
            return

        delay = self.base_delay
        while not self._connected and not self._closing:
            if self.max_retries > 0 and self._retry_count >= self.max_retries:
                logger.error(f"Max retries ({self.max_retries}) reached, giving up")
                raise WsConnectionError(f"Max retries ({self.max_retries}) reached")

            self._retry_count += 1
            logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._retry_count})...")
            await asyncio.sleep(delay)

            try:
                await self.connect()
                logger.info(f"Reconnected after {self._retry_count} retries")

                # Flush queued messages
                while not self._queue.empty():
                    msg = self._queue.get_nowait()
                    try:
                        await self._ws.send(json.dumps(msg))
                    except Exception:
                        self._queue.put_nowait(msg)
                        break
            except Exception as exc:
                logger.warning(f"Reconnect attempt {self._retry_count} failed: {exc}")
                delay = min(delay * self.backoff_factor, self.max_delay)


# ── Convenience factory ────────────────────────────────────────────────────────


async def create_client(
    uri: str,
    token_provider: Callable[[], str],
    channels: Optional[List[str]] = None,
    **kwargs,
) -> WsClient:
    """
    Create and connect a WS client, optionally subscribing to channels.
    """
    client = WsClient(uri, token_provider, **kwargs)
    await client.connect()
    if channels:
        await client.subscribe(channels)
    return client
