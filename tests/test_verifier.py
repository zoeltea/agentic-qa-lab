"""Unit tests for Phase 4 Verifier — Multi-Layer Cross-Checking with Fault Injection Scenarios."""
import pytest
from agent.verifier import (
    Verifier,
    FaultInjectionConfig,
    Verdict,
    verify_cross_layer,
)


def test_normal_pass_when_all_layers_consistent():
    """Semua layer UI, API, DB memiliki order_number yang sama -> PASS."""
    ui = {"order_number": "ORD-12345", "total": "Rp 700.000"}
    api = {"status_code": 200, "order_number": "ORD-12345"}
    db = {"rows": [{"order_number": "ORD-12345", "status": "PAID"}], "row_count": 1}

    verdict = verify_cross_layer(ui=ui, api=api, db=db)
    assert verdict.status == "PASS"
    assert "ORD-12345" in verdict.reason


def test_normal_fail_when_order_mismatch():
    """UI dan DB memiliki order_number berbeda -> FAIL."""
    ui = {"order_number": "ORD-12345"}
    api = {"status_code": 200, "order_number": "ORD-12345"}
    db = {"rows": [{"order_number": "ORD-99999", "status": "PAID"}], "row_count": 1}

    verdict = verify_cross_layer(ui=ui, api=api, db=db)
    assert verdict.status == "FAIL"
    assert "mismatch" in verdict.reason.lower()


def test_normal_fail_when_insufficient_evidence():
    """Hanya 1 layer yang punya bukti -> FAIL."""
    ui = {"order_number": "ORD-12345"}
    api = None
    db = None

    verdict = verify_cross_layer(ui=ui, api=api, db=db)
    assert verdict.status == "FAIL"
    assert "insufficient" in verdict.reason.lower()


def test_fault_silent_db_failure_detected():
    """Fault simulate_silent_db_failure aktif: UI ada order, tapi DB kosong -> ANOMALY_DETECTED."""
    fault_config = FaultInjectionConfig(simulate_silent_db_failure=True)
    ui = {"order_number": "ORD-SILENT-FAIL", "total": "Rp 500.000"}
    api = {"status_code": 200, "order_number": "ORD-SILENT-FAIL"}
    db = {"rows": [], "row_count": 0}  # DB write dropped

    verdict = verify_cross_layer(ui=ui, api=api, db=db, fault_config=fault_config)
    assert verdict.status == "ANOMALY_DETECTED"
    assert "Silent DB Failure" in verdict.reason


def test_fault_corrupted_stock_detected():
    """Fault simulate_corrupted_stock aktif: UI cart stock != DB stock -> ANOMALY_DETECTED."""
    fault_config = FaultInjectionConfig(simulate_corrupted_stock=True)
    ui = {"stock": 5, "order_number": "ORD-123"}
    api = {"status_code": 200, "order_number": "ORD-123"}
    db = {"stock": 10, "rows": [{"order_number": "ORD-123"}], "row_count": 1}

    verdict = verify_cross_layer(ui=ui, api=api, db=db, fault_config=fault_config)
    assert verdict.status == "ANOMALY_DETECTED"
    assert "Stock Corruption" in verdict.reason


def test_fault_slow_db_detected_with_error_logs():
    """Fault simulate_slow_db_ms aktif & logs menunjukkan timeout/error -> ANOMALY_DETECTED."""
    fault_config = FaultInjectionConfig(simulate_slow_db_ms=5000)
    ui = {"order_number": "ORD-SLOW"}
    api = {"status_code": 200, "order_number": "ORD-SLOW"}
    db = {"rows": [{"order_number": "ORD-SLOW"}], "row_count": 1}
    logs = {"error_count": 1, "fault_config": {"simulate_slow_db_ms": 5000}}

    verdict = verify_cross_layer(ui=ui, api=api, db=db, logs=logs, fault_config=fault_config)
    assert verdict.status == "ANOMALY_DETECTED"
    assert "Slow DB" in verdict.reason
