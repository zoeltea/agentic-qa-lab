"""Tests for DbTool — testing safety guardrails, allowlists, and execution."""
import pytest
import os
from agent.tools.db_tool import DbTool
from app.database import init_db

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_tools_db.sqlite3")


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


def test_db_tool_valid_select():
    tool = DbTool(db_path=TEST_DB_PATH)
    result = tool.run(sql="SELECT * FROM products ORDER BY id ASC")
    assert result.ok is True
    assert result.error is None
    assert result.data["row_count"] == 4
    assert result.data["rows"][0]["sku"] == "PROD-MEC-01"


def test_db_tool_parameterized_query():
    tool = DbTool(db_path=TEST_DB_PATH)
    result = tool.run(sql="SELECT * FROM products WHERE id = ?", params=[1])
    assert result.ok is True
    assert result.data["row_count"] == 1
    assert result.data["rows"][0]["name"] == "Mechanical Keyboard Wireless Pro"


def test_db_tool_rejects_non_select():
    tool = DbTool(db_path=TEST_DB_PATH)
    result = tool.run(sql="DELETE FROM products WHERE id = 1")
    assert result.ok is False
    assert "Safety violation" in (result.error or "")


def test_db_tool_rejects_drop_table():
    tool = DbTool(db_path=TEST_DB_PATH)
    result = tool.run(sql="DROP TABLE products")
    assert result.ok is False
    assert "Safety violation" in (result.error or "")


def test_db_tool_rejects_insert():
    tool = DbTool(db_path=TEST_DB_PATH)
    result = tool.run(sql="INSERT INTO products (sku, name, price, stock, category) VALUES ('X', 'Y', 100, 1, 'Z')")
    assert result.ok is False
    assert "Safety violation" in (result.error or "")


def test_db_tool_rejects_unallowed_table():
    tool = DbTool(db_path=TEST_DB_PATH)
    result = tool.run(sql="SELECT * FROM sqlite_master")
    assert result.ok is False
    assert "not in the allowlist" in (result.error or "")


def test_db_tool_rejects_semicolon_chaining():
    tool = DbTool(db_path=TEST_DB_PATH)
    result = tool.run(sql="SELECT * FROM products; SELECT * FROM vouchers")
    assert result.ok is False
    assert "Multiple statements" in (result.error or "")
