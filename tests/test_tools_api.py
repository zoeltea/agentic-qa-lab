"""Tests for ApiTool — testing allowlisted endpoints, methods, and error interception."""
import pytest
import os
from starlette.testclient import TestClient

from app.server import app
from app.database import init_db
from agent.tools.api_tool import ApiTool

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_tools_api.sqlite3")


@pytest.fixture(autouse=True)
def setup_db():
    os.environ["AQA_DB_PATH"] = TEST_DB_PATH
    init_db(reset=True, db_path=TEST_DB_PATH)
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


@pytest.fixture
def mock_api_tool():
    # Use TestClient directly as a duck-typed HTTP client
    test_client = TestClient(app, base_url="http://testserver")
    tool = ApiTool(base_url="http://testserver", client=test_client)
    yield tool
    test_client.close()


def test_api_tool_healthcheck(mock_api_tool):
    result = mock_api_tool.run(method="GET", path="/api/health")
    assert result.ok is True
    assert result.data["status_code"] == 200
    assert result.data["body"]["status"] == "healthy"


def test_api_tool_get_products(mock_api_tool):
    result = mock_api_tool.run(method="GET", path="/api/products")
    assert result.ok is True
    assert result.data["status_code"] == 200
    assert len(result.data["body"]) == 4


def test_api_tool_apply_voucher(mock_api_tool):
    result = mock_api_tool.run(
        method="POST",
        path="/api/voucher/apply",
        body={"code": "DISKON10", "order_subtotal": 200000.0},
    )
    assert result.ok is True
    assert result.data["status_code"] == 200
    assert result.data["body"]["valid"] is True
    assert result.data["body"]["discount_amount"] == 20000.0


def test_api_tool_checkout(mock_api_tool):
    payload = {
        "customer_name": "SDET Agent Tool User",
        "customer_email": "tool.user@example.com",
        "shipping_address": "Jl. Tool No. 1",
        "payment_method": "qris",
        "voucher_code": "DISKON10",
        "items": [{"product_id": 1, "sku": "PROD-MEC-01", "quantity": 1}],
    }
    result = mock_api_tool.run(method="POST", path="/api/checkout", body=payload)
    assert result.ok is True
    assert result.data["status_code"] == 200
    assert result.data["body"]["success"] is True
    assert result.data["body"]["order_number"].startswith("ORD-")


def test_api_tool_rejects_unallowed_path(mock_api_tool):
    result = mock_api_tool.run(method="GET", path="/unauthorized/endpoint")
    assert result.ok is False
    assert "Safety violation" in (result.error or "")


def test_api_tool_rejects_invalid_method(mock_api_tool):
    result = mock_api_tool.run(method="HEAD", path="/api/products")
    assert result.ok is False
    assert "Safety violation" in (result.error or "")
