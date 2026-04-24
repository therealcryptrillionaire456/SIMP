"""
SIMP MCP Tool Schema

Compatibility wrapper over the native SIMP tool surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from simp.native_tools import SimpTool, ToolExample, ToolParameter


class SimpMCPTool(SimpTool):
    """MCP-compatible constructor wrapper over ``SimpTool``."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Optional[callable] = None,
        parameters: Optional[List[ToolParameter]] = None,
        examples: Optional[List[ToolExample]] = None,
        intent_type: str = "",
        routing_hint: str = "auto",
        brp_sensitivity: str = "normal",
        cost_per_call: float = 0.0,
        timeout_seconds: int = 30,
        security_level: str = "signed",
        mesh_preferred: bool = False,
        cache_ttl: int = 0,
        execution_class: str = "native",
        invocation_mode: str = "native",
        simp_intent_type: str = "",
        simp_routing_hint: str = "auto",
        simp_brp_sensitivity: str = "normal",
        simp_cost_per_call: float = 0.0,
        simp_timeout_seconds: int = 30,
        simp_security_level: str = "signed",
        simp_mesh_preferred: bool = False,
        simp_cache_ttl: int = 0,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
            parameters=parameters or [],
            examples=examples or [],
            intent_type=intent_type or simp_intent_type,
            routing_hint=routing_hint if routing_hint != "auto" else simp_routing_hint,
            brp_sensitivity=brp_sensitivity if brp_sensitivity != "normal" else simp_brp_sensitivity,
            cost_per_call=cost_per_call if cost_per_call != 0.0 else simp_cost_per_call,
            timeout_seconds=timeout_seconds if timeout_seconds != 30 else simp_timeout_seconds,
            security_level=security_level if security_level != "signed" else simp_security_level,
            mesh_preferred=mesh_preferred or simp_mesh_preferred,
            cache_ttl=cache_ttl if cache_ttl != 0 else simp_cache_ttl,
            execution_class=execution_class,
            invocation_mode=invocation_mode,
        )


__all__ = ["SimpMCPTool", "ToolParameter", "ToolExample"]
