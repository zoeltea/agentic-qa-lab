"""Phase 2 Step 1 Unit Tests — base.py contract verification."""
import pytest
from pydantic import BaseModel
from agent.tools.base import BaseTool, ToolResult


class FakeSchema(BaseModel):
    value: str


class FakeTool(BaseTool):
    name = "fake_tool"
    description = "A fake tool for testing BaseTool contract."
    input_schema = FakeSchema

    def run(self, **kwargs) -> ToolResult:
        v = kwargs.get("value", "")
        if v == "trigger_error":
            return self._error("simulated failure")
        return self._success({"processed": v})


def test_tool_result_defaults():
    result = ToolResult(ok=True)
    assert result.ok is True
    assert result.data == {}
    assert result.error is None
    assert result.latency_ms == 0


def test_tool_result_with_data():
    result = ToolResult(ok=True, data={"foo": "bar"}, latency_ms=15)
    assert result.data == {"foo": "bar"}
    assert result.latency_ms == 15


def test_base_tool_success_helper():
    tool = FakeTool()
    result = tool.run(value="hello")
    assert result.ok is True
    assert result.data == {"processed": "hello"}
    assert result.error is None


def test_base_tool_error_helper():
    tool = FakeTool()
    result = tool.run(value="trigger_error")
    assert result.ok is False
    assert result.error == "simulated failure"


def test_to_mcp_tool_format():
    tool = FakeTool()
    mcp_tool = tool.to_mcp_tool()
    assert mcp_tool["name"] == "fake_tool"
    assert mcp_tool["description"] == "A fake tool for testing BaseTool contract."
    assert "value" in mcp_tool["inputSchema"]["properties"]


def test_subclass_missing_attr_raises():
    with pytest.raises(TypeError):
        class BrokenTool(BaseTool): pass
