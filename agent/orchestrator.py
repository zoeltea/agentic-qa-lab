"""ReAct Orchestrator Engine for Agentic QA Lab.
Coordinates Plan -> Select Tool -> Execute (via ToolRegistry) -> Observe -> Evaluate loop with strict guardrails.
"""
import time
from typing import Callable, Optional, Dict, Any, List
from agent.tools.registry import ToolRegistry
from agent.guardrails import Guardrails, GuardrailState, GuardrailResult
from agent.evaluator import LayerEvidence, TestVerdict, evaluate_order_reconciliation


class ScriptedPlanner:
    """Deterministic, step-by-step planner for end-to-end checkout & reconciliation testing."""

    def __init__(self, steps: Optional[List[Dict[str, Any]]] = None):
        self.steps = steps if steps is not None else self._default_checkout_steps()
        self._current_index = 0

    def _default_checkout_steps(self) -> List[Dict[str, Any]]:
        return [
            {
                "thought": "Step 1: Open the store catalog via UI to verify rendering.",
                "tool": "browser_action",
                "args": {"action": "open_store"}
            },
            {
                "thought": "Step 2: Check backend health API status.",
                "tool": "api_client",
                "args": {"method": "GET", "path": "/api/health"}
            },
            {
                "thought": "Step 3: Query initial product stock from database (Ground Truth).",
                "tool": "db_query",
                "args": {"sql": "SELECT id, sku, name, price, stock FROM products WHERE id = 1"}
            },
            {
                "thought": "Step 4: Add mechanical keyboard (id=1) to cart via UI.",
                "tool": "browser_action",
                "args": {"action": "add_to_cart", "product_id": 1}
            },
            {
                "thought": "Step 5: Apply promo voucher 'DISKON10' via UI.",
                "tool": "browser_action",
                "args": {"action": "apply_voucher", "code": "DISKON10"}
            },
            {
                "thought": "Step 6: Submit checkout form via UI.",
                "tool": "browser_action",
                "args": {
                    "action": "checkout",
                    "customer_name": "Zul SDET Orchestrator",
                    "customer_email": "zul.orch@example.com",
                    "shipping_address": "Jl. ReAct Loop No. 10",
                    "payment_method": "qris"
                }
            },
            {
                "thought": "Step 7: Reconcile database order records using captured order number.",
                "tool": "db_query",
                "args": {
                    "sql": "SELECT order_number, customer_name, subtotal, discount_amount, total_amount, status FROM orders ORDER BY id DESC LIMIT 1"
                }
            },
            {
                "thought": "Step 8: Check server logs and fault injection config status.",
                "tool": "log_inspector",
                "args": {"check_fault_config": True, "last_n_lines": 5}
            }
        ]

    def next_step(self, goal: str, history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Return the next step in the plan or None if plan is exhausted."""
        if self._current_index < len(self.steps):
            step = self.steps[self._current_index]
            self._current_index += 1
            return step
        return None


class Orchestrator:
    """Core ReAct Orchestration Engine with Strict Guardrails and Multi-Layer Evidence Collection."""

    def __init__(
        self,
        registry: ToolRegistry,
        guardrails: Optional[Guardrails] = None,
        planner: Optional[Any] = None,
        evaluator_fn: Optional[Callable[..., TestVerdict]] = None,
        max_turns: int = 12,
    ):
        self.registry = registry
        self.guardrails = guardrails or Guardrails(max_turns=max_turns)
        self.planner = planner or ScriptedPlanner()
        self.evaluator_fn = evaluator_fn or evaluate_order_reconciliation
        self.max_turns = max_turns

    def run(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TestVerdict:
        """Execute the ReAct loop until a decisive TestVerdict or Guardrail trip."""
        state = GuardrailState(start_time_ms=int(time.time() * 1000))
        evidence = LayerEvidence()
        trace: List[Dict[str, Any]] = []

        while True:
            # 1. Guardrail Circuit Breaker Check
            g_res = self.guardrails.check(state)
            if g_res.tripped:
                return self.evaluator_fn(evidence, trace, guardrail_result=g_res)

            # 2. Planning Step
            step = self.planner.next_step(goal, trace)
            if not step:
                # Plan exhausted, perform final evaluation
                return self.evaluator_fn(evidence, trace, guardrail_result=None)

            thought = step.get("thought", "")
            tool_name = step.get("tool", "")
            args = step.get("args", {})

            # 3. Update Turn Counter & State History
            state.turn_count += 1
            state.history.append((tool_name, args))
            state.estimated_tokens += 150  # estimated prompt/completion token cost per turn

            # 4. Tool Execution via Registry
            tool_res = self.registry.dispatch(tool_name, args)

            # 5. Extract Multi-Layer Evidence from Observation
            if tool_res.ok:
                if tool_name == "browser_action":
                    if args.get("action") == "checkout" and tool_res.data.get("success"):
                        evidence.ui = tool_res.data
                elif tool_name == "api_client":
                    if args.get("path") in ("/api/checkout", "/api/health") or "/api/orders" in args.get("path", ""):
                        evidence.api = tool_res.data
                elif tool_name == "db_query":
                    if "orders" in args.get("sql", "").lower():
                        evidence.db = tool_res.data
                elif tool_name == "log_inspector":
                    evidence.logs = tool_res.data

            # 6. Record Trace
            turn_record = {
                "turn": state.turn_count,
                "thought": thought,
                "tool": tool_name,
                "args": args,
                "observation": {
                    "ok": tool_res.ok,
                    "data": tool_res.data,
                    "error": tool_res.error,
                    "latency_ms": tool_res.latency_ms
                }
            }
            trace.append(turn_record)
