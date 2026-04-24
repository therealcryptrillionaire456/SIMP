"""
SIMP MCP Transport

Wraps the MCP bridge as a first-class SIMP transport, alongside HTTP, BLE,
Nostr, and Mesh.  This means SIMP agents can send intents *to* MCP servers
and receive intents *from* MCP clients, all through the standard transport
abstraction.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .tool_schema import SimpMCPTool
from .tool_registry import ToolRegistry
from .intent_bridge import IntentBridge, intent_bridge

logger = logging.getLogger("mcp.transport")


# ---------------------------------------------------------------------------
# MCP Transport — conforms to transport.py ABC pattern
# ---------------------------------------------------------------------------

class MCPTransport:
    """
    SIMP transport that communicates over MCP (Model Context Protocol).

    Provides two modes:

    1. **Server mode** — Exposes the local SIMP broker as an MCP endpoint
       that external MCP clients can discover and call.

    2. **Client mode** — Discovers external MCP servers and makes their
       tools available as routable SIMP intents.
    """

    transport_name = "mcp"
    priority = 90  # High priority — MCP is a preferred transport

    def __init__(self, bridge: Optional[IntentBridge] = None):
        self._bridge = bridge or intent_bridge
        self._server_mode = False
        self._mcp_endpoint: str = ""
        self._server_functions: Dict[str, Callable] = {}

    # ------------------------------------------------------------------
    # server mode: expose local SIMP as MCP endpoint
    # ------------------------------------------------------------------

    def start_server(
        self,
        endpoint: str = "",
        mcp_list_tools: Optional[Callable] = None,
        mcp_call_tool: Optional[Callable] = None,
    ) -> None:
        """
        Activate server mode.

        ``endpoint`` is the URL where external MCP clients reach this
        transport (e.g. ``/mcp/tools``).  If not provided, the transport
        relies on the broker's HTTP routes.

        ``mcp_list_tools`` and ``mcp_call_tool`` are the HTTP handlers
        that the ``HttpServer`` registers.  If not provided, defaults
        are used.
        """
        self._server_mode = True
        self._mcp_endpoint = endpoint or "/mcp"
        if mcp_list_tools:
            self._server_functions["list_tools"] = mcp_list_tools
        if mcp_call_tool:
            self._server_functions["call_tool"] = mcp_call_tool
        logger.info("MCP transport started in SERVER mode at '%s'", self._mcp_endpoint)

    def stop_server(self) -> None:
        self._server_mode = False
        self._server_functions.clear()
        logger.info("MCP transport server mode stopped")

    @property
    def is_server(self) -> bool:
        return self._server_mode

    # ------------------------------------------------------------------
    # client mode: connect to external MCP servers
    # ------------------------------------------------------------------

    def connect(self, server_id: str, base_url: str) -> bool:
        """
        Connect to an external MCP server, fetch its tool list, and register
        all tools as local ``SimpMCPTool`` entries.

        Returns True if the connection succeeded.
        """
        try:
            import requests as req
            resp = req.get(f"{base_url}/tools/list", timeout=15)
            resp.raise_for_status()
            tool_list = resp.json().get("tools", [])

            self._bridge.register_external_mcp_server(server_id, base_url, tool_list)
            logger.info("MCP transport connected to '%s' at %s (%d tools)", server_id, base_url, len(tool_list))
            return True

        except Exception as exc:
            logger.warning("MCP transport connect to '%s' failed: %s", server_id, exc)
            return False

    def disconnect(self, server_id: str) -> bool:
        """Disconnect from an external MCP server."""
        # Removal from bridge happens via intent_bridge internals
        logger.info("MCP transport disconnected from '%s'", server_id)
        return True

    # ------------------------------------------------------------------
    # standard transport interface
    # ------------------------------------------------------------------

    def send(
        self,
        payload: Dict[str, Any],
        target: str = "",
        **opts: Any,
    ) -> Dict[str, Any]:
        """
        Send a message to an external MCP server.

        If ``target`` is an MCP server ID registered via ``connect()``,
        the payload is delivered as an MCP ``tools/call`` request.
        """
        if not target:
            return {"status": "error", "error": "No target MCP server specified"}

        # Check if this is a registered external MCP server
        servers = self._bridge.get_registered_servers()
        if target not in servers:
            return {"status": "error", "error": f"Unknown MCP server '{target}'"}

        base_url = servers[target]["base_url"]
        tool_name = payload.get("tool_name", payload.get("intent_type", "unknown"))
        arguments = payload.get("params", payload.get("arguments", {}))

        try:
            import requests as req
            resp = req.post(
                f"{base_url}/tools/call",
                json={"name": tool_name, "arguments": arguments},
                timeout=30,
            )
            resp.raise_for_status()
            return {"status": "ok", "result": resp.json()}

        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def receive(self, **opts: Any) -> Optional[Dict[str, Any]]:
        """Not used in current design — MCP transport is pull-based."""
        return None

    # ------------------------------------------------------------------
    # utility
    # ------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        return {
            "transport": "mcp",
            "server_mode": self._server_mode,
            "endpoint": self._mcp_endpoint,
            "external_servers": self._bridge.get_registered_servers(),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

mcp_transport: MCPTransport = MCPTransport()
