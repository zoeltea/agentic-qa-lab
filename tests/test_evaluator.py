"""Phase 3 Unit Tests for Evaluator and Zero-Hallucination Assertion."""
import pytest
from agent.evaluator import (
    LayerEvidence,
    TestVerdict,
    evaluate_order_reconciliation,
)
from agent.guardrails import GuardrailResult


def test_evaluator_pass_when_consistent():
    evidence = LayerEvidence(
        ui={"order_number": "ORD-123", "total": "Rp 700.000"},
        api={"status_code": 200, "body": {"order_number": "ORD-123"}},
        db={"row_count": 1, "rows": [{"order_number": "ORD-123"}]}
    )
    verdict = evaluate_order_reconciliation(evidence, trace=[])
    assert verdict.status == "PASS"
    assert "consistent" in verdict.reason.lower()


def test_evaluator_fail_when_order_number_mismatch():
    evidence = LayerEvidence(
        ui={"order_number": "ORD-123"},
        db={"row_count": 1, "rows": [{"order_number": "ORD-999"}]}
    )
    verdict = evaluate_order_reconciliation(evidence, trace=[])
    assert verdict.status == "FAIL"
    assert "mismatch" in verdict.reason.lower()


def test_evaluator_fail_when_db_record_missing_silent_failure():
    # UI says success but DB has 0 rows
    evidence = LayerEvidence(
        ui={"order_number": "ORD-123"},
        db={"row_count": 0, "rows": []}
    )
    verdict = evaluate_order_reconciliation(evidence, trace=[])
    assert verdict.status == "FAIL"
    assert "zero-hallucination" in verdict.reason.lower()
    assert "silent failure" in verdict.reason.lower()


def test_evaluator_blocked_when_guardrail_tripped():
    evidence = LayerEvidence(ui={"order_number": "ORD-123"})
    g_res = GuardrailResult(tripped=True, reason="Max turns budget exceeded", action="abort")
    verdict = evaluate_order_reconciliation(evidence, trace=[], guardrail_result=g_res)
    assert verdict.status == "BLOCKED"
    assert "max turns" in verdict.reason.lower()
