"""
SIMP MCP Tool Registry

Compatibility wrapper over the native SIMP tool registry.
"""

from __future__ import annotations

from simp.native_tools import (
    NATIVE_TOOL_REGISTRIES,
    NativeToolRegistry,
    native_tool,
    native_tool_registry,
)

TOOL_REGISTRIES = NATIVE_TOOL_REGISTRIES
ToolRegistry = NativeToolRegistry
tool_registry = native_tool_registry
mcp_tool = native_tool

__all__ = [
    "TOOL_REGISTRIES",
    "ToolRegistry",
    "tool_registry",
    "mcp_tool",
]
