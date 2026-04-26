"""
SIMP WebSocket Bridge — Option A

Standalone async WebSocket server that sits alongside the Flask HTTP broker.
Authenticates via JWT, bridges WS messages to the broker via HTTP.

Architecture:
  Agent ──WS──► :5556 WS Bridge ──HTTP──► :5555 Broker

Protocol:
  - Connect: send {"type": "auth", "token": "<jwt>"}
  - Send intent: send {"type": "intent", "intent": {...intent_data...}}
  - Subscribe: send {"type": "subscribe", "channels": ["channel1", "channel2"]}
  - Server pushes: JSON with "type": "push" and intent payload
  - Heartbeat: send {"type": "ping"} → {"type": "pong"}
  - Close: send {"type": "close"} or TCP close

JWT claims must include "sub" (agent_id) and optionally "capabilities".
"""

import asyncio
import json
import logging
import os
import ssl
import time
from dataclasses import dataclass
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol, serve

logger = logging.getLogger("SIMP.WS.Bridge")

# ── Channel ACL definitions ───────────────────────────────────────────────────

# Reserved channels that require specific capabilities
CHANNEL_CAPABILITY_REQUIREMENTS: Dict[str, List[str]] = {
    "signals.trading": ["trade"],
    "signals.alpha": ["trade", "analyze"],
    "admin": ["admin"],
    "intent.routed": ["route"],
    "system": ["admin"],
}

# Channels that are open to all authenticated agents
OPEN_CHANNELS: Set[str] = {
    "alerts",
    "intent.routed",
    "heartbeat",
}

# Wildcard patterns (e.g., "intent.routed.*")
WILDCARD_PATTERNS = True

# ── JWT verification (reuses jwt_auth.py patterns) ──────────────────────────
from simp.server.jwt_auth import verify_jwt, get_jwt_config

# ── Broker HTTP client (forwards intents via HTTP) ───────────────────────────

import httpx


# ═══════════════════════════════════════════════════════════════════════════════
# WS Bridge
# ═══════════════════════════════════════════════════════════════════════════════


class WsBridge:
    """
    Standalone WebSocket bridge for SIMP agents.

    Runs on a configurable port (default :5556) as an asyncio server.
    Authenticates WebSocket connections using JWT tokens from jwt_auth.py.
    Forwards agent intents to the SIMP broker via HTTP.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5556,
        broker_url: str = "http://127.0.0.1:5555",
        ws_ping_interval: float = 30.0,
        ws_ping_timeout: float = 10.0,
    ):
        self.host = host
        self.port = int(os.environ.get("SIMP_WS_PORT", port))
        self.broker_url = os.environ.get("SIMP_BROKER_URL", broker_url)
        self.ws_ping_interval = float(
            os.environ.get("SIMP_WS_PING_INTERVAL", ws_ping_interval)
        )
        self.ws_ping_timeout = float(
            os.environ.get("SIMP_WS_PING_TIMEOUT", ws_ping_timeout)
        )

        # Sprint 85 — TLS termination (wss://)
        self.ssl_context: Optional[ssl.SSLContext] = None
        tls_cert = os.environ.get("SIMP_WS_TLS_CERT", "")
        tls_key = os.environ.get("SIMP_WS_TLS_KEY", "")
        if tls_cert and tls_key:
            try:
                self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                self.ssl_context.load_cert_chain(tls_cert, tls_key)
                logger.info(f"TLS enabled: wss://{self.host}:{self.port}")
            except Exception as exc:
                logger.error(f"Failed to load TLS cert/key: {exc}")
                self.ssl_context = None

        # Sprint 85 — Rate limiting per agent
        self._rate_limit = int(os.environ.get("SIMP_WS_RATE_LIMIT", 100))  # intents/sec
        self._rate_window = float(os.environ.get("SIMP_WS_RATE_WINDOW", 1.0))  # seconds
        self._intent_timestamps: Dict[str, List[float]] = defaultdict(list)

        # Connected agents: agent_id -> (websocket, channels)
        self._connections: Dict[str, "WsConnection"] = {}
        # Channel subscribers: channel_name -> set of agent_ids
        self._channels: Dict[str, Set[str]] = {}
        # Reverse lookup: ws -> agent_id
        self._ws_to_agent: Dict[int, str] = {}

        # HTTP client for forwarding intents to broker
        self._http: Optional[httpx.AsyncClient] = None
        # The running asyncio server
        self._server: Optional[websockets.WebSocketServer] = None
        # Background task for broker polling (push mode)
        self._poll_task: Optional[asyncio.Task] = None

        # Stats
        self.stats = {
            "connections_total": 0,
            "connections_active": 0,
            "intents_forwarded": 0,
            "pushes_sent": 0,
            "auth_failures": 0,
            "errors": 0,
        }

        logger.info(
            f"WsBridge configured: {self.host}:{self.port} → broker {self.broker_url}"
        )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self):
        """Start the WebSocket server."""
        self._http = httpx.AsyncClient(timeout=30.0)
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            ping_interval=self.ws_ping_interval,
            ping_timeout=self.ws_ping_timeout,
            ssl=self.ssl_context,
        )
        logger.info(f"WsBridge listening on ws://{self.host}:{self.port}")
        return self

    async def stop(self):
        """Gracefully shut down the WebSocket server."""
        logger.info("WsBridge shutting down...")

        # Close all connections
        for agent_id in list(self._connections.keys()):
            try:
                ws = self._connections[agent_id].ws
                await ws.close(1001, "Server shutting down")
            except Exception:
                pass

        self._connections.clear()
        self._channels.clear()
        self._ws_to_agent.clear()

        # Cancel poll task
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Close HTTP client
        if self._http:
            await self._http.aclose()

        logger.info("WsBridge shut down complete")

    async def serve_forever(self):
        """Run until cancelled."""
        try:
            await self._server.wait_closed()
        except asyncio.CancelledError:
            await self.stop()

    # ── Connection Handler ───────────────────────────────────────────────────

    async def _handle_connection(self, ws: WebSocketServerProtocol):
        """Handle a new WebSocket connection lifecycle."""
        agent_id: Optional[str] = None
        connection_id = id(ws)

        logger.info(f"New WS connection from {ws.remote_address}")
        self.stats["connections_total"] += 1
        self.stats["connections_active"] += 1

        try:
            # Wait for auth message
            raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
            msg = self._parse_message(raw)
            if not msg or msg.get("type") != "auth":
                await ws.send(json.dumps({
                    "type": "error",
                    "code": "AUTH_REQUIRED",
                    "message": "First message must be auth with JWT token",
                }))
                await ws.close(4001, "Auth required")
                self.stats["auth_failures"] += 1
                return

            # Verify JWT
            token = msg.get("token", "")
            claims = self._verify_token(token)
            if not claims:
                await ws.send(json.dumps({
                    "type": "error",
                    "code": "AUTH_FAILED",
                    "message": "Invalid or expired JWT token",
                }))
                await ws.close(4001, "Auth failed")
                self.stats["auth_failures"] += 1
                return

            agent_id = claims.get("sub")
            if not agent_id:
                await ws.send(json.dumps({
                    "type": "error",
                    "code": "AUTH_FAILED",
                    "message": "JWT missing 'sub' claim",
                }))
                await ws.close(4001, "Auth failed")
                self.stats["auth_failures"] += 1
                return

            # Register connection
            capabilities = claims.get("capabilities", [])
            conn = WsConnection(
                ws=ws,
                agent_id=agent_id,
                capabilities=capabilities,
                connected_at=time.time(),
            )
            self._connections[agent_id] = conn
            self._ws_to_agent[connection_id] = agent_id

            logger.info(f"Agent '{agent_id}' authenticated via WS (caps={capabilities})")

            await ws.send(json.dumps({
                "type": "auth_ok",
                "agent_id": agent_id,
                "capabilities": capabilities,
            }))

            # Message loop
            async for raw in ws:
                msg = self._parse_message(raw)
                if not msg:
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))

                elif msg_type == "intent":
                    await self._handle_intent(agent_id, msg.get("intent", {}))

                elif msg_type == "subscribe":
                    channels = msg.get("channels", [])
                    await self._handle_subscribe(agent_id, channels)

                elif msg_type == "unsubscribe":
                    channels = msg.get("channels", [])
                    await self._handle_unsubscribe(agent_id, channels)

                elif msg_type == "close":
                    break

                else:
                    await ws.send(json.dumps({
                        "type": "error",
                        "code": "UNKNOWN_TYPE",
                        "message": f"Unknown message type: {msg_type}",
                    }))

        except asyncio.TimeoutError:
            logger.warning(f"WS connection timed out waiting for auth: {ws.remote_address}")
            self.stats["auth_failures"] += 1
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as exc:
            logger.error(f"WS connection error: {exc}")
            self.stats["errors"] += 1
        finally:
            # Cleanup
            if agent_id:
                self._connections.pop(agent_id, None)
                # Remove from all channels
                for channel in list(self._channels.keys()):
                    self._channels[channel].discard(agent_id)
                    if not self._channels[channel]:
                        del self._channels[channel]
                self._ws_to_agent.pop(connection_id, None)
                self.stats["connections_active"] -= 1
                logger.info(f"Agent '{agent_id}' disconnected (active: {self.stats['connections_active']})")
            # Cleanup _ws_to_agent even if auth never completed
            elif connection_id in self._ws_to_agent:
                self._ws_to_agent.pop(connection_id, None)
                self.stats["connections_active"] -= 1

    # ── Rate Limiting ─────────────────────────────────────────────────────

    def _check_rate_limit(self, agent_id: str) -> bool:
        """Return True if agent is within rate limit, False if exceeded."""
        now = time.time()
        window_start = now - self._rate_window
        # Prune old timestamps
        self._intent_timestamps[agent_id] = [
            ts for ts in self._intent_timestamps[agent_id] if ts > window_start
        ]
        if len(self._intent_timestamps[agent_id]) >= self._rate_limit:
            return False
        self._intent_timestamps[agent_id].append(now)
        return True

    # ── Message Handlers ────────────────────────────────────────────────────

    async def _handle_intent(self, agent_id: str, intent_data: Dict[str, Any]):
        """Forward an intent from WS to the broker via HTTP."""
        if not intent_data:
            return

        # Rate limiting
        if not self._check_rate_limit(agent_id):
            logger.warning(f"Rate limit exceeded for agent '{agent_id}'")
            await self._connections[agent_id].ws.send(json.dumps({
                "type": "error",
                "code": "RATE_LIMITED",
                "message": f"Rate limit exceeded ({self._rate_limit} intents per {self._rate_window}s)",
            }))
            return

        # Enrich with source info
        intent_data["source"] = intent_data.get("source", agent_id)
        intent_data["transport"] = "websocket"

        try:
            resp = await self._http.post(
                f"{self.broker_url}/intents",
                json=intent_data,
                headers={
                    "Content-Type": "application/json",
                    "X-Transport": "websocket",
                    "X-Agent-Id": agent_id,
                },
                timeout=10.0,
            )
            self.stats["intents_forwarded"] += 1

            # Forward response back to agent
            if resp.status_code < 500:
                try:
                    result = resp.json()
                    await self._connections[agent_id].ws.send(json.dumps({
                        "type": "intent_result",
                        "status": resp.status_code,
                        "result": result,
                    }))
                except Exception:
                    await self._connections[agent_id].ws.send(json.dumps({
                        "type": "intent_result",
                        "status": resp.status_code,
                        "result": {"raw": resp.text[:4096]},
                    }))
            else:
                await self._connections[agent_id].ws.send(json.dumps({
                    "type": "error",
                    "code": "BROKER_ERROR",
                    "message": f"Broker returned {resp.status_code}",
                }))

        except httpx.RequestError as exc:
            logger.error(f"Broker HTTP error forwarding intent from {agent_id}: {exc}")
            self.stats["errors"] += 1
            try:
                await self._connections[agent_id].ws.send(json.dumps({
                    "type": "error",
                    "code": "BROKER_UNREACHABLE",
                    "message": f"Cannot reach broker: {exc}",
                }))
            except Exception:
                pass

    async def _handle_subscribe(self, agent_id: str, channels: List[str]):
        """Subscribe an agent to one or more channels, checking ACLs."""
        if agent_id not in self._connections:
            return
        conn = self._connections[agent_id]
        allowed, denied = self._filter_allowed_channels(agent_id, channels, conn.capabilities)

        if denied:
            await conn.ws.send(json.dumps({
                "type": "error",
                "code": "CHANNEL_DENIED",
                "message": f"Access denied to channels: {denied}",
                "denied": denied,
            }))

        for channel in allowed:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(agent_id)
            logger.info(f"Agent '{agent_id}' subscribed to channel '{channel}'")

        if allowed:
            await conn.ws.send(json.dumps({
                "type": "subscribed",
                "channels": allowed,
                "denied": denied if denied else None,
            }))

    async def _handle_unsubscribe(self, agent_id: str, channels: List[str]):
        """Unsubscribe an agent from one or more channels."""
        if agent_id not in self._connections:
            return
        for channel in channels:
            if channel in self._channels:
                self._channels[channel].discard(agent_id)
                if not self._channels[channel]:
                    del self._channels[channel]

        await self._connections[agent_id].ws.send(json.dumps({
            "type": "unsubscribed",
            "channels": channels,
        }))

    # ── Push (broker → agent) ───────────────────────────────────────────────

    async def push_to_channel(self, channel: str, payload: Dict[str, Any]):
        """Push a message to all agents subscribed to a channel."""
        if channel not in self._channels:
            return

        dead_agents = []
        for agent_id in self._channels[channel]:
            conn = self._connections.get(agent_id)
            if not conn:
                dead_agents.append(agent_id)
                continue
            try:
                await conn.ws.send(json.dumps({
                    "type": "push",
                    "channel": channel,
                    "data": payload,
                    "timestamp": time.time(),
                }))
                self.stats["pushes_sent"] += 1
            except Exception:
                dead_agents.append(agent_id)

        # Cleanup dead subscriptions
        for agent_id in dead_agents:
            self._channels[channel].discard(agent_id)
            self._connections.pop(agent_id, None)
        if not self._channels[channel]:
            del self._channels[channel]

    async def push_to_agent(self, agent_id: str, payload: Dict[str, Any]):
        """Push a message directly to a specific agent."""
        conn = self._connections.get(agent_id)
        if not conn:
            logger.warning(f"Cannot push to '{agent_id}': not connected")
            return
        try:
            await conn.ws.send(json.dumps({
                "type": "push",
                "target": agent_id,
                "data": payload,
                "timestamp": time.time(),
            }))
            self.stats["pushes_sent"] += 1
        except Exception as exc:
            logger.error(f"Error pushing to '{agent_id}': {exc}")
            self._connections.pop(agent_id, None)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _parse_message(self, raw: Any) -> Optional[Dict[str, Any]]:
        """Parse a raw WebSocket message as JSON."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(f"Invalid JSON message: {exc}")
            return None

    def _verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a JWT token and return claims, or None on failure."""
        cfg = get_jwt_config()
        if not cfg.enabled or not cfg.secret:
            logger.warning("JWT not configured — WS auth disabled")
            return None

        result = verify_jwt(token)
        if result is None:
            return None
        # verify_jwt returns claims dict directly (not nested under "claims")
        return result

    def _check_channel_permission(self, agent_id: str, channel: str, capabilities: List[str]) -> bool:
        """Check if an agent has permission to subscribe to a channel."""
        # Open channels are accessible to all authenticated agents
        if channel in OPEN_CHANNELS:
            return True

        # Check capability requirements
        required_caps = CHANNEL_CAPABILITY_REQUIREMENTS.get(channel, [])
        if required_caps:
            return all(cap in capabilities for cap in required_caps)

        # Pattern-based matching (e.g., "intent.routed.*")
        if "." in channel:
            prefix = channel.rsplit(".", 1)[0]
            required_caps = CHANNEL_CAPABILITY_REQUIREMENTS.get(prefix + ".*", 
                CHANNEL_CAPABILITY_REQUIREMENTS.get(prefix, []))
            if required_caps:
                return all(cap in capabilities for cap in required_caps)

        # Default: allow if no specific requirements
        return True

    def _filter_allowed_channels(self, agent_id: str, channels: List[str], 
                                   capabilities: List[str]) -> tuple:
        """Filter channels to only those the agent can access. Returns (allowed, denied)."""
        allowed = []
        denied = []
        for ch in channels:
            if self._check_channel_permission(agent_id, ch, capabilities):
                allowed.append(ch)
            else:
                denied.append(ch)
                logger.warning(f"Agent '{agent_id}' denied access to channel '{ch}'")
        return allowed, denied

    def get_metrics(self) -> Dict[str, Any]:
        """Return metrics in Prometheus-compatible format."""
        return {
            "ws_bridge_connections_active": self.stats["connections_active"],
            "ws_bridge_connections_total": self.stats["connections_total"],
            "ws_bridge_intents_forwarded": self.stats["intents_forwarded"],
            "ws_bridge_pushes_sent": self.stats["pushes_sent"],
            "ws_bridge_auth_failures": self.stats["auth_failures"],
            "ws_bridge_errors": self.stats["errors"],
            "ws_bridge_channels_total": len(self._channels),
            "ws_bridge_agents_connected": len(self._connections),
        }

    def get_prometheus_text(self) -> str:
        """Return Prometheus-formatted metrics text."""
        m = self.get_metrics()
        lines = [
            "# HELP ws_bridge_connections_active Number of active WebSocket connections",
            "# TYPE ws_bridge_connections_active gauge",
            f"ws_bridge_connections_active {m['ws_bridge_connections_active']}",
            "# HELP ws_bridge_connections_total Total WebSocket connections",
            "# TYPE ws_bridge_connections_total counter",
            f"ws_bridge_connections_total {m['ws_bridge_connections_total']}",
            "# HELP ws_bridge_intents_forwarded Total intents forwarded to broker",
            "# TYPE ws_bridge_intents_forwarded counter",
            f"ws_bridge_intents_forwarded {m['ws_bridge_intents_forwarded']}",
            "# HELP ws_bridge_pushes_sent Total push messages sent",
            "# TYPE ws_bridge_pushes_sent counter",
            f"ws_bridge_pushes_sent {m['ws_bridge_pushes_sent']}",
            "# HELP ws_bridge_auth_failures Total authentication failures",
            "# TYPE ws_bridge_auth_failures counter",
            f"ws_bridge_auth_failures {m['ws_bridge_auth_failures']}",
            "# HELP ws_bridge_errors Total errors",
            "# TYPE ws_bridge_errors counter",
            f"ws_bridge_errors {m['ws_bridge_errors']}",
            "# HELP ws_bridge_channels_total Number of active channels",
            "# TYPE ws_bridge_channels_total gauge",
            f"ws_bridge_channels_total {m['ws_bridge_channels_total']}",
            "# HELP ws_bridge_agents_connected Number of connected agents",
            "# TYPE ws_bridge_agents_connected gauge",
            f"ws_bridge_agents_connected {m['ws_bridge_agents_connected']}",
        ]
        return "\n".join(lines) + "\n"

    @property
    def connected_agents(self) -> Set[str]:
        """Return set of currently connected agent IDs."""
        return set(self._connections.keys())

    @property
    def connected_count(self) -> int:
        """Return number of currently connected agents."""
        return len(self._connections)


# ═══════════════════════════════════════════════════════════════════════════════
# Connection Tracking
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class WsConnection:
    """Represents an authenticated WebSocket connection from an agent."""
    ws: WebSocketServerProtocol
    agent_id: str
    capabilities: List[str]
    connected_at: float

    @property
    def uptime(self) -> float:
        return time.time() - self.connected_at


# ═══════════════════════════════════════════════════════════════════════════════
# Run standalone
# ═══════════════════════════════════════════════════════════════════════════════


async def main():
    """Run the WS bridge standalone."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    bridge = WsBridge()
    await bridge.start()
    logger.info(f"WS Bridge running on ws://{bridge.host}:{bridge.port}")
    await bridge.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
