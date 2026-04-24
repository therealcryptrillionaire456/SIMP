"""
SIMP MCP Bridge — Model Context Protocol Integration Layer

Makes every SIMP agent and intent type accessible as MCP-compatible tools,
resources, and prompts. Also allows SIMP agents to call external MCP servers
as if they were registered SIMP agents.
"""

from .tool_schema import SimpMCPTool, ToolParameter, ToolExample
from .tool_registry import ToolRegistry, tool_registry
from .intent_bridge import IntentBridge, intent_bridge

__all__ = [
    "SimpMCPTool",
    "ToolParameter",
    "ToolExample",
    "ToolRegistry",
    "tool_registry",
    "IntentBridge",
    "intent_bridge",
]
