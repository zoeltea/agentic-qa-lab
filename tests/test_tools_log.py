"""Tests for LogTool — verifying fault injection config read and log tailing."""
import pytest
import os
from agent.tools.log_tool import LogTool
from app.database import init_db, get_db_connection

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_tools_log.sqlite3")
TEST_LOG_PATH = os.path.join(os.path.dirname(__file__), "test_server.log")


@pytest.fixture(autouse=True)
def setup_resources():
    os.environ["AQA_DB_PATH"] = TEST_DB_PATH
    init_db(reset=True, db_path=TEST_DB_PATH)
    # Create a dummy log file
    with open(TEST_LOG_PATH, "w") as f:
        f.write("Line 1: Server startup\nLine 2: Connected DB\nLine 3: Request received\n")

    yield

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass
    if os.path.exists(TEST_LOG_PATH):
        try:
            os.remove(TEST_LOG_PATH)
        except OSError:
            pass


def test_log_tool_reads_fault_config():
    tool = LogTool(log_file_path=TEST_LOG_PATH, db_path=TEST_DB_PATH)
    result = tool.run(check_fault_config=True)
    assert result.ok is True
    assert result.data["fault_config"] is not None
    assert result.data["fault_config"]["simulate_silent_db_failure"] == 0


def test_log_tool_reads_custom_fault_config():
    # Update fault injection config
    conn = get_db_connection(db_path=TEST_DB_PATH)
    with conn:
        conn.execute("UPDATE fault_injection_config SET simulate_silent_db_failure = 1 WHERE id = 1")
    conn.close()

    tool = LogTool(log_file_path=TEST_LOG_PATH, db_path=TEST_DB_PATH)
    result = tool.run(check_fault_config=True)
    assert result.ok is True
    assert result.data["fault_config"]["simulate_silent_db_failure"] == 1


def test_log_tool_reads_log_lines():
    tool = LogTool(log_file_path=TEST_LOG_PATH, db_path=TEST_DB_PATH)
    result = tool.run(last_n_lines=2)
    assert result.ok is True
    assert len(result.data["logs"]) == 2
    assert "Line 3" in result.data["logs"][-1]
