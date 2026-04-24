"""
ProjectX Dynamic Tool Generator

Generates safe bounded MCP tools from structured requirements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from simp.mcp.tool_registry import ToolRegistry
from simp.mcp.tool_schema import SimpMCPTool


@dataclass
class GeneratedToolSpec:
    name: str
    description: str
    requirement: str
    tool_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "requirement": self.requirement,
            "tool_type": self.tool_type,
            "parameters": dict(self.parameters),
        }


class DynamicToolCreator:
    """
    Create safe local tools from requirement strings.

    Supported tool patterns are intentionally bounded:
    - summarize list/items/text
    - count records/items/words
    - filter records by numeric threshold
    - extract selected fields from dict records
    """

    def __init__(self, agent_id: str = "projectx") -> None:
        self._agent_id = agent_id

    def create_tool(self, requirement: str, *, name_hint: str = "") -> SimpMCPTool:
        spec = self._parse_requirement(requirement, name_hint=name_hint)
        handler = self._build_handler(spec)
        input_schema = self._build_input_schema(spec)
        return SimpMCPTool(
            name=spec.name,
            description=spec.description,
            input_schema=input_schema,
            handler=handler,
            simp_intent_type=f"projectx_dynamic_tool:{spec.tool_type}",
        )

    def register_tool(self, requirement: str, *, name_hint: str = "") -> Dict[str, Any]:
        registry = ToolRegistry.get_registry(self._agent_id, create=True)
        assert registry is not None
        tool = self.create_tool(requirement, name_hint=name_hint)
        registry.register(tool)
        return {
            "status": "success",
            "tool": tool.to_full_dict(),
            "tool_count": len(registry.list_tools()),
        }

    def _parse_requirement(self, requirement: str, *, name_hint: str = "") -> GeneratedToolSpec:
        req = " ".join(str(requirement).strip().split())
        if not req:
            raise ValueError("Tool requirement must be non-empty")
        lowered = req.lower()
        raw_name = name_hint or req[:48]
        safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", raw_name.strip().lower()).strip("_")[:48]
        if not safe_name:
            safe_name = "generated_tool"

        if any(term in lowered for term in ("summarize", "summarise", "summary")):
            return GeneratedToolSpec(
                name=safe_name,
                description=f"Summarize structured items for: {req}",
                requirement=req,
                tool_type="summarize",
            )
        if any(term in lowered for term in ("count", "total")):
            return GeneratedToolSpec(
                name=safe_name,
                description=f"Count structured items for: {req}",
                requirement=req,
                tool_type="count",
            )
        if "filter" in lowered and any(term in lowered for term in ("threshold", "min", "above", "greater")):
            return GeneratedToolSpec(
                name=safe_name,
                description=f"Filter records by numeric threshold for: {req}",
                requirement=req,
                tool_type="filter_threshold",
            )
        if any(term in lowered for term in ("extract", "select fields", "pluck")):
            return GeneratedToolSpec(
                name=safe_name,
                description=f"Extract selected fields for: {req}",
                requirement=req,
                tool_type="extract_fields",
            )
        raise ValueError(f"Unsupported tool requirement: {req}")

    def _build_handler(self, spec: GeneratedToolSpec):
        if spec.tool_type == "summarize":
            def _handler(items: List[Any], max_items: int = 5) -> Dict[str, Any]:
                bounded = [str(item)[:160] for item in (items or [])[:max(1, min(int(max_items), 20))]]
                return {
                    "count": len(items or []),
                    "summary": "; ".join(bounded),
                }
            return _handler
        if spec.tool_type == "count":
            def _handler(items: List[Any], key: str = "") -> Dict[str, Any]:
                values = items or []
                if key:
                    count = sum(1 for item in values if isinstance(item, dict) and key in item)
                else:
                    count = len(values)
                return {"count": count, "key": key}
            return _handler
        if spec.tool_type == "filter_threshold":
            def _handler(items: List[Dict[str, Any]], field: str, min_value: float) -> Dict[str, Any]:
                threshold = float(min_value)
                filtered = []
                for item in (items or []):
                    if not isinstance(item, dict):
                        continue
                    try:
                        value = float(item.get(field))
                    except (TypeError, ValueError):
                        continue
                    if value >= threshold:
                        filtered.append(item)
                return {"count": len(filtered), "items": filtered[:50]}
            return _handler
        if spec.tool_type == "extract_fields":
            def _handler(items: List[Dict[str, Any]], fields: List[str]) -> Dict[str, Any]:
                extracted = []
                for item in (items or [])[:100]:
                    if isinstance(item, dict):
                        extracted.append({field: item.get(field) for field in fields[:20]})
                return {"count": len(extracted), "items": extracted}
            return _handler
        raise ValueError(f"Unsupported generated tool type: {spec.tool_type}")

    @staticmethod
    def _build_input_schema(spec: GeneratedToolSpec) -> Dict[str, Any]:
        if spec.tool_type == "summarize":
            return {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "description": "Items to summarize"},
                    "max_items": {"type": "number", "description": "Maximum items to include", "default": 5},
                },
                "required": ["items"],
            }
        if spec.tool_type == "count":
            return {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "description": "Items to count"},
                    "key": {"type": "string", "description": "Optional dict key to count"},
                },
                "required": ["items"],
            }
        if spec.tool_type == "filter_threshold":
            return {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "description": "Dict records"},
                    "field": {"type": "string", "description": "Numeric field to inspect"},
                    "min_value": {"type": "number", "description": "Minimum allowed value"},
                },
                "required": ["items", "field", "min_value"],
            }
        if spec.tool_type == "extract_fields":
            return {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "description": "Dict records"},
                    "fields": {"type": "array", "description": "Fields to extract"},
                },
                "required": ["items", "fields"],
            }
        return {"type": "object", "properties": {}}


_dynamic_tool_creators: Dict[str, DynamicToolCreator] = {}


def get_dynamic_tool_creator(agent_id: str = "projectx") -> DynamicToolCreator:
    creator = _dynamic_tool_creators.get(agent_id)
    if creator is None:
        creator = DynamicToolCreator(agent_id=agent_id)
        _dynamic_tool_creators[agent_id] = creator
    return creator
