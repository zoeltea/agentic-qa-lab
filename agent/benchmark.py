"""Benchmark Suite & False-Pass Rate Asserter for Multi-Layer Agentic QA."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import uuid

from agent.metrics import TokenCostTracker, LatencyProfiler, RunMetrics
from agent.verifier import Verifier, FaultInjectionConfig, verify_cross_layer


@dataclass
class BenchmarkReport:
    """Aggregated quality and efficiency metrics across a benchmark suite run."""
    total_runs: int = 0
    passed_runs: int = 0
    anomalies_detected: int = 0
    failed_runs: int = 0
    blocked_runs: int = 0
    false_pass_count: int = 0
    false_pass_rate_percent: float = 0.0     # Target: 0.0%
    anomaly_recall_percent: float = 0.0      # Target: 100.0%
    mean_duration_sec: float = 0.0
    mean_tokens_per_run: float = 0.0
    total_cost_usd: float = 0.0
    runs: List[RunMetrics] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "passed_runs": self.passed_runs,
            "anomalies_detected": self.anomalies_detected,
            "failed_runs": self.failed_runs,
            "blocked_runs": self.blocked_runs,
            "false_pass_count": self.false_pass_count,
            "false_pass_rate_percent": self.false_pass_rate_percent,
            "anomaly_recall_percent": self.anomaly_recall_percent,
            "mean_duration_sec": self.mean_duration_sec,
            "mean_tokens_per_run": self.mean_tokens_per_run,
            "total_cost_usd": self.total_cost_usd,
            "runs": [
                {
                    "run_id": r.run_id,
                    "scenario_name": r.scenario_name,
                    "verdict_status": r.verdict_status,
                    "total_tokens": r.total_tokens,
                    "estimated_cost_usd": r.estimated_cost_usd,
                    "total_duration_sec": r.total_duration_sec,
                    "fault_injected": r.fault_injected,
                    "fault_type": r.fault_type,
                }
                for r in self.runs
            ],
        }

    def to_markdown_table(self) -> str:
        lines = [
            "| Scenario | Fault Injected | Verdict | Tokens | Cost ($) | Latency (s) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]
        for r in self.runs:
            fault_flag = f"Yes ({r.fault_type})" if r.fault_injected else "No"
            status_icon = "✅" if r.verdict_status in ("PASS", "ANOMALY_DETECTED") else "❌"
            lines.append(
                f"| {r.scenario_name} | {fault_flag} | {status_icon} `{r.verdict_status}` | "
                f"{r.total_tokens:,} | ${r.estimated_cost_usd:.5f} | {r.total_duration_sec:.3f}s |"
            )
        lines.append("")
        lines.append(f"**Summary:** Total Runs: {self.total_runs} | False-Pass Rate: `{self.false_pass_rate_percent:.1f}%` | Anomaly Recall: `{self.anomaly_recall_percent:.1f}%` | Total Cost: `${self.total_cost_usd:.5f}`")
        return "\n".join(lines)


class BenchmarkRunner:
    """Executes test scenarios under normal and fault-injected states and computes quality metrics."""

    def __init__(self, verifier_engine: Optional[Verifier] = None):
        self.verifier = verifier_engine or Verifier()

    def run_matrix(self, scenarios: List[Dict[str, Any]]) -> BenchmarkReport:
        """
        Runs the benchmarking matrix:
        - Evaluates each scenario across UI/API/DB/Log evidence layers.
        - Profiles latency & token usage.
        - Calculates False-Pass Rate and Recall.
        """
        run_results: List[RunMetrics] = []
        total_tokens_all = 0
        total_cost_all = 0.0
        total_duration_all = 0.0

        passed_count = 0
        anomalies_count = 0
        failed_count = 0
        blocked_count = 0
        false_pass_count = 0
        fault_scenarios_count = 0

        for sc in scenarios:
            run_id = f"run-{uuid.uuid4().hex[:8]}"
            scenario_name = sc.get("name", "unnamed_scenario")
            fault_config = sc.get("fault_config", FaultInjectionConfig())
            fault_injected = sc.get("fault_injected", False)
            fault_type = sc.get("fault_type", None)

            # Token & Latency tracking
            tracker = TokenCostTracker(model=sc.get("model", "default"))
            tracker.record_usage(
                prompt_tokens=sc.get("prompt_tokens", 850),
                completion_tokens=sc.get("completion_tokens", 180),
            )

            profiler = LatencyProfiler()
            # Simulate layer execution profiles
            ui_lat = sc.get("ui_latency", 0.08)
            api_lat = sc.get("api_latency", 0.02)
            db_lat = sc.get("db_latency", 0.01)
            profiler.record_layer_latency("ui", ui_lat)
            profiler.record_layer_latency("api", api_lat)
            profiler.record_layer_latency("db", db_lat)
            profiler.record_layer_latency("orchestrator", 0.01)

            # Cross-layer verification execution
            evidence_ui = sc.get("ui")
            evidence_api = sc.get("api")
            evidence_db = sc.get("db")
            evidence_logs = sc.get("logs")

            self.verifier.set_fault_config(fault_config)
            verdict = self.verifier.verify_cross_layer(
                ui=evidence_ui,
                api=evidence_api,
                db=evidence_db,
                logs=evidence_logs,
            )

            duration = round(ui_lat + api_lat + db_lat + 0.02, 4)

            # Check quality metrics
            if fault_injected:
                fault_scenarios_count += 1
                if verdict.status == "PASS":
                    # Hallucination / Missed anomaly!
                    false_pass_count += 1
                elif verdict.status == "ANOMALY_DETECTED":
                    anomalies_count += 1
                elif verdict.status == "FAIL":
                    failed_count += 1
                elif verdict.status == "BLOCKED":
                    blocked_count += 1
            else:
                if verdict.status == "PASS":
                    passed_count += 1
                elif verdict.status == "FAIL":
                    failed_count += 1
                elif verdict.status == "BLOCKED":
                    blocked_count += 1
                elif verdict.status == "ANOMALY_DETECTED":
                    anomalies_count += 1

            total_tokens_all += tracker.total_tokens
            total_cost_all += tracker.estimated_cost_usd
            total_duration_all += duration

            metrics = RunMetrics(
                run_id=run_id,
                scenario_name=scenario_name,
                verdict_status=verdict.status,
                total_turns=sc.get("turns", 4),
                total_tokens=tracker.total_tokens,
                prompt_tokens=tracker.prompt_tokens,
                completion_tokens=tracker.completion_tokens,
                estimated_cost_usd=tracker.estimated_cost_usd,
                total_duration_sec=duration,
                layer_latency_breakdown=profiler.layer_latencies,
                fault_injected=fault_injected,
                fault_type=fault_type,
            )
            run_results.append(metrics)

        total_runs = len(scenarios)
        mean_dur = round(total_duration_all / max(1, total_runs), 4)
        mean_tok = round(total_tokens_all / max(1, total_runs), 1)

        # FPR: Fault scenarios yang lolos sebagai PASS
        fpr = round((false_pass_count / max(1, fault_scenarios_count)) * 100.0, 2) if fault_scenarios_count > 0 else 0.0

        # Anomaly Recall: Fault scenarios yang berhasil ditangkap sebagai ANOMALY_DETECTED
        recall = round((anomalies_count / max(1, fault_scenarios_count)) * 100.0, 2) if fault_scenarios_count > 0 else 100.0

        return BenchmarkReport(
            total_runs=total_runs,
            passed_runs=passed_count,
            anomalies_detected=anomalies_count,
            failed_runs=failed_count,
            blocked_runs=blocked_count,
            false_pass_count=false_pass_count,
            false_pass_rate_percent=fpr,
            anomaly_recall_percent=recall,
            mean_duration_sec=mean_dur,
            mean_tokens_per_run=mean_tok,
            total_cost_usd=round(total_cost_all, 6),
            runs=run_results,
        )
