"""Unit and E2E tests for BrowserTool and Page Object Models (POM)."""
import pytest
import os
import time
import subprocess
from agent.tools.browser_tool import BrowserTool
from agent.tools.base import ToolResult

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_browser_tool.sqlite3")


@pytest.fixture(scope="module")
def browser_test_server():
    """Start isolated test server instance for browser tool testing."""
    os.environ["AQA_DB_PATH"] = TEST_DB_PATH

    from app.database import init_db
    init_db(reset=True)

    # Start uvicorn server on port 8093 for testing
    proc = subprocess.Popen(
        [
            "/home/zoeltea/my_work/agentic-qa-lab/.venv/bin/uvicorn",
            "app.server:app",
            "--host", "127.0.0.1",
            "--port", "8093"
        ],
        cwd="/home/zoeltea/my_work/agentic-qa-lab",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ, AQA_DB_PATH=TEST_DB_PATH)
    )

    # Wait for server ready
    import httpx
    deadline = time.time() + 10.0
    server_ready = False
    while time.time() < deadline:
        try:
            r = httpx.get("http://127.0.0.1:8093/api/health", timeout=1.0)
            if r.status_code == 200:
                server_ready = True
                break
        except Exception:
            time.sleep(0.3)

    if not server_ready:
        proc.terminate()
        pytest.fail("Test server failed to start on port 8093")

    yield "http://127.0.0.1:8093"

    # Teardown
    proc.terminate()
    proc.wait()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


def test_browser_tool_contract_and_mcp_schema():
    tool = BrowserTool(base_url="http://127.0.0.1:8093")
    assert tool.name == "browser_action"
    assert "semantic actions" in tool.description.lower()
    
    mcp_def = tool.to_mcp_tool()
    assert mcp_def["name"] == "browser_action"
    assert "properties" in mcp_def["inputSchema"]
    assert "action" in mcp_def["inputSchema"]["properties"]


def test_browser_tool_semantic_flow(browser_test_server):
    tool = BrowserTool(base_url=browser_test_server, headless=True)
    
    try:
        # 1. Open Store Action
        res = tool.run(action="open_store")
        assert isinstance(res, ToolResult)
        assert res.ok is True
        assert res.data["rendered_products_count"] == 4
        assert len(res.data["products"]) == 4

        # 2. Add to Cart Action
        res_add = tool.run(action="add_to_cart", product_id=1)
        assert res_add.ok is True
        assert res_add.data["product_id"] == 1
        assert res_add.data["cart_badge_count"] == 1

        # 3. Apply Voucher Action
        res_voucher = tool.run(action="apply_voucher", code="DISKON10")
        assert res_voucher.ok is True
        assert res_voucher.data["applied"] is True
        assert "berhasil" in res_voucher.data["message"].lower()

        # 4. Checkout Action
        res_checkout = tool.run(
            action="checkout",
            customer_name="Zul Automated Tester",
            customer_email="zul.test@example.com",
            shipping_address="Jl. Otomasi QA No. 99, Jakarta",
            payment_method="qris"
        )
        assert res_checkout.ok is True
        assert res_checkout.data["success"] is True
        assert res_checkout.data["order_number"].startswith("ORD-")

        # 5. Invalid action error handling (Zero-Exception Contract)
        res_invalid = tool.run(action="non_existent_action")
        assert res_invalid.ok is False
        assert "unknown action" in res_invalid.error.lower()

    finally:
        tool.close()
