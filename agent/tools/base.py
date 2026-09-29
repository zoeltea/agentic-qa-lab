"""Base contract and ToolResult for Phase 2 Multi-Tool integration."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from dataclasses import dataclass, field
from pydantic import BaseModel


@dataclass
class ToolResult:
    """Standardized result returned by every Phase 2 tool."""
    ok: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: int = 0


class BaseTool(ABC):
    """Abstract base class for all Phase 2 tools.
    Enforces contract: name, description, input_schema, and run() method.
    """
    name: str
    description: str
    input_schema: Type[BaseModel]

    def __init_subclass__(cls, **kwargs):
        # Validate required attributes are defined in subclasses
        for attr in ("name", "description", "input_schema"):
            if getattr(cls, attr, None) is None:
                raise TypeError(f"[{cls.__name__}] missing required attribute '{attr}'")
        super().__init_subclass__(**kwargs)

    # --- OOP Helper Methods (convenient for subclasses) ---
    def _success(self, data: Any = None, latency: int = 0) -> ToolResult:
        return ToolResult(ok=True, data=data if data is not None else {}, latency_ms=latency)

    def _error(self, msg: str, latency: int = 0) -> ToolResult:
        return ToolResult(ok=False, error=msg, latency_ms=latency)

    # --- Abstract Method ---
    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """Execute the tool logic with validated arguments.
        Must return ToolResult and never raise unhandled exceptions.
        """
        ...

    # --- MCP Compatibility Method ---
    def to_mcp_tool(self) -> dict:
        """Export tool definition for MCP (Model Context Protocol) clients.
        Returns: {\"name\", \"description\", \"inputSchema\"}
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema.model_json_schema(),
        }
