"""
SIMP Native Tool Surface

Native-first tool descriptors and registries for internal SIMP agents.
The MCP layer is a compatibility facade over this module, not the source
of truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import inspect
import logging
import threading
from typing import Any, Callable, ClassVar, Dict, List, Optional, Set

logger = logging.getLogger("simp.native_tools")


@dataclass
class ToolParameter:
    """A single parameter of a native SIMP tool."""

    name: str
    type: str
    description: str = ""
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None

    def to_json_schema_property(self) -> Dict[str, Any]:
        prop: Dict[str, Any] = {"type": self.type, "description": self.description}
        if self.default is not None:
            prop["default"] = self.default
        if self.enum is not None:
            prop["enum"] = self.enum
        return prop


@dataclass
class ToolExample:
    """An example invocation + result for a tool."""

    name: str
    arguments: Dict[str, Any]
    result: str = ""


@dataclass
class SimpTool:
    """
    Native SIMP tool descriptor.

    The fields remain wire-compatible with the MCP tool shape so external
    adapters can re-export the same tool without redefining it.
    """

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Optional[Callable[..., Any]] = None
    parameters: List[ToolParameter] = field(default_factory=list)
    examples: List[ToolExample] = field(default_factory=list)
    intent_type: str = ""
    routing_hint: str = "auto"
    brp_sensitivity: str = "normal"
    cost_per_call: float = 0.0
    timeout_seconds: int = 30
    security_level: str = "signed"
    mesh_preferred: bool = False
    cache_ttl: int = 0
    execution_class: str = "native"
    invocation_mode: str = "native"

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        *,
        name: str = "",
        description: str = "",
        intent_type: str = "",
    ) -> "SimpTool":
        """Auto-build a native tool descriptor from a Python function."""
        sig = inspect.signature(func)
        params: List[ToolParameter] = []
        required: List[str] = []

        for pname, param in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            ptype = "string"
            if param.annotation is not inspect.Parameter.empty:
                ann = str(param.annotation)
                if "int" in ann or "float" in ann:
                    ptype = "number"
                elif "bool" in ann:
                    ptype = "boolean"
                elif "dict" in ann or "Dict" in ann:
                    ptype = "object"
                elif "list" in ann or "List" in ann or "tuple" in ann:
                    ptype = "array"
            required_flag = param.default is inspect.Parameter.empty
            if required_flag:
                required.append(pname)
            params.append(
                ToolParameter(
                    name=pname,
                    type=ptype,
                    required=required_flag,
                    default=None if required_flag else param.default,
                )
            )

        input_schema = {
            "type": "object",
            "properties": {p.name: p.to_json_schema_property() for p in params},
            "required": required,
        }

        return cls(
            name=name or func.__name__,
            description=description or (func.__doc__ or "").strip(),
            input_schema=input_schema,
            handler=func,
            parameters=params,
            intent_type=intent_type or name or func.__name__,
        )

    # MCP compatibility aliases
    @property
    def simp_intent_type(self) -> str:
        return self.intent_type

    @simp_intent_type.setter
    def simp_intent_type(self, value: str) -> None:
        self.intent_type = value

    @property
    def simp_routing_hint(self) -> str:
        return self.routing_hint

    @simp_routing_hint.setter
    def simp_routing_hint(self, value: str) -> None:
        self.routing_hint = value

    @property
    def simp_brp_sensitivity(self) -> str:
        return self.brp_sensitivity

    @simp_brp_sensitivity.setter
    def simp_brp_sensitivity(self, value: str) -> None:
        self.brp_sensitivity = value

    @property
    def simp_cost_per_call(self) -> float:
        return self.cost_per_call

    @simp_cost_per_call.setter
    def simp_cost_per_call(self, value: float) -> None:
        self.cost_per_call = value

    @property
    def simp_timeout_seconds(self) -> int:
        return self.timeout_seconds

    @simp_timeout_seconds.setter
    def simp_timeout_seconds(self, value: int) -> None:
        self.timeout_seconds = value

    @property
    def simp_security_level(self) -> str:
        return self.security_level

    @simp_security_level.setter
    def simp_security_level(self, value: str) -> None:
        self.security_level = value

    @property
    def simp_mesh_preferred(self) -> bool:
        return self.mesh_preferred

    @simp_mesh_preferred.setter
    def simp_mesh_preferred(self, value: bool) -> None:
        self.mesh_preferred = value

    @property
    def simp_cache_ttl(self) -> int:
        return self.cache_ttl

    @simp_cache_ttl.setter
    def simp_cache_ttl(self, value: int) -> None:
        self.cache_ttl = value

    def to_native_descriptor(self) -> Dict[str, Any]:
        """Return the internal native contract shape for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "intent_type": self.intent_type,
            "routing_hint": self.routing_hint,
            "brp_sensitivity": self.brp_sensitivity,
            "timeout_seconds": self.timeout_seconds,
            "security_level": self.security_level,
            "mesh_preferred": self.mesh_preferred,
            "cache_ttl": self.cache_ttl,
            "execution_class": self.execution_class,
            "invocation_mode": self.invocation_mode,
            "parameters": [asdict(p) for p in self.parameters],
            "examples": [asdict(e) for e in self.examples],
        }

    def to_mcp_list_item(self) -> Dict[str, Any]:
        """Return the MCP wire-format tool list item."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    def to_simp_metadata(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "routing_hint": self.routing_hint,
            "brp_sensitivity": self.brp_sensitivity,
            "cost_per_call": self.cost_per_call,
            "timeout_seconds": self.timeout_seconds,
            "security_level": self.security_level,
            "mesh_preferred": self.mesh_preferred,
            "cache_ttl": self.cache_ttl,
            "execution_class": self.execution_class,
            "invocation_mode": self.invocation_mode,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("handler", None)
        d["simp"] = self.to_simp_metadata()
        return d

    def __hash__(self) -> int:
        return hash(self.name)


NATIVE_TOOL_REGISTRIES: Dict[str, "NativeToolRegistry"] = {}
_REGISTRY_LOCK = threading.Lock()


class NativeToolRegistry:
    """Thread-safe registry for a single agent's native SIMP tools."""

    _registry_map: ClassVar[Dict[str, "NativeToolRegistry"]] = NATIVE_TOOL_REGISTRIES

    def __init__(self, agent_id: str = ""):
        self._agent_id = agent_id
        self._lock = threading.Lock()
        self._tools: Dict[str, SimpTool] = {}
        if agent_id:
            with _REGISTRY_LOCK:
                self._registry_map[agent_id] = self

    def register(self, tool: SimpTool) -> None:
        with self._lock:
            if tool.name in self._tools:
                logger.debug("Tool %s re-registered for agent %s", tool.name, self._agent_id)
            self._tools[tool.name] = tool

    def register_many(self, tools: List[SimpTool]) -> None:
        with self._lock:
            for tool in tools:
                self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._tools.pop(name, None) is not None

    def get_tool(self, name: str) -> Optional[SimpTool]:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> List[SimpTool]:
        with self._lock:
            return list(self._tools.values())

    def list_native_items(self) -> List[Dict[str, Any]]:
        return [tool.to_native_descriptor() for tool in self.list_tools()]

    def list_mcp_items(self) -> List[Dict[str, Any]]:
        return [tool.to_mcp_list_item() for tool in self.list_tools()]

    def tool_names(self) -> Set[str]:
        with self._lock:
            return set(self._tools.keys())

    def invoke(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        tool = self.get_tool(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in agent '{self._agent_id}'")
        if tool.handler is None:
            raise TypeError(f"Tool '{name}' has no callable handler")
        call_args = dict(arguments or {})
        if kwargs:
            call_args.update(kwargs)
        return tool.handler(**call_args)

    def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Backward-compatible alias used by the MCP wrapper."""
        return self.invoke(name, arguments=arguments, **kwargs)

    @classmethod
    def get_registry(cls, agent_id: str, create: bool = False) -> Optional["NativeToolRegistry"]:
        with _REGISTRY_LOCK:
            registry = cls._registry_map.get(agent_id)
        if registry is None and create:
            registry = cls(agent_id=agent_id)
        return registry

    @classmethod
    def all_registries(cls) -> Dict[str, "NativeToolRegistry"]:
        with _REGISTRY_LOCK:
            return dict(cls._registry_map)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self._agent_id,
            "tool_count": len(self._tools),
            "execution_class": "native",
            "tools": {name: tool.to_full_dict() for name, tool in self._tools.items()},
        }


native_tool_registry: NativeToolRegistry = NativeToolRegistry(agent_id="simp_agent")


def native_tool(
    name: str = "",
    description: str = "",
    intent_type: str = "",
):
    """Decorator that registers a function in the native tool registry."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        tool = SimpTool.from_function(
            func,
            name=name,
            description=description,
            intent_type=intent_type,
        )
        native_tool_registry.register(tool)
        return func

    return decorator
