"""Tests for TokenCostTracker, LatencyProfiler, and RunMetrics."""
import time
from agent.metrics import TokenCostTracker, LatencyProfiler, RunMetrics


def test_token_cost_tracker_calculation():
    """Verify token usage tracking and cost calculation for different models."""
    # 1. Default model ($0.50 prompt, $1.50 comp per 1M)
    tracker = TokenCostTracker(model="default")
    tracker.record_usage(prompt_tokens=1000, completion_tokens=500)
    assert tracker.prompt_tokens == 1000
    assert tracker.completion_tokens == 500
    assert tracker.total_tokens == 1500

    # 1000/1M * 0.50 = 0.0005, 500/1M * 1.50 = 0.00075 -> Total = 0.00125
    assert tracker.estimated_cost_usd == 0.00125

    # 2. Add more tokens
    tracker.record_usage(prompt_tokens=1000, completion_tokens=500)
    assert tracker.total_tokens == 3000
    assert tracker.estimated_cost_usd == 0.0025

    # 3. Specific model (gpt-4o-mini: $0.15 / $0.60 per 1M)
    mini_tracker = TokenCostTracker(model="gpt-4o-mini")
    mini_tracker.record_usage(prompt_tokens=100_000, completion_tokens=50_000)
    # 100k/1M * 0.15 = 0.015, 50k/1M * 0.60 = 0.030 -> Total = 0.045
    assert mini_tracker.estimated_cost_usd == 0.045


def test_latency_profiler_layer_breakdown():
    """Verify wall-clock latency measurement and layer decomposition."""
    profiler = LatencyProfiler()
    
    # Simulate layer durations
    profiler.record_layer_latency("ui", 0.15)
    profiler.record_layer_latency("api", 0.05)
    profiler.record_layer_latency("db", 0.02)
    profiler.record_layer_latency("logs", 0.01)
    profiler.record_layer_latency("ui", 0.10)  # accumulate ui

    assert profiler.layer_latencies["ui"] == 0.25
    assert profiler.layer_latencies["api"] == 0.05
    assert profiler.layer_latencies["db"] == 0.02
    assert profiler.layer_latencies["logs"] == 0.01
    assert profiler.layer_latencies["orchestrator"] == 0.0

    # Test turn latencies
    profiler.record_turn_latency(0.12)
    profiler.record_turn_latency(0.08)
    assert len(profiler.turn_latencies) == 2

    # Total duration is positive float
    assert profiler.total_duration_sec >= 0.0


def test_run_metrics_serialization():
    """Verify RunMetrics structure, properties, and dictionary serialization."""
    metrics = RunMetrics(
        run_id="run_test_001",
        scenario_name="Normal Checkout Flow",
        verdict_status="PASS",
        total_turns=8,
        total_tokens=2450,
        prompt_tokens=1800,
        completion_tokens=650,
        estimated_cost_usd=0.001875,
        total_duration_sec=1.452,
        layer_latency_breakdown={
            "ui": 0.85,
            "api": 0.25,
            "db": 0.10,
            "logs": 0.05,
            "orchestrator": 0.20,
        },
        fault_injected=False,
        fault_type=None,
    )

    data = metrics.to_dict()
    assert data["run_id"] == "run_test_001"
    assert data["verdict_status"] == "PASS"
    assert data["total_turns"] == 8
    assert data["total_tokens"] == 2450
    assert data["estimated_cost_usd"] == 0.001875
    assert data["fault_injected"] is False
    assert data["layer_latency_breakdown"]["ui"] == 0.85
