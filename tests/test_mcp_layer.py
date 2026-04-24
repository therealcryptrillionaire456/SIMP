"""
Tests for the SIMP MCP layer: tool schema, registry, intent bridge, and transport.
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.mcp.tool_schema import SimpMCPTool, ToolParameter, ToolExample
from simp.mcp.tool_registry import ToolRegistry, tool_registry, mcp_tool


# ======================================================================
# Tool Schema Tests
# ======================================================================

class TestSimpMCPTool:
    def test_minimal_tool(self):
        """A tool can be created with just a name and description."""
        tool = SimpMCPTool(
            name="ping",
            description="Check if the agent is alive",
            input_schema={"type": "object", "properties": {}},
        )
        assert tool.name == "ping"
        assert tool.description == "Check if the agent is alive"

    def test_from_function(self):
        """from_function auto-builds a tool from a Python function signature."""

        def arb_scan(pair: str, min_spread_bps: float = 5.0) -> dict:
            """Scan for arbitrage opportunities on a trading pair."""
            return {"pair": pair, "opportunities": []}

        tool = SimpMCPTool.from_function(arb_scan)
        assert tool.name == "arb_scan"
        assert "arbitrage" in tool.description

    def test_to_mcp_list_item(self):
        """to_mcp_list_item returns the MCP wire format."""
        tool = SimpMCPTool(
            name="test_tool",
            description="Does something",
            input_schema={
                "type": "object",
                "properties": {"x": {"type": "number"}},
                "required": ["x"],
            },
        )
        item = tool.to_mcp_list_item()
        assert item["name"] == "test_tool"
        assert item["description"] == "Does something"
        assert item["inputSchema"]["properties"]["x"]["type"] == "number"

    def test_to_full_dict_includes_simp_metadata(self):
        """to_full_dict includes the x-simp metadata block."""
        tool = SimpMCPTool(
            name="quantum_scan",
            description="Scan with quantum enhancement",
            input_schema={},
            simp_intent_type="quantum_arbitrage_scan",
            simp_brp_sensitivity="high",
            simp_cost_per_call=0.01,
        )
        d = tool.to_full_dict()
        assert d["name"] == "quantum_scan"
        assert d["simp"]["intent_type"] == "quantum_arbitrage_scan"
        assert d["simp"]["brp_sensitivity"] == "high"
        assert d["simp"]["cost_per_call"] == 0.01

    def test_tool_parameter_json_schema(self):
        """ToolParameter produces valid JSON Schema properties."""
        param = ToolParameter(
            name="pairs",
            type="array",
            description="List of trading pairs",
            required=True,
        )
        prop = param.to_json_schema_property()
        assert prop["type"] == "array"
        assert "description" in prop

    def test_tool_with_examples(self):
        """Tools can carry examples."""
        example = ToolExample(
            name="basic_scan",
            arguments={"pair": "BTC-USD"},
            result="Found 3 opportunities",
        )
        tool = SimpMCPTool(
            name="scan",
            description="Scan",
            input_schema={},
            examples=[example],
        )
        assert len(tool.examples) == 1
        assert tool.examples[0].name == "basic_scan"

    def test_tool_hashing(self):
        """Tools are hashable by name."""
        t1 = SimpMCPTool(name="a", description="", input_schema={})
        t2 = SimpMCPTool(name="a", description="Different", input_schema={})
        t3 = SimpMCPTool(name="b", description="", input_schema={})
        assert hash(t1) == hash(t2)
        assert hash(t1) != hash(t3)


# ======================================================================
# Tool Registry Tests
# ======================================================================

class TestToolRegistry:
    def test_register_and_list(self):
        """Registering tools and listing them works."""
        reg = ToolRegistry(agent_id="test_agent")
        t1 = SimpMCPTool(name="tool_a", description="A", input_schema={})
        t2 = SimpMCPTool(name="tool_b", description="B", input_schema={})
        reg.register(t1)
        reg.register(t2)
        tools = reg.list_tools()
        assert len(tools) == 2
        assert {t.name for t in tools} == {"tool_a", "tool_b"}

    def test_get_tool(self):
        """get_tool returns a tool by name."""
        reg = ToolRegistry()
        t = SimpMCPTool(name="find_me", description="Target", input_schema={})
        reg.register(t)
        assert reg.get_tool("find_me") is t
        assert reg.get_tool("non_existent") is None

    def test_unregister(self):
        """unregister removes a tool."""
        reg = ToolRegistry()
        t = SimpMCPTool(name="remove_me", description="", input_schema={})
        reg.register(t)
        assert reg.unregister("remove_me") is True
        assert reg.get_tool("remove_me") is None
        assert reg.unregister("remove_me") is False

    def test_register_many(self):
        """register_many registers multiple tools at once."""
        reg = ToolRegistry()
        tools = [
            SimpMCPTool(name=f"tool_{i}", description="", input_schema={})
            for i in range(5)
        ]
        reg.register_many(tools)
        assert len(reg.list_tools()) == 5

    def test_list_mcp_items(self):
        """list_mcp_items returns MCP wire-format items."""
        reg = ToolRegistry()
        reg.register(SimpMCPTool(name="t1", description="One", input_schema={"type": "object"}))
        items = reg.list_mcp_items()
        assert len(items) == 1
        assert items[0]["name"] == "t1"

    def test_tool_names(self):
        """tool_names returns the set of registered tool names."""
        reg = ToolRegistry()
        reg.register(SimpMCPTool(name="x", description="", input_schema={}))
        reg.register(SimpMCPTool(name="y", description="", input_schema={}))
        assert reg.tool_names() == {"x", "y"}

    def test_to_dict(self):
        """to_dict returns agent metadata and tool list."""
        reg = ToolRegistry(agent_id="quantumarb")
        reg.register(SimpMCPTool(name="scan", description="Scan", input_schema={}))
        d = reg.to_dict()
        assert d["agent_id"] == "quantumarb"
        assert d["tool_count"] == 1
        assert "scan" in d["tools"]

    def test_thread_safety(self):
        """Registry operations are thread-safe (no crashes under contention)."""
        import threading

        reg = ToolRegistry()
        errors = []

        def register_worker():
            for i in range(100):
                try:
                    reg.register(SimpMCPTool(name=f"t_{i}", description="", input_schema={}))
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=register_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # At least some tools should be registered (might have duplicates from overwrites)
        assert len(reg.list_tools()) >= 100


# ======================================================================
# mcp_tool decorator tests
# ======================================================================

class TestMcpToolDecorator:
    def test_decorator_registers_tool(self):
        """The @mcp_tool decorator registers the function in the global registry."""
        test_reg = ToolRegistry(agent_id="test_decorator")

        # Temporarily replace global registry's internal dict
        # (cleaner: just test the decorator's effect on a local registry)
        from simp.mcp.tool_registry import mcp_tool as decorator_factory, tool_registry

        # Test with a fresh registry
        @decorator_factory(name="decorated_ping", description="Ping from decorator")
        def ping_handler(target: str = "all") -> dict:
            """Ping a target agent."""
            return {"status": "ok", "target": target}

        # The decorator registered in the global module-level registry
        retrieved = tool_registry.get_tool("decorated_ping")
        assert retrieved is not None
        assert retrieved.name == "decorated_ping"
        assert retrieved.description == "Ping from decorator"


# ======================================================================
# Intent Bridge Tests (unit-level, no broker required)
# ======================================================================

class TestIntentBridge:
    def test_register_intent_mapping(self):
        """Bridge can map MCP tool names to SIMP intent types."""
        from simp.mcp.intent_bridge import IntentBridge

        bridge = IntentBridge()
        bridge.register_intent_mapping("arb_scan", "quantum_arbitrage_scan", target_agent="quantumarb")

        assert bridge._tool_to_intent["arb_scan"] == "quantum_arbitrage_scan"
        assert bridge._intent_to_tool["quantum_arbitrage_scan"] == "arb_scan"

    def test_call_as_intent_returns_error_without_broker(self):
        """Without a broker configured, call_as_intent returns an error result."""
        from simp.mcp.intent_bridge import IntentBridge

        bridge = IntentBridge()
        bridge.register_intent_mapping("test_tool", "test_intent")
        result = bridge.call_as_intent("test_tool", {})
        assert result.success is False
        assert "Broker not configured" in (result.error or "")

    def test_call_as_intent_unknown_tool(self):
        """Calling an unmapped tool returns an error."""
        from simp.mcp.intent_bridge import IntentBridge

        bridge = IntentBridge()
        result = bridge.call_as_intent("nonexistent", {})
        assert result.success is False
        assert "No intent mapping" in (result.error or "")

    def test_tool_list_to_capabilities(self):
        """MCP tool list is converted to SIMP capability names."""
        from simp.mcp.intent_bridge import IntentBridge

        bridge = IntentBridge()
        tools = [
            {"name": "ping", "description": "Ping"},
            {"name": "scan", "description": "Scan"},
        ]
        caps = bridge.tool_list_to_capabilities(tools)
        assert "mcp:ping" in caps
        assert "mcp:scan" in caps

    def test_register_external_mcp_server(self, monkeypatch):
        """External MCP server tools are registered as local SimpMCPTool entries."""
        from simp.mcp.intent_bridge import IntentBridge

        bridge = IntentBridge()
        tool_list = [
            {
                "name": "get_price",
                "description": "Get current price",
                "inputSchema": {
                    "type": "object",
                    "properties": {"pair": {"type": "string"}},
                    "required": ["pair"],
                },
            }
        ]

        # Mock requests to avoid real HTTP calls
        bridge.register_external_mcp_server(
            server_id="external_mcp",
            base_url="http://localhost:9999",
            tool_list=tool_list,
        )

        all_tools = bridge.list_all_tools()
        names = {t.name for t in all_tools}
        assert "get_price" in names

        servers = bridge.get_registered_servers()
        assert "external_mcp" in servers
        assert servers["external_mcp"]["tool_count"] == 1


# ======================================================================
# MCP Transport Tests
# ======================================================================

class TestMCPTransport:
    def test_transport_name_and_priority(self):
        """MCP transport declares its name and priority."""
        from simp.mcp.transport import MCPTransport

        transport = MCPTransport()
        assert transport.transport_name == "mcp"
        assert transport.priority == 90

    def test_server_mode_start_stop(self):
        """Starting and stopping server mode works."""
        from simp.mcp.transport import MCPTransport

        transport = MCPTransport()
        assert transport.is_server is False

        transport.start_server(endpoint="/mcp/tools")
        assert transport.is_server is True

        transport.stop_server()
        assert transport.is_server is False

    def test_describe(self):
        """describe returns transport metadata."""
        from simp.mcp.transport import MCPTransport

        transport = MCPTransport()
        d = transport.describe()
        assert d["transport"] == "mcp"
        assert d["server_mode"] is False
        assert "external_servers" in d

    def test_send_unknown_server(self):
        """Sending to an unknown MCP server returns an error."""
        from simp.mcp.transport import MCPTransport

        transport = MCPTransport()
        result = transport.send({"intent_type": "ping"}, target="nonexistent")
        assert result["status"] == "error"
        assert "Unknown MCP server" in result["error"]

    def test_send_no_target(self):
        """Sending without a target returns an error."""
        from simp.mcp.transport import MCPTransport

        transport = MCPTransport()
        result = transport.send({"intent_type": "ping"})
        assert result["status"] == "error"
