"""Central Tool Registry for Phase 2.
Provides tool discovery, Constructor Dependency Injection, and MCP / OpenAI schema export.
"""
from typing import Dict, List, Optional, Any
from agent.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """Registry managing collection of available tools.
    Supports Constructor Dependency Injection for seamless testing and mocking.
    """

    def __init__(self, tools: Optional[List[BaseTool]] = None):
        self._tools: Dict[str, BaseTool] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: BaseTool):
        """Register a single tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Export list of tool definitions formatted for MCP clients."""
        return [tool.to_mcp_tool() for tool in self._tools.values()]

    def list_openai_tools(self) -> List[Dict[str, Any]]:
        """Export tool definitions formatted for OpenAI / Anthropic function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema.model_json_schema(),
                },
            }
            for tool in self._tools.values()
        ]

    def dispatch(self, name: str, args: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Dispatch execution to the registered tool by name with arguments.
        Enforces Zero-Exception contract: unhandled errors are returned as ToolResult(ok=False).
        """
        tool = self.get(name)
        if not tool:
            return ToolResult(
                ok=False,
                error=f"Tool '{name}' is not registered in the ToolRegistry (available: {list(self._tools.keys())}).",
            )

        args = args or {}
        try:
            return tool.run(**args)
        except Exception as e:
            return ToolResult(
                ok=False,
                error=f"Unhandled runtime exception inside tool '{name}': {str(e)}",
            )
