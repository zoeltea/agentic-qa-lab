"""Evaluator and Structured TestVerdict with Zero-Hallucination Assertion Engine."""
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field

from agent.guardrails import GuardrailResult


class LayerEvidence(BaseModel):
    """Captured cross-layer evidence collected during ReAct execution."""
    ui: Optional[Dict[str, Any]] = None      # e.g., {"order_number": "ORD-...", "total_amount_display": "..."}
    api: Optional[Dict[str, Any]] = None     # e.g., {"status_code": 200, "body": {"order_number": "..."}}
    db: Optional[Dict[str, Any]] = None      # e.g., {"row_count": 1, "rows": [{"order_number": "..."}]}
    logs: Optional[Dict[str, Any]] = None    # e.g., {"fault_config": {...}, "error_count": 0}


class TestVerdict(BaseModel):
    """Structured, auditable verdict for test scenario execution."""
    status: Literal["PASS", "FAIL", "BLOCKED"]
    reason: str
    evidence: LayerEvidence = Field(default_factory=LayerEvidence)
    trace: List[Dict[str, Any]] = Field(default_factory=list)


def evaluate_order_reconciliation(
    evidence: LayerEvidence,
    trace: List[Dict[str, Any]],
    guardrail_result: Optional[GuardrailResult] = None,
    expected_order_number: Optional[str] = None
) -> TestVerdict:
    """Evaluate multi-layer evidence with zero-hallucination rules for order reconciliation.
    
    Rules:
    1. If guardrail is tripped -> BLOCKED with guardrail reason.
    2. Zero-Hallucination: PASS requires consistent order_number across available UI, API, and DB layers.
    3. If DB order record is missing while UI reported success -> FAIL (Detects Silent Backend Failures).
    4. If order numbers mismatch between layers -> FAIL.
    """
    # 1. Guardrail Tripped Check
    if guardrail_result and guardrail_result.tripped:
        return TestVerdict(
            status="BLOCKED",
            reason=guardrail_result.reason or "Execution blocked by circuit breaker guardrail",
            evidence=evidence,
            trace=trace
        )

    # 2. Layer Extraction
    ui_order = None
    if evidence.ui:
        ui_order = evidence.ui.get("order_number")

    api_order = None
    if evidence.api:
        body = evidence.api.get("body") or {}
        api_order = body.get("order_number")

    db_order = None
    if evidence.db:
        rows = evidence.db.get("rows") or []
        if rows and len(rows) > 0:
            db_order = rows[0].get("order_number")

    target_order = expected_order_number or ui_order or api_order or db_order

    if not target_order:
        return TestVerdict(
            status="FAIL",
            reason="No order number captured in any layer (UI, API, or DB).",
            evidence=evidence,
            trace=trace
        )

    # 3. Cross-layer consistency checks
    # Check UI vs DB
    if ui_order and not db_order:
        return TestVerdict(
            status="FAIL",
            reason=f"Zero-Hallucination Violation: UI reported success for order '{ui_order}', but no matching record found in Database (Silent Failure).",
            evidence=evidence,
            trace=trace
        )

    # Check API vs DB
    if api_order and not db_order:
        return TestVerdict(
            status="FAIL",
            reason=f"Zero-Hallucination Violation: API returned order '{api_order}', but Database has 0 matching records.",
            evidence=evidence,
            trace=trace
        )

    # Check Mismatch between UI and DB
    if ui_order and db_order and ui_order != db_order:
        return TestVerdict(
            status="FAIL",
            reason=f"Cross-layer mismatch: UI order '{ui_order}' != DB order '{db_order}'.",
            evidence=evidence,
            trace=trace
        )

    # Check Mismatch between API and DB
    if api_order and db_order and api_order != db_order:
        return TestVerdict(
            status="FAIL",
            reason=f"Cross-layer mismatch: API order '{api_order}' != DB order '{db_order}'.",
            evidence=evidence,
            trace=trace
        )

    # 4. Valid PASS
    return TestVerdict(
        status="PASS",
        reason=f"Multi-layer reconciliation verified: Order '{target_order}' is consistent across all verified layers (UI={ui_order}, API={api_order}, DB={db_order}).",
        evidence=evidence,
        trace=trace
    )
