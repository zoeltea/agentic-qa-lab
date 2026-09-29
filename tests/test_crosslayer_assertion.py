"""Tests for VerifierGuardrails and Cross-Layer Assertion constraints."""
import pytest
from agent.verifier_guardrails import VerifierGuardrails, GuardrailResult


def test_guardrail_evidence_completeness():
    """1 layer evidence -> GuardrailResult tripped (insufficient layers)."""
    guard = VerifierGuardrails(min_evidence_layers=2)
    res = guard.check_evidence_completeness(evidence_layers=1)
    assert res.tripped is True
    assert res.action == "abort"
    assert "Insufficient evidence layers" in (res.reason or "")

    # Valid case: 2 layers -> not tripped
    res_valid = guard.check_evidence_completeness(evidence_layers=2)
    assert res_valid.tripped is False
    assert res_valid.action == "continue"


def test_guardrail_duplication():
    """check_description 'verify_order_number' dipanggil 3x -> GuardrailResult tripped."""
    guard = VerifierGuardrails(duplication_threshold=3)
    
    # Call 1: pass
    res1 = guard.check_duplication("verify_order_number")
    assert res1.tripped is False
    assert res1.action == "continue"

    # Call 2: pass
    res2 = guard.check_duplication("verify_order_number")
    assert res2.tripped is False
    assert res2.action == "continue"

    # Call 3: tripped
    res3 = guard.check_duplication("verify_order_number")
    assert res3.tripped is True
    assert res3.action == "abort"
    assert "Duplication threshold reached" in (res3.reason or "")


def test_guardrail_maturity():
    """verdict='PASS' dengan checks_done=1 -> GuardrailResult tripped (retry)."""
    guard = VerifierGuardrails()
    
    res_premature = guard.check_maturity(verdict="PASS", checks_done=1)
    assert res_premature.tripped is True
    assert res_premature.action == "retry"
    assert "Premature PASS verdict" in (res_premature.reason or "")

    # Non-PASS verdict does not trip maturity
    res_fail = guard.check_maturity(verdict="FAIL", checks_done=1)
    assert res_fail.tripped is False
    assert res_fail.action == "continue"


def test_guardrail_all_clear():
    """3 layers evidence, checks_done=3, no duplication -> GuardrailResult not tripped."""
    guard = VerifierGuardrails(min_evidence_layers=2, duplication_threshold=3)

    # 1. Check completeness with 3 layers
    res_comp = guard.check_evidence_completeness(evidence_layers=3)
    assert res_comp.tripped is False

    # 2. Check 3 distinct actions (no duplication)
    assert guard.check_duplication("check_ui_modal").tripped is False
    assert guard.check_duplication("check_api_response").tripped is False
    assert guard.check_duplication("check_db_orders").tripped is False

    # 3. Check maturity with checks_done=3
    res_mat = guard.check_maturity(verdict="PASS", checks_done=3)
    assert res_mat.tripped is False
    assert res_mat.action == "continue"
