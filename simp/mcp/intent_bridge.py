"""
SIMP MCP Intent Bridge

Translates between the MCP tool model and SIMP's native intent system.
- MCP ``tools/call``  →  SIMP ``route_intent()``
- SIMP intent response → MCP tool result

This is the glue that makes *any SIMP agent callable as an MCP tool* and
*any MCP server appear as a SIMP agent*.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .tool_schema import SimpMCPTool
from .tool_registry import ToolRegistry

logger = logging.getLogger("mcp.bridge")


# ---------------------------------------------------------------------------
# Translation result
# ---------------------------------------------------------------------------

@dataclass
class BridgeCallResult:
    """Result of bridging an MCP tool call into a SIMP intent."""
    success: bool
    mcp_tool_name: str
    simp_intent_type: str
    target_agent: str = ""
    intent_id: str = ""
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Intent Bridge
# ---------------------------------------------------------------------------

class IntentBridge:
    """
    Translate between MCP tool calls and SIMP intents.

    Two-direction:

    1. **Inbound** — External MCP client calls a tool → bridge translates
       to a SIMP intent and routes it through the broker.

    2. **Outbound** — A SIMP agent discovers an external MCP server →
       bridge registers the MCP server's tools as if they were local SIMP
       capabilities.
    """

    def __init__(self, broker_ref: Optional[Any] = None):
        self._broker = broker_ref          # SimpBroker instance
        self._lock = threading.Lock()
        self._tool_to_intent: Dict[str, str] = {}            # tool_name → intent_type
        self._intent_to_tool: Dict[str, str] = {}            # intent_type → tool_name
        self._agent_tool_registries: Dict[str, ToolRegistry] = {}
        self._external_mcp_servers: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    def set_broker(self, broker: Any) -> None:
        self._broker = broker

    # ------------------------------------------------------------------
    # inbound: MCP tools/call → SIMP route_intent
    # ------------------------------------------------------------------

    def register_intent_mapping(
        self,
        mcp_tool_name: str,
        intent_type: str,
        target_agent: str = "auto",
    ) -> None:
        """
        Declare that an MCP tool name maps to a SIMP intent type.

        When an MCP client calls ``tools/call`` for this tool, the
        bridge will create an intent of the given ``intent_type`` and
        route it to ``target_agent``.
        """
        with self._lock:
            self._tool_to_intent[mcp_tool_name] = intent_type
            self._intent_to_tool[intent_type] = mcp_tool_name

    def call_as_intent(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        source_agent: str = "mcp_bridge",
    ) -> BridgeCallResult:
        """
        Execute an MCP tool by routing a SIMP intent through the broker.

        Steps:
        1. Look up the intent type for this tool name
        2. Build a ``CanonicalIntent`` (or equivalent dict)
        3. Call ``self._broker.route_intent(...)``
        4. Translate the response back into a tool result
        """
        with self._lock:
            intent_type = self._tool_to_intent.get(tool_name, "")
            if not intent_type:
                return BridgeCallResult(
                    success=False,
                    mcp_tool_name=tool_name,
                    simp_intent_type="",
                    error=f"No intent mapping for tool '{tool_name}'",
                )

        if self._broker is None:
            return BridgeCallResult(
                success=False,
                mcp_tool_name=tool_name,
                simp_intent_type=intent_type,
                error="Broker not configured",
            )

        # Build a simplified intent dict (same shape as broker expects)
        intent = {
            "intent_type": intent_type,
            "source_agent": source_agent,
            "target_agent": "auto",
            "params": arguments,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }

        import time
        t0 = time.monotonic()

        try:
            response = self._broker.route_intent(intent)

            if response is None:
                result = BridgeCallResult(
                    success=False,
                    mcp_tool_name=tool_name,
                    simp_intent_type=intent_type,
                    error="Broker returned None",
                    duration_ms=(time.monotonic() - t0) * 1000,
                )
            elif isinstance(response, dict) and response.get("status") == "error":
                result = BridgeCallResult(
                    success=False,
                    mcp_tool_name=tool_name,
                    simp_intent_type=intent_type,
                    error=response.get("error", "Unknown error"),
                    duration_ms=(time.monotonic() - t0) * 1000,
                )
            else:
                result = BridgeCallResult(
                    success=True,
                    mcp_tool_name=tool_name,
                    simp_intent_type=intent_type,
                    intent_id=response.intent_id if hasattr(response, "intent_id") else "",
                    result=response,
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

        except Exception as exc:
            result = BridgeCallResult(
                success=False,
                mcp_tool_name=tool_name,
                simp_intent_type=intent_type,
                error=str(exc),
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        logger.info(
            "MCP call '%s' → intent '%s': %s (%.1f ms)",
            tool_name, intent_type,
            "OK" if result.success else f"FAIL: {result.error}",
            result.duration_ms,
        )
        return result

    # ------------------------------------------------------------------
    # inbound: translate MCP tool list → SIMP capability list
    # ------------------------------------------------------------------

    def tool_list_to_capabilities(self, tools: List[Dict[str, Any]]) -> List[str]:
        """Extract SIMP capability names from an MCP tool list."""
        caps = []
        for t in tools:
            name = t.get("name", "")
            if name:
                caps.append(f"mcp:{name}")
        return caps

    # ------------------------------------------------------------------
    # outbound: register an external MCP server's tools as SIMP agent
    # ------------------------------------------------------------------

    def register_external_mcp_server(
        self,
        server_id: str,
        base_url: str,
        tool_list: List[Dict[str, Any]],
    ) -> None:
        """
        Register an external MCP server as if it were a SIMP agent.

        Each tool from the MCP server becomes a local ``SimpMCPTool``
        whose handler delegates to ``tools/call`` over HTTP.
        """
        from .tool_schema import SimpMCPTool, ToolParameter

        registry = ToolRegistry(agent_id=server_id)

        for t in tool_list:
            name = t.get("name", "")
            desc = t.get("description", "")
            schema = t.get("inputSchema", {})

            # Build a handler that proxies to the external MCP server
            def _make_proxy(tool_name: str, url: str):
                def _proxy(**kwargs: Any) -> Any:
                    import requests as req
                    resp = req.post(
                        f"{url}/tools/call",
                        json={"name": tool_name, "arguments": kwargs},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    return resp.json()
                return _proxy

            tool = SimpMCPTool(
                name=name,
                description=desc,
                input_schema=schema,
                handler=_make_proxy(name, base_url),
            )
            registry.register(tool)

        with self._lock:
            self._agent_tool_registries[server_id] = registry
            self._external_mcp_servers[server_id] = {
                "base_url": base_url,
                "tool_count": len(tool_list),
            }

        logger.info("Registered external MCP server '%s' (%d tools)", server_id, len(tool_list))

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------

    def list_all_tools(self) -> List[SimpMCPTool]:
        """Aggregate tools from all registered sources."""
        all_tools: Dict[str, SimpMCPTool] = {}

        # Local agent registries
        for registry in self._agent_tool_registries.values():
            for t in registry.list_tools():
                all_tools[t.name] = t

        return list(all_tools.values())

    def list_all_mcp_items(self) -> List[Dict[str, Any]]:
        return [t.to_mcp_list_item() for t in self.list_all_tools()]

    def get_registered_servers(self) -> Dict[str, Any]:
        return dict(self._external_mcp_servers)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

intent_bridge: IntentBridge = IntentBridge()
