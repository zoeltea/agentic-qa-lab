# Phase 5 Execution Plan & Collaboration Contract
## Observability & Benchmarking Suite (Tokens, Latency, False-Pass Rate) — AQA-5 / 587599d7

> **Project:** Agentic QA Lab & Portfolio (AutoQA-Agent)  
> **Target Workspace:** `/home/zoeltea/my_work/agentic-qa-lab`  
> **Collaborators:** Hermes Agent & OpenClaw (ben)  
> **Status:** Draft / Ready for Implementation  
> **Prerequisite:** Phase 4 MERGED to `master` (61 tests passed, Verifier & Fault Injection verified)

---

## 1. 🎯 Objective & Definition of Done

Membangun sistem **Observability & Benchmarking Suite** komprehensif untuk mengukur performa, efisiensi biaya, dan ketangguhan framework Agentic QA:
1. **Token & Cost Meter:** Mengukur konsumsi token (prompt & completion) dan estimasi biaya USD per test run / turn berdasarkan pricing model.
2. **Latency Profiler & Breakdown:** Merekam wall-clock execution time per turn, dekomposisi latency per layer (Browser/UI, REST API, SQLite DB, Log/Fault check, Reasoning loop).
3. **Benchmarking Matrix & False-Pass Rate Asserter:** Menjalankan matriks pengujian (Normal vs 3 Fault Injection scenarios) secara otomatis dan mengkalkulasi metrik kualitas SDET:
   - **False-Pass Rate (FPR):** Persentase skenario fault-injection yang lolos sebagai `PASS` (Target: **0.0%** / Zero-Hallucination).
   - **Anomaly Detection Recall:** Persentase anomali yang berhasil ditangkap sebagai `ANOMALY_DETECTED` (Target: **100.0%**).
   - **Mean Latency per Run** & **Mean Cost per Run ($)**.

### Definition of Done (DoD):
1. `agent/metrics.py` mengimplementasikan `TokenCostTracker`, `LatencyProfiler`, dan dataclass `RunMetrics`.
2. `agent/benchmark.py` mengimplementasikan `BenchmarkRunner` yang mengeksekusi test scenario matrix dan menghasilkan summary report (`BenchmarkReport`).
3. `tests/test_metrics.py` dan `tests/test_benchmark.py` lulus 100%.
4. Demo `python -m agent.benchmark_demo` mengeksekusi benchmarking matrix (4 skenario) dan menampilkan ringkasan metrik (Tokens, Cost, Latency, FPR=0%, Recall=100%).
5. Seluruh test suite `pytest tests/ -v` hijau 100%.

---

## 2. 👥 Division of Work (Hermes & OpenClaw)

```
[ Metrics & Cost Tracker ] ──► [ Benchmark Matrix Runner ] ──► [ Reporting & Demo ]
     (OpenClaw / ben)                    (Hermes)                      (Bersama)
            │                               │                              │
   tests/test_metrics.py         tests/test_benchmark.py         agent/benchmark_demo.py
```

| Step | Scope | Assignee | Deliverables / Files | Test Verification |
| :--- | :--- | :---: | :--- | :--- |
| **Step 1** | Token, Cost & Latency Metrics Engine | **OpenClaw (ben)** | `agent/metrics.py`<br>`tests/test_metrics.py` | `pytest tests/test_metrics.py` |
| **Step 2** | Benchmark Suite & False-Pass Asserter | **Hermes** | `agent/benchmark.py`<br>`tests/test_benchmark.py` | `pytest tests/test_benchmark.py` |
| **Step 3** | Benchmark Demo Runner & Integration | **Bersama** | `agent/benchmark_demo.py` | `python -m agent.benchmark_demo` + full `pytest tests/` |

---

## 3. 📐 Technical Specification & File Contracts

### 3.1 `agent/metrics.py` (OpenClaw / ben)

```python
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time


# Pricing table per 1M tokens (USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "default": {"prompt": 0.50, "completion": 1.50},  # $0.50 / $1.50 per 1M tokens
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "claude-3-5-haiku": {"prompt": 0.80, "completion": 4.00},
}


@dataclass
class TokenCostTracker:
    model: str = "default"
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def record_usage(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING["default"])
        cost_prompt = (self.prompt_tokens / 1_000_000.0) * pricing["prompt"]
        cost_comp = (self.completion_tokens / 1_000_000.0) * pricing["completion"]
        return round(cost_prompt + cost_comp, 6)


@dataclass
class LatencyProfiler:
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
        if layer in self.layer_latencies:
            self.layer_latencies[layer] += duration_sec

    @property
    def total_duration_sec(self) -> float:
        return round(time.perf_counter() - self.start_time, 4)


@dataclass
class RunMetrics:
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
```

### 3.2 `agent/benchmark.py` (Hermes)

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any
from agent.metrics import RunMetrics


@dataclass
class BenchmarkReport:
    total_runs: int
    passed_runs: int
    anomalies_detected: int
    failed_runs: int
    blocked_runs: int
    false_pass_count: int
    false_pass_rate_percent: float     # Must be 0.0%
    anomaly_recall_percent: float      # Must be 100.0%
    mean_duration_sec: float
    mean_tokens_per_run: float
    total_cost_usd: float
    runs: List[RunMetrics] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]: ...
    def to_markdown_table(self) -> str: ...


class BenchmarkRunner:
    """Executes test scenarios under normal and fault-injected states and computes quality metrics."""

    def __init__(self, verifier_engine, orchestrator_engine=None):
        self.verifier = verifier_engine
        self.orchestrator = orchestrator_engine

    def run_matrix(self, scenarios: List[Dict[str, Any]]) -> BenchmarkReport:
        """
        Runs the full benchmarking matrix:
        - Evaluates each scenario.
        - Profiles latency & token usage.
        - Calculates False-Pass Rate and Recall.
        """
        pass
```

### 3.3 `agent/benchmark_demo.py` (Bersama)

CLI Runner yang mengeksekusi 4 skenario benchmark matrix:
1. `SCENARIO_NORMAL`: Normal checkout flow -> Expected: `PASS`
2. `SCENARIO_SILENT_DB_FAILURE`: Fault injection -> Expected: `ANOMALY_DETECTED` (Must NOT be PASS)
3. `SCENARIO_CORRUPTED_STOCK`: Fault injection -> Expected: `ANOMALY_DETECTED` (Must NOT be PASS)
4. `SCENARIO_SLOW_DB`: Fault injection -> Expected: `ANOMALY_DETECTED` (Must NOT be PASS)

Menghasilkan tabel metrik eksekusi + ringkasan:
- False-Pass Rate: `0.0%`
- Anomaly Recall: `100.0%`
- Token, Latency & Cost Breakdown per scenario.

---

## 4. 🧪 Test Plan & Acceptance Criteria

### 4.1 `tests/test_metrics.py` (OpenClaw / ben)
1. `test_token_cost_tracker_calculation`: Verifikasi rumus hitung token dan pricing USD.
2. `test_latency_profiler_layer_breakdown`: Verifikasi akumulasi latency per layer (ui, api, db, logs).
3. `test_run_metrics_serialization`: Verifikasi struktur data `RunMetrics` terisi lengkap dan serializable.

### 4.2 `tests/test_benchmark.py` (Hermes)
1. `test_benchmark_runner_zero_false_pass_rate`: Verifikasi saat fault aktif, tidak ada false pass (FPR = 0.0%).
2. `test_benchmark_runner_anomaly_recall_100`: Verifikasi seluruh anomali terdeteksi (Recall = 100.0%).
3. `test_benchmark_report_summary_aggregation`: Verifikasi agregasi mean duration, total tokens, dan total cost.

---

## 5. 🚀 Execution Order

1. **Buat file `phase5_execution_plan.md` & checkout branch `feat/phase-5-observability-and-benchmarking`**.
2. **OpenClaw (ben):** Implementasi Step 1 (`agent/metrics.py` + `tests/test_metrics.py`) -> Test passed.
3. **Hermes:** Implementasi Step 2 (`agent/benchmark.py` + `tests/test_benchmark.py`) -> Test passed.
4. **Bersama:** Implementasi Step 3 (`agent/benchmark_demo.py`) + Full suite `pytest tests/` (semua hijau).
5. **Update status Plane.so AQA-5 ke Done** & Buat PR ke `master`.

---

*Dokumen ini adalah kontrak eksekusi resmi Phase 5 — implementasi mengikuti spec di atas.*
