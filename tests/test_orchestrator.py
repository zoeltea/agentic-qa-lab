"""Phase 3 Integration Tests for Orchestrator, ScriptedPlanner, Guardrails, and Evaluator."""
import pytest
import os
import subprocess
import time
from typing import List, Dict, Any

from agent.tools.registry import ToolRegistry
from agent.tools.db_tool import DbTool
from agent.tools.api_tool import ApiTool
from agent.tools.browser_tool import BrowserTool
from agent.tools.log_tool import LogTool
from agent.guardrails import Guardrails
from agent.orchestrator import Orchestrator, ScriptedPlanner
from agent.evaluator import TestVerdict

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_orch_testbed.sqlite3")


@pytest.fixture(scope="module")
def orch_live_server():
    """Start live test server for Orchestrator integration tests."""
    os.environ["AQA_DB_PATH"] = TEST_DB_PATH

    from app.database import init_db
    init_db(reset=True)

    proc = subprocess.Popen(
        [
            "/home/zoeltea/my_work/agentic-qa-lab/.venv/bin/uvicorn",
            "app.server:app",
            "--host", "127.0.0.1",
            "--port", "8094"
        ],
        cwd="/home/zoeltea/my_work/agentic-qa-lab",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ, AQA_DB_PATH=TEST_DB_PATH)
    )

    import httpx
    deadline = time.time() + 10.0
    ready = False
    while time.time() < deadline:
        try:
            r = httpx.get("http://127.0.0.1:8094/api/health", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.3)

    if not ready:
        proc.terminate()
        pytest.fail("Test server failed to start on port 8094")

    yield "http://127.0.0.1:8094"

    proc.terminate()
    proc.wait()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


def test_orchestrator_successful_reconciliation_flow(orch_live_server):
    # Setup Real Tools with live test server
    b_tool = BrowserTool(base_url=orch_live_server, headless=True)
    registry = ToolRegistry(
        tools=[
            DbTool(db_path=TEST_DB_PATH),
            ApiTool(base_url=orch_live_server),
            b_tool,
            LogTool(db_path=TEST_DB_PATH),
        ]
    )

    planner = ScriptedPlanner()
    guardrails = Guardrails(max_turns=12)
    orchestrator = Orchestrator(registry=registry, guardrails=guardrails, planner=planner)

    try:
        verdict = orchestrator.run(goal="Verify full checkout and multi-layer reconciliation for mechanical keyboard with DISKON10 voucher.")
        
        assert isinstance(verdict, TestVerdict)
        assert verdict.status == "PASS"
        assert "multi-layer reconciliation verified" in verdict.reason.lower()
        assert verdict.evidence.ui is not None
        assert verdict.evidence.db is not None
        assert len(verdict.trace) == 8
    finally:
        b_tool.close()


def test_orchestrator_circuit_breaker_turn_budget(orch_live_server):
    # Infinite Planner that never stops yielding steps
    class InfinitePlanner:
        def next_step(self, goal, history):
            return {
                "thought": f"Infinite turn {len(history)}",
                "tool": "api_client",
                "args": {"method": "GET", "path": f"/api/health?t={len(history)}"}
            }

    registry = ToolRegistry(tools=[ApiTool(base_url=orch_live_server)])
    # Set tight turn limit: max 3 turns
    guardrails = Guardrails(max_turns=3)
    orchestrator = Orchestrator(
        registry=registry,
        guardrails=guardrails,
        planner=InfinitePlanner(),
        max_turns=3
    )

    verdict = orchestrator.run(goal="Test turn limit circuit breaker")
    assert verdict.status == "BLOCKED"
    assert "budget exceeded" in verdict.reason.lower()


def test_orchestrator_circuit_breaker_loop_detection(orch_live_server):
    # Repetitive Planner calling same tool with identical args
    class LoopingPlanner:
        def next_step(self, goal, history):
            return {
                "thought": "Looping identical call",
                "tool": "api_client",
                "args": {"method": "GET", "path": "/api/health"}
            }

    registry = ToolRegistry(tools=[ApiTool(base_url=orch_live_server)])
    guardrails = Guardrails(consecutive_identical_threshold=2)
    orchestrator = Orchestrator(
        registry=registry,
        guardrails=guardrails,
        planner=LoopingPlanner()
    )

    verdict = orchestrator.run(goal="Test loop detection circuit breaker")
    assert verdict.status == "BLOCKED"
    assert "loop detected" in verdict.reason.lower()
