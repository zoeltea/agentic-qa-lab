"""Phase 4 Demo — Multi-Layer Verification & Fault Injection Scenarios Showcase."""
import json
from agent.verifier import Verifier, FaultInjectionConfig, verify_cross_layer


def run_demo():
    print("=" * 80)
    print("🚀 PHASE 4 DEMO: MULTI-LAYER VERIFICATION & FAULT INJECTION SHOWCASE")
    print("=" * 80)

    # -------------------------------------------------------------
    # Scenario 1: Normal Checkout Flow (Cross-Layer Reconciliation)
    # -------------------------------------------------------------
    print("\n--- SCENARIO 1: NORMAL CHECKOUT (ALL LAYERS CONSISTENT) ---")
    ui_normal = {
        "order_number": "ORD-2026-NORMAL-8891",
        "total": "Rp 700.000",
        "voucher_code": "DISKON10",
        "stock": 9,
    }
    api_normal = {
        "status_code": 200,
        "order_number": "ORD-2026-NORMAL-8891",
        "status": "PAID",
    }
    db_normal = {
        "rows": [{"order_number": "ORD-2026-NORMAL-8891", "status": "PAID", "total_amount": 700000}],
        "stock": 9,
        "row_count": 1,
    }

    verdict_1 = verify_cross_layer(ui=ui_normal, api=api_normal, db=db_normal)
    print(f"Status : {verdict_1.status}")
    print(f"Reason : {verdict_1.reason}")
    print("Verdict JSON:")
    print(json.dumps(verdict_1.model_dump(), indent=2))

    # -------------------------------------------------------------
    # Scenario 2: Fault Injection — Silent DB Failure
    # -------------------------------------------------------------
    print("\n--- SCENARIO 2: FAULT INJECTION — SILENT DB FAILURE ---")
    fault_silent = FaultInjectionConfig(simulate_silent_db_failure=True)
    ui_silent = {
        "order_number": "ORD-2026-SILENT-FAIL",
        "total": "Rp 500.000",
    }
    api_silent = {
        "status_code": 200,
        "order_number": "ORD-2026-SILENT-FAIL",
    }
    db_silent = {
        "rows": [],  # DB write dropped/failed silently
        "row_count": 0,
    }

    verdict_2 = verify_cross_layer(
        ui=ui_silent, api=api_silent, db=db_silent, fault_config=fault_silent
    )
    print(f"Status : {verdict_2.status}")
    print(f"Reason : {verdict_2.reason}")

    # -------------------------------------------------------------
    # Scenario 3: Fault Injection — Corrupted Stock
    # -------------------------------------------------------------
    print("\n--- SCENARIO 3: FAULT INJECTION — CORRUPTED STOCK ---")
    fault_stock = FaultInjectionConfig(simulate_corrupted_stock=True)
    ui_stock = {
        "order_number": "ORD-2026-STOCK-TAMPER",
        "stock": 5,  # UI reports 5 left in stock
    }
    api_stock = {
        "status_code": 200,
        "order_number": "ORD-2026-STOCK-TAMPER",
    }
    db_stock = {
        "rows": [{"order_number": "ORD-2026-STOCK-TAMPER"}],
        "stock": 10,  # DB actually has 10 (discrepancy/tampered)
        "row_count": 1,
    }

    verdict_3 = verify_cross_layer(
        ui=ui_stock, api=api_stock, db=db_stock, fault_config=fault_stock
    )
    print(f"Status : {verdict_3.status}")
    print(f"Reason : {verdict_3.reason}")

    # -------------------------------------------------------------
    # Scenario 4: Fault Injection — Slow DB Latency Anomaly
    # -------------------------------------------------------------
    print("\n--- SCENARIO 4: FAULT INJECTION — SLOW DB RESPONSE ---")
    fault_slow = FaultInjectionConfig(simulate_slow_db_ms=8000)
    ui_slow = {"order_number": "ORD-2026-SLOW-LATENCY"}
    api_slow = {"status_code": 200, "order_number": "ORD-2026-SLOW-LATENCY"}
    db_slow = {"rows": [{"order_number": "ORD-2026-SLOW-LATENCY"}], "row_count": 1}
    logs_slow = {
        "error_count": 2,
        "fault_config": {"simulate_slow_db_ms": 8000},
        "message": "Gateway timeout / Query threshold exceeded (8000ms > 5000ms)",
    }

    verdict_4 = verify_cross_layer(
        ui=ui_slow, api=api_slow, db=db_slow, logs=logs_slow, fault_config=fault_slow
    )
    print(f"Status : {verdict_4.status}")
    print(f"Reason : {verdict_4.reason}")

    print("\n" + "=" * 80)
    print("✅ ALL 4 SCENARIOS DEMONSTRATED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
