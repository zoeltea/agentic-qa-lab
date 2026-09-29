"""Unit tests for ToolRegistry — discovery, DI, MCP export, and error interception."""
import pytest
from pydantic import BaseModel
from agent.tools.base import BaseTool, ToolResult
from agent.tools.registry import ToolRegistry


class DummyInput(BaseModel):
    query: str


class DummyToolA(BaseTool):
    name = "dummy_a"
    description = "Dummy tool A description"
    input_schema = DummyInput

    def run(self, **kwargs) -> ToolResult:
        return self._success({"echo": kwargs.get("query", "")})


class DummyToolB(BaseTool):
    name = "dummy_b"
    description = "Dummy tool B description"
    input_schema = DummyInput

    def run(self, **kwargs) -> ToolResult:
        if kwargs.get("query") == "raise":
            raise RuntimeError("Intentional unhandled bug in tool B")
        return self._success({"result_b": True})


def test_registry_constructor_di():
    tool_a = DummyToolA()
    registry = ToolRegistry(tools=[tool_a])
    assert registry.get("dummy_a") is tool_a
    assert registry.get("dummy_b") is None


def test_registry_dispatch_success():
    registry = ToolRegistry(tools=[DummyToolA()])
    res = registry.dispatch("dummy_a", {"query": "test value"})
    assert res.ok is True
    assert res.data["echo"] == "test value"


def test_registry_dispatch_not_found():
    registry = ToolRegistry()
    res = registry.dispatch("nonexistent_tool")
    assert res.ok is False
    assert "not registered" in (res.error or "")


def test_registry_dispatch_unhandled_exception_intercepted():
    registry = ToolRegistry(tools=[DummyToolB()])
    res = registry.dispatch("dummy_b", {"query": "raise"})
    assert res.ok is False
    assert "Unhandled runtime exception" in (res.error or "")
    assert "Intentional unhandled bug" in (res.error or "")


def test_registry_mcp_and_openai_export():
    registry = ToolRegistry(tools=[DummyToolA(), DummyToolB()])
    mcp_tools = registry.list_tools()
    assert len(mcp_tools) == 2
    assert mcp_tools[0]["name"] == "dummy_a"
    assert "inputSchema" in mcp_tools[0]

    openai_tools = registry.list_openai_tools()
    assert len(openai_tools) == 2
    assert openai_tools[0]["type"] == "function"
    assert openai_tools[0]["function"]["name"] == "dummy_a"
