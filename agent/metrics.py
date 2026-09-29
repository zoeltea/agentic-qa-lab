"""Observability & Metrics Instrumentation Module.

Tracks token consumption, estimated USD cost, and latency breakdown per execution layer.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time


# Pricing table per 1,000,000 tokens (USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "default": {"prompt": 0.50, "completion": 1.50},  # $0.50 prompt / $1.50 completion
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "claude-3-5-haiku": {"prompt": 0.80, "completion": 4.00},
    "omniroute/antigravity_combo": {"prompt": 0.50, "completion": 1.50},
}


@dataclass
class TokenCostTracker:
    """Tracks token consumption (prompt & completion) and calculates estimated USD cost."""
    model: str = "default"
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def record_usage(self, prompt_tokens: int, completion_tokens: int):
        """Record token usage for a single step or turn."""
        self.prompt_tokens += max(0, prompt_tokens)
        self.completion_tokens += max(0, completion_tokens)

    @property
    def total_tokens(self) -> int:
        """Total tokens accumulated."""
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Calculates total estimated cost in USD based on model pricing table."""
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING["default"])
        cost_prompt = (self.prompt_tokens / 1_000_000.0) * pricing["prompt"]
        cost_comp = (self.completion_tokens / 1_000_000.0) * pricing["completion"]
        return round(cost_prompt + cost_comp, 6)


@dataclass
class LatencyProfiler:
    """Profiles wall-clock execution time and tracks latency breakdown across architecture layers."""
    start_time: float = field(default_factory=time.perf_counter)
    turn_latencies: List[float] = field(default_factory=list)
    layer_latencies: Dict[str, float] = field(default_factory=lambda: {
        "ui": 0.0,
        "api": 0.0,
        "db": 0.0,
        "logs": 0.0,
        "orchestrator": 0.0,
    })

    def record_layer_latency(self, layer: str, duration_sec: float):
        """Record latency (in seconds) spent in a specific layer."""
        if layer in self.layer_latencies:
            self.layer_latencies[layer] = round(self.layer_latencies[layer] + max(0.0, duration_sec), 4)
        else:
            self.layer_latencies[layer] = round(max(0.0, duration_sec), 4)

    def record_turn_latency(self, duration_sec: float):
        """Record total duration of a single turn."""
        self.turn_latencies.append(round(max(0.0, duration_sec), 4))

    @property
    def total_duration_sec(self) -> float:
        """Total wall-clock duration in seconds since profiler initialization."""
        return round(time.perf_counter() - self.start_time, 4)


@dataclass
class RunMetrics:
    """Comprehensive observability metrics captured for a single test run."""
    run_id: str
    scenario_name: str
    verdict_status: str
    total_turns: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    total_duration_sec: float
    layer_latency_breakdown: Dict[str, float]
    fault_injected: bool = False
    fault_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize run metrics to dict."""
        return {
            "run_id": self.run_id,
            "scenario_name": self.scenario_name,
            "verdict_status": self.verdict_status,
            "total_turns": self.total_turns,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "total_duration_sec": self.total_duration_sec,
            "layer_latency_breakdown": self.layer_latency_breakdown,
            "fault_injected": self.fault_injected,
            "fault_type": self.fault_type,
        }
