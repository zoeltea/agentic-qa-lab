"""Standalone Demo Runner for Phase 5: Observability & Benchmarking Suite."""
import json
from agent.verifier import FaultInjectionConfig
from agent.benchmark import BenchmarkRunner


def run_benchmark_demo():
    print("=" * 80)
    print("📊 PHASE 5 DEMO: OBSERVABILITY & BENCHMARKING SUITE SHOWCASE")
    print("=" * 80)
    print("Running automated 4-scenario benchmark matrix with metrics instrumentation...\n")

    runner = BenchmarkRunner()

    scenarios = [
        {
            "name": "Scenario 1: Normal E2E Checkout Flow",
            "fault_injected": False,
            "fault_type": None,
            "fault_config": FaultInjectionConfig(),
            "ui": {
                "order_number": "ORD-2026-BENCH-001",
                "total": "Rp 700.000",
                "voucher_code": "DISKON10",
                "stock": 9,
            },
            "api": {
                "status_code": 200,
                "order_number": "ORD-2026-BENCH-001",
                "status": "PAID",
            },
            "db": {
                "rows": [{"order_number": "ORD-2026-BENCH-001", "status": "PAID", "total_amount": 700000}],
                "stock": 9,
                "row_count": 1,
            },
            "prompt_tokens": 1250,
            "completion_tokens": 320,
            "ui_latency": 0.12,
            "api_latency": 0.03,
            "db_latency": 0.015,
            "turns": 8,
        },
        {
            "name": "Scenario 2: Fault Injection — Silent DB Failure",
            "fault_injected": True,
            "fault_type": "silent_db_failure",
            "fault_config": FaultInjectionConfig(simulate_silent_db_failure=True),
            "ui": {
                "order_number": "ORD-2026-SILENT-FAIL",
                "total": "Rp 700.000",
            },
            "api": {
                "status_code": 200,
                "order_number": "ORD-2026-SILENT-FAIL",
                "status": "PAID",
            },
            "db": None,  # Silent drop of DB write
            "prompt_tokens": 1100,
            "completion_tokens": 280,
            "ui_latency": 0.10,
            "api_latency": 0.025,
            "db_latency": 0.01,
            "turns": 6,
        },
        {
            "name": "Scenario 3: Fault Injection — Corrupted Stock",
            "fault_injected": True,
            "fault_type": "corrupted_stock",
            "fault_config": FaultInjectionConfig(simulate_corrupted_stock=True),
            "ui": {
                "order_number": "ORD-2026-STOCK-TAMPER",
                "stock": 5,
            },
            "api": {
                "status_code": 200,
                "order_number": "ORD-2026-STOCK-TAMPER",
            },
            "db": {
                "rows": [{"order_number": "ORD-2026-STOCK-TAMPER"}],
                "stock": 10,  # Desynchronized / corrupted
            },
            "prompt_tokens": 980,
            "completion_tokens": 240,
            "ui_latency": 0.09,
            "api_latency": 0.02,
            "db_latency": 0.01,
            "turns": 5,
        },
        {
            "name": "Scenario 4: Fault Injection — Slow DB Latency Anomaly",
            "fault_injected": True,
            "fault_type": "slow_db_ms",
            "fault_config": FaultInjectionConfig(simulate_slow_db_ms=8000),
            "ui": {
                "order_number": "ORD-2026-SLOW-DB",
            },
            "api": {
                "status_code": 200,
                "order_number": "ORD-2026-SLOW-DB",
            },
            "db": {
                "rows": [{"order_number": "ORD-2026-SLOW-DB"}],
            },
            "logs": {
                "error_count": 1,
            },
            "prompt_tokens": 1050,
            "completion_tokens": 260,
            "ui_latency": 0.11,
            "api_latency": 0.03,
            "db_latency": 0.08,
            "turns": 6,
        },
    ]

    report = runner.run_matrix(scenarios)

    print(report.to_markdown_table())
    print("\n" + "=" * 80)
    print("📈 AGGREGATED METRICS SUMMARY REPORT")
    print("=" * 80)
    summary_json = {
        "total_runs": report.total_runs,
        "passed_runs": report.passed_runs,
        "anomalies_detected": report.anomalies_detected,
        "false_pass_rate_percent": f"{report.false_pass_rate_percent}%",
        "anomaly_recall_percent": f"{report.anomaly_recall_percent}%",
        "mean_tokens_per_run": report.mean_tokens_per_run,
        "total_cost_usd": f"${report.total_cost_usd:.6f}",
        "mean_duration_sec": f"{report.mean_duration_sec:.4f}s",
    }
    print(json.dumps(summary_json, indent=2))
    print("=" * 80)
    print("✅ BENCHMARK SUITE COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark_demo()
