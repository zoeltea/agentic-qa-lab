"""Core Verifier Module — Multi-Layer Cross-Checking Engine with Fault Injection Awareness."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class FaultInjectionConfig(BaseModel):
    """Keadaan fault injection saat ini — diambil dari DB atau guardrails."""
    simulate_silent_db_failure: bool = False
    simulate_slow_db_ms: int = 0
    simulate_corrupted_stock: bool = False


class LayerEvidence(BaseModel):
    """Evidence captured dari masing-masing layer (UI/API/DB)."""
    ui: Optional[Dict[str, Any]] = None      # ex: {"order_number": "ORD-...", "total": "Rp 700.000", "voucher": "DISKON10"}
    api: Optional[Dict[str, Any]] = None     # ex: {"status_code": 200, "body": {"order_number": "ORD-...", "status": "PAID"}}
    db: Optional[Dict[str, Any]] = None      # ex: {"rows": [{"order_number": "ORD-...", "status": "PAID", "total": 700000}], "row_count": 1}
    logs: Optional[Dict[str, Any]] = None    # ex: {"fault_config": {"simulate_silent_db_failure": 1}, ...}


class Verdict(BaseModel):
    """Structured verdict untuk multi-layer verification."""
    status: str = Field(..., description="PASS | FAIL | BLOCKED | ANOMALY_DETECTED")
    reason: str = Field(..., description="Human-readable explanation")
    evidence: LayerEvidence = Field(default_factory=LayerEvidence)
    fault_config: Optional[FaultInjectionConfig] = Field(default=None)
    trace: List[Dict[str, Any]] = Field(default_factory=list)


@dataclass
class Verifier:
    """Multi-layer cross-checker engine with fault injection awareness."""
    fault_config: FaultInjectionConfig = field(default_factory=FaultInjectionConfig)

    def set_fault_config(self, config: FaultInjectionConfig):
        self.fault_config = config

    def verify_cross_layer(
        self,
        ui: Optional[Dict[str, Any]],
        api: Optional[Dict[str, Any]],
        db: Optional[Dict[str, Any]],
        logs: Optional[Dict[str, Any]] = None,
    ) -> Verdict:
        """
        Cross-layer verification with fault injection awareness:
        Priority order: Fault checks -> Layer consistency -> Verdict
        """
        # 1. Check fault injection configs
        result = self._check_fault_injection(ui, api, db, logs)
        if result["tripped"]:
            return Verdict(
                status="ANOMALY_DETECTED",
                reason=result["reason"],
                evidence=LayerEvidence(
                    ui=ui, api=api, db=db, logs=logs,
                ),
                fault_config=self.fault_config,
                trace=[{"step": "fault_check", "result": result}],
            )

        # 2. Normal cross-layer consistency check
        verdict = self._normal_cross_layer(ui, api, db)
        return verdict

    def _check_fault_injection(
        self,
        ui: Optional[Dict[str, Any]],
        api: Optional[Dict[str, Any]],
        db: Optional[Dict[str, Any]],
        logs: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check semua 3 fault injection scenario."""
        reasons: list[str] = []

        # Scenario 1: Silent DB Failure
        # Jika simulate_silent_db_failure aktif:
        # - API return 200 sukses (order_number ada)
        # - Tapi DB order record missing/different
        if self.fault_config.simulate_silent_db_failure:
            ui_order = ui.get("order_number") if isinstance(ui, dict) else None
            db_order = self._extract_db_order_number(db) if isinstance(db, dict) else None
            if ui_order and not db_order:
                reasons.append(
                    f"ANOMALY_DETECTED: Silent DB Failure - UI reported order '{ui_order}' "
                    f"but no matching record in database (API success but DB write dropped)"
                )
            # Jika UI missing order_number tapi DB ada → juga anomaly
            elif ui_order is None and db_order:
                reasons.append(
                    f"ANOMALY_DETECTED: Silent DB Failure - Database has order '{db_order}' "
                    f"but UI reported no order number"
                )

        # Scenario 2: Slow DB Response
        # Jika simulate_slow_db_ms > 0 & latency terlalu lama
        if self.fault_config.simulate_slow_db_ms > 0:
            # Cek logs untuk latency info
            if logs and isinstance(logs, dict):
                error_count = logs.get("error_count", 0)
                if error_count > 0:
                    reasons.append(
                        f"ANOMALY_DETECTED: Slow DB Response - "
                        f"Fault injection simulate_slow_db_ms={self.fault_config.simulate_slow_db_ms}ms "
                        f"triggered database latency anomalies"
                    )

        # Scenario 3: Corrupted Stock
        # Jika simulate_corrupted_stock aktif:
        # - Check stock consistency antar layer
        ui_stock = self._extract_stock(ui) if isinstance(ui, dict) else None
        db_stock = self._extract_stock(db) if isinstance(db, dict) else None
        if self.fault_config.simulate_corrupted_stock:
            if ui_stock is not None and db_stock is not None and ui_stock != db_stock:
                reasons.append(
                    f"ANOMALY_DETECTED: Stock Corruption - "
                    f"UI stock={ui_stock} != DB stock={db_stock} "
                    f"(database state may have been tampered or stale)"
                )

        if reasons:
            return {"tripped": True, "reason": " | ".join(reasons)}
        return {"tripped": False, "reason": ""}

    def _normal_cross_layer(self, ui, api, db) -> Verdict:
        """Normal cross-layer verification tanpa fault injection."""
        # Extract order numbers dari setiap layer
        ui_order = self._extract_order_number(ui) if isinstance(ui, dict) else None
        api_order = self._extract_order_number(api) if isinstance(api, dict) else None
        db_order = self._extract_order_number(db) if isinstance(db, dict) else None

        # Check: Semua layer harus punya order number
        if not ui_order and not api_order and not db_order:
            return Verdict(
                status="FAIL",
                reason="FAIL: No order number captured in any layer (UI, API, or DB).",
                evidence=LayerEvidence(ui=ui, api=api, db=db),
            )

        # Jika hanya 1 layer punya order number → FAIL (tidak cukup bukti)
        if sum(x is not None for x in [ui_order, api_order, db_order]) < 2:
            return Verdict(
                status="FAIL",
                reason="FAIL: Insufficient evidence across layers (at least 2 layers must have order numbers).",
                evidence=LayerEvidence(ui=ui, api=api, db=db),
            )

        # Cek konsistensi antara UI dan DB
        if ui_order and db_order and ui_order != db_order:
            return Verdict(
                status="FAIL",
                reason=f"Cross-layer mismatch: UI order '{ui_order}' != DB order '{db_order}'.",
                evidence=LayerEvidence(ui=ui, api=api, db=db),
            )

        # Cek konsistensi antara API dan DB
        if api_order and db_order and api_order != db_order:
            return Verdict(
                status="FAIL",
                reason=f"Cross-layer mismatch: API order '{api_order}' != DB order '{db_order}'.",
                evidence=LayerEvidence(ui=ui, api=api, db=db),
            )

        # Semua layer konsisten → PASS
        # Ambil order number yang muncul (prioritas: UI > API > DB, pertama yang tidak None)
        final_order = ui_order or api_order or db_order
        return Verdict(
            status="PASS",
            reason=f"Multi-layer reconciliation verified: Order '{final_order}' is consistent across all verified layers.",
            evidence=LayerEvidence(ui=ui, api=api, db=db),
        )

    @staticmethod
    def _extract_order_number(data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Ekstrak order_number dari dict apa pun (termasuk format rows DB)."""
        if not isinstance(data, dict):
            return None
        # Format DB query result: {"rows": [{"order_number": ...}]}
        if "rows" in data and isinstance(data["rows"], list) and len(data["rows"]) > 0:
            row0 = data["rows"][0]
            if isinstance(row0, dict) and "order_number" in row0:
                return row0.get("order_number")
        # Format direct: {"order_number": ...}
        return data.get("order_number")

    @staticmethod
    def _extract_stock(data: Optional[Dict[str, Any]]) -> Optional[int]:
        """Ekstrak stock value dari dict apa pun."""
        if not isinstance(data, dict):
            return None
        # Coba berbagai field stock
        for key in ["stock", "total_stock", "cart_stock", "inventory"]:
            if key in data:
                val = data[key]
                if isinstance(val, (int, float)):
                    return int(val)
        return None

    @staticmethod
    def _extract_db_order_number(data: Optional[Dict[str, Any]]) -> Optional[str]:
        """Ekstrak order_number khusus dari output DB query."""
        if not isinstance(data, dict):
            return None
        # DB query result bisa berformat rows:[{order_number:...}] atau langsung {order_number:...}
        if "rows" in data and isinstance(data["rows"], list) and len(data["rows"]) > 0:
            return data["rows"][0].get("order_number")
        return data.get("order_number")


# Convenience function
def verify_cross_layer(
    ui: Optional[Dict[str, Any]],
    api: Optional[Dict[str, Any]],
    db: Optional[Dict[str, Any]],
    logs: Optional[Dict[str, Any]] = None,
    fault_config: Optional[FaultInjectionConfig] = None,
) -> Verdict:
    """Fungsi helper untuk verifikasi cross-layer dengan sekali instantiate."""
    verifier = Verifier(fault_config=fault_config or FaultInjectionConfig())
    return verifier.verify_cross_layer(ui, api, db, logs)