# app/ai/tool_registry.py
from dataclasses import dataclass
from typing import Any, Callable, Dict

@dataclass
class ToolSpec:
    name: str
    handler: Callable[..., Any]

TOOL_REGISTRY: Dict[str, ToolSpec] = {}

def register_tool(spec: ToolSpec) -> None:
    TOOL_REGISTRY[spec.name] = spec

def get_tool(name: str) -> ToolSpec:
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]
