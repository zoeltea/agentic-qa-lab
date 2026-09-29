"""Tests for BenchmarkRunner and BenchmarkReport."""
import pytest
from agent.benchmark import BenchmarkRunner, BenchmarkReport
from agent.verifier import FaultInjectionConfig


def test_benchmark_runner_zero_false_pass_rate():
    """Verify that under fault injection, no faults pass silently (FPR = 0.0%)."""
    runner = BenchmarkRunner()

    scenarios = [
        {
            "name": "Normal Checkout",
            "fault_injected": False,
            "fault_config": FaultInjectionConfig(),
            "ui": {"order_number": "ORD-123", "stock": 5},
            "api": {"status_code": 200, "order_number": "ORD-123"},
            "db": {"rows": [{"order_number": "ORD-123"}], "stock": 5},
        },
        {
            "name": "Silent DB Failure",
            "fault_injected": True,
            "fault_type": "silent_db_failure",
            "fault_config": FaultInjectionConfig(simulate_silent_db_failure=True),
            "ui": {"order_number": "ORD-FAIL"},
            "api": {"status_code": 200, "order_number": "ORD-FAIL"},
            "db": None,  # Missing DB write
        },
        {
            "name": "Corrupted Stock",
            "fault_injected": True,
            "fault_type": "corrupted_stock",
            "fault_config": FaultInjectionConfig(simulate_corrupted_stock=True),
            "ui": {"order_number": "ORD-456", "stock": 3},
            "api": {"status_code": 200, "order_number": "ORD-456"},
            "db": {"rows": [{"order_number": "ORD-456"}], "stock": 8},
        },
    ]

    report = runner.run_matrix(scenarios)

    assert report.total_runs == 3
    assert report.passed_runs == 1
    assert report.anomalies_detected == 2
    assert report.false_pass_count == 0
    assert report.false_pass_rate_percent == 0.0
    assert report.anomaly_recall_percent == 100.0


def test_benchmark_runner_anomaly_recall_100():
    """Verify that all fault injections are reliably captured with 100% recall."""
    runner = BenchmarkRunner()

    scenarios = [
        {
            "name": "Slow DB Latency Anomaly",
            "fault_injected": True,
            "fault_type": "slow_db_ms",
            "fault_config": FaultInjectionConfig(simulate_slow_db_ms=8000),
            "ui": {"order_number": "ORD-SLOW"},
            "api": {"status_code": 200, "order_number": "ORD-SLOW"},
            "db": {"rows": [{"order_number": "ORD-SLOW"}]},
            "logs": {"error_count": 1},
        },
    ]

    report = runner.run_matrix(scenarios)

    assert report.total_runs == 1
    assert report.anomalies_detected == 1
    assert report.anomaly_recall_percent == 100.0
    assert report.false_pass_rate_percent == 0.0


def test_benchmark_report_summary_aggregation():
    """Verify aggregation metrics, dictionary conversion, and Markdown table output."""
    runner = BenchmarkRunner()

    scenarios = [
        {
            "name": "Normal Scenario",
            "fault_injected": False,
            "fault_config": FaultInjectionConfig(),
            "ui": {"order_number": "ORD-OK"},
            "api": {"status_code": 200, "order_number": "ORD-OK"},
            "db": {"rows": [{"order_number": "ORD-OK"}]},
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "ui_latency": 0.10,
            "api_latency": 0.05,
            "db_latency": 0.02,
        },
    ]

    report = runner.run_matrix(scenarios)

    assert report.total_runs == 1
    assert report.mean_tokens_per_run == 1200.0
    assert report.total_cost_usd > 0.0
    assert report.mean_duration_sec > 0.0

    # Serialization
    report_dict = report.to_dict()
    assert report_dict["total_runs"] == 1
    assert len(report_dict["runs"]) == 1

    # Markdown table
    md_table = report.to_markdown_table()
    assert "| Scenario | Fault Injected | Verdict |" in md_table
    assert "Normal Scenario" in md_table
    assert "False-Pass Rate: `0.0%`" in md_table
