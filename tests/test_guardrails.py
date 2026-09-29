"""Phase 3 Unit Tests for Guardrails, Circuit Breakers, and Loop Detectors."""
import pytest
import time
from agent.guardrails import (
    Guardrails,
    GuardrailState,
    GuardrailResult,
    TurnBudgetGuard,
    LoopDetector,
    TokenBudgetGuard,
    ExecutionTimeoutGuard,
)


def test_turn_budget_guard():
    guard = TurnBudgetGuard(max_turns=3)
    state = GuardrailState(turn_count=2)
    assert guard.check(state).tripped is False

    state.turn_count = 3
    assert guard.check(state).tripped is False

    state.turn_count = 4
    res = guard.check(state)
    assert res.tripped is True
    assert res.action == "abort"
    assert "budget exceeded" in res.reason.lower()


def test_loop_detector_consecutive_identical():
    detector = LoopDetector(consecutive_identical_threshold=2)
    state = GuardrailState()

    # Call 1
    state.history.append(("db_query", {"sql": "SELECT 1"}))
    assert detector.check(state).tripped is False

    # Call 2: Different query
    state.history.append(("db_query", {"sql": "SELECT 2"}))
    assert detector.check(state).tripped is False

    # Call 3: Identical query to Call 2
    state.history.append(("db_query", {"sql": "SELECT 2"}))
    res = detector.check(state)
    assert res.tripped is True
    assert res.action == "abort"
    assert "repetitive tool loop" in res.reason.lower()


def test_loop_detector_ping_pong_cycle():
    detector = LoopDetector()
    state = GuardrailState()

    # Pattern A -> B -> A -> B
    state.history.append(("api_client", {"path": "/api/products"}))
    state.history.append(("db_query", {"sql": "SELECT 1"}))
    state.history.append(("api_client", {"path": "/api/products"}))
    state.history.append(("db_query", {"sql": "SELECT 1"}))

    res = detector.check(state)
    assert res.tripped is True
    assert res.action == "abort"
    assert "ping-pong" in res.reason.lower()


def test_token_budget_guard():
    guard = TokenBudgetGuard(max_tokens=1000)
    state = GuardrailState(estimated_tokens=500)
    assert guard.check(state).tripped is False

    state.estimated_tokens = 1000
    assert guard.check(state).tripped is False

    state.estimated_tokens = 1001
    res = guard.check(state)
    assert res.tripped is True
    assert res.action == "abort"
    assert "token budget exceeded" in res.reason.lower()


def test_execution_timeout_guard():
    guard = ExecutionTimeoutGuard(max_ms=100)
    # Start time in the past
    state = GuardrailState(start_time_ms=int(time.time() * 1000) - 200)
    res = guard.check(state)
    assert res.tripped is True
    assert res.action == "abort"
    assert "timeout exceeded" in res.reason.lower()


def test_facade_guardrails_priority():
    # Test priority order: Timeout -> Turn -> Loop -> Token
    # Configure low timeout and over-budget turns
    guardrails = Guardrails(
        max_turns=2,
        consecutive_identical_threshold=2,
        max_tokens=100,
        max_timeout_ms=50,
    )

    # Trigger both Timeout and Turn budget simultaneously
    state = GuardrailState(
        turn_count=5,
        estimated_tokens=500,
        start_time_ms=int(time.time() * 1000) - 100,
    )

    res = guardrails.check(state)
    assert res.tripped is True
    # Timeout has highest priority
    assert "timeout" in res.reason.lower()

    # Now with fresh timestamp, Turn budget should be prioritized over Token
    fresh_state = GuardrailState(
        turn_count=5,
        estimated_tokens=500,
        start_time_ms=int(time.time() * 1000),
    )
    res_fresh = guardrails.check(fresh_state)
    assert res_fresh.tripped is True
    assert "turns" in res_fresh.reason.lower()
