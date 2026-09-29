"""Strict Guardrails, Circuit Breakers, Loop Detection, and Budget Enforcers for Phase 3."""
import time
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Tuple, Dict, Any

Action = Literal["continue", "abort", "retry"]


@dataclass
class GuardrailResult:
    """Result returned by guardrail checks."""
    tripped: bool
    reason: Optional[str] = None
    action: Action = "continue"


@dataclass
class GuardrailState:
    """State tracking container for Orchestrator execution loop."""
    turn_count: int = 0
    history: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)  # (tool_name, args)
    estimated_tokens: int = 0
    start_time_ms: int = field(default_factory=lambda: int(time.time() * 1000))


class TurnBudgetGuard:
    """Enforces a hard upper bound on ReAct reasoning turns."""

    def __init__(self, max_turns: int = 12):
        self.max_turns = max_turns

    def check(self, state: GuardrailState) -> GuardrailResult:
        if state.turn_count > self.max_turns:
            return GuardrailResult(
                tripped=True,
                reason=f"Max turns budget exceeded ({state.turn_count} > {self.max_turns})",
                action="abort",
            )
        return GuardrailResult(tripped=False, action="continue")


class LoopDetector:
    """Detects repetitive tool invocations and action ping-pong loops."""

    def __init__(self, consecutive_identical_threshold: int = 2):
        self.threshold = consecutive_identical_threshold

    def check(self, state: GuardrailState) -> GuardrailResult:
        if len(state.history) < self.threshold:
            return GuardrailResult(tripped=False, action="continue")

        # Check for consecutive identical calls (tool_name + args)
        recent_calls = state.history[-self.threshold:]
        first_call = recent_calls[0]
        all_identical = all(call == first_call for call in recent_calls)

        if all_identical:
            tool_name = first_call[0]
            return GuardrailResult(
                tripped=True,
                reason=(
                    f"Repetitive tool loop detected: tool '{tool_name}' invoked "
                    f"{self.threshold} times with identical arguments"
                ),
                action="abort",
            )

        # Check for 2-step cycle pattern: [A, B, A, B]
        if len(state.history) >= 4:
            if (
                state.history[-1] == state.history[-3]
                and state.history[-2] == state.history[-4]
                and state.history[-1] != state.history[-2]
            ):
                return GuardrailResult(
                    tripped=True,
                    reason="Ping-pong cycle detected between alternating tools",
                    action="abort",
                )

        return GuardrailResult(tripped=False, action="continue")


class TokenBudgetGuard:
    """Enforces maximum allowed cumulative token budget."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    def check(self, state: GuardrailState) -> GuardrailResult:
        if state.estimated_tokens > self.max_tokens:
            return GuardrailResult(
                tripped=True,
                reason=f"Token budget exceeded ({state.estimated_tokens} > {self.max_tokens})",
                action="abort",
            )
        return GuardrailResult(tripped=False, action="continue")


class ExecutionTimeoutGuard:
    """Enforces wall-clock execution time limit per test case run."""

    def __init__(self, max_ms: int = 120000):
        self.max_ms = max_ms

    def check(self, state: GuardrailState) -> GuardrailResult:
        now_ms = int(time.time() * 1000)
        elapsed = now_ms - state.start_time_ms
        if elapsed > self.max_ms:
            return GuardrailResult(
                tripped=True,
                reason=f"Execution timeout exceeded ({elapsed}ms > {self.max_ms}ms)",
                action="abort",
            )
        return GuardrailResult(tripped=False, action="continue")


class Guardrails:
    """Unified Facade combining all strict circuit breakers and guards.
    Evaluates checks in strict priority order: Timeout -> Turn Budget -> Loop Detector -> Token Budget.
    """

    def __init__(
        self,
        max_turns: int = 12,
        consecutive_identical_threshold: int = 2,
        max_tokens: int = 8000,
        max_timeout_ms: int = 120000,
    ):
        self.timeout_guard = ExecutionTimeoutGuard(max_ms=max_timeout_ms)
        self.turn_guard = TurnBudgetGuard(max_turns=max_turns)
        self.loop_detector = LoopDetector(consecutive_identical_threshold=consecutive_identical_threshold)
        self.token_guard = TokenBudgetGuard(max_tokens=max_tokens)

    def check(self, state: GuardrailState) -> GuardrailResult:
        """Run all guardrail checks in priority order and return first tripped result."""
        # 1. Timeout Check
        res = self.timeout_guard.check(state)
        if res.tripped:
            return res

        # 2. Turn Budget Check
        res = self.turn_guard.check(state)
        if res.tripped:
            return res

        # 3. Loop Detector Check
        res = self.loop_detector.check(state)
        if res.tripped:
            return res

        # 4. Token Budget Check
        res = self.token_guard.check(state)
        if res.tripped:
            return res

        return GuardrailResult(tripped=False, action="continue")
