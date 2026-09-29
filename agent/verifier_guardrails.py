"""Verifier Guardrails for Multi-Layer Cross-Checking and State Consistency."""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class GuardrailResult:
    """Result of a verifier guardrail check."""
    tripped: bool
    reason: Optional[str] = None
    action: str = "continue"  # continue | abort | retry


class VerifierGuardrails:
    """Guardrails specifically designed for Verifier — ensures verification is consistent, mature, and non-redundant."""

    def __init__(
        self,
        max_cross_layer_checks: int = 5,
        min_evidence_layers: int = 2,
        duplication_threshold: int = 3,
    ):
        self.max_cross_layer_checks = max_cross_layer_checks
        self.min_evidence_layers = min_evidence_layers
        self.duplication_threshold = duplication_threshold
        self._check_history: List[str] = []

    def check_evidence_completeness(self, evidence_layers: int) -> GuardrailResult:
        """Check if minimum required evidence layers are collected before deciding a verdict."""
        if evidence_layers < self.min_evidence_layers:
            return GuardrailResult(
                tripped=True,
                reason=f"Insufficient evidence layers: collected {evidence_layers}, minimum required is {self.min_evidence_layers}.",
                action="abort",
            )
        return GuardrailResult(tripped=False, action="continue")

    def check_duplication(self, check_description: str) -> GuardrailResult:
        """Prevent verifier from executing the same check repeatedly without progress."""
        self._check_history.append(check_description)
        count = self._check_history.count(check_description)
        if count >= self.duplication_threshold:
            return GuardrailResult(
                tripped=True,
                reason=f"Duplication threshold reached for check '{check_description}' ({count} times).",
                action="abort",
            )
        return GuardrailResult(tripped=False, action="continue")

    def check_maturity(self, verdict: str, checks_done: int) -> GuardrailResult:
        """Ensure verifier does not prematurely issue a PASS verdict before verifying cross-layers."""
        if verdict == "PASS" and checks_done < 3:
            return GuardrailResult(
                tripped=True,
                reason=f"Premature PASS verdict: only {checks_done} checks performed, minimum required is 3.",
                action="retry",
            )
        return GuardrailResult(tripped=False, action="continue")
