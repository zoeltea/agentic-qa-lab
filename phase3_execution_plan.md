# Phase 3 Execution Plan & Collaboration Contract
## Core Agentic QA Orchestration Engine with Strict Guardrails (AQA-3 / ed2804a1)

> **Project:** Agentic QA Lab & Portfolio (AutoQA-Agent)  
> **Target Workspace:** `/home/zoeltea/my_work/agentic-qa-lab`  
> **Collaborators:** Hermes Agent & OpenClaw (ben)  
> **Status:** Approved for Implementation  
> **Prerequisite:** Phase 2 DONE (38 test passed, 4 tools + registry + demo verified)

---

## 1. 🎯 Objective & Definition of Done

Membangun **otak agent** — ReAct reasoning loop yang deterministik — yang memanggil Phase 2 `ToolRegistry` langkah-demi-langkah, dijaga oleh circuit breaker agar tidak infinite-loop / hallucinate, dan diakhiri dengan structured verdict yang bisa diaudit.

### Definition of Done (DoD):
1. `agent/orchestrator.py` mengimplementasikan loop: `Plan → Select Tool → Execute (via ToolRegistry) → Observe → Evaluate` sampai verdict final atau guardrail trip.
2. `agent/guardrails.py` menyediakan `CircuitBreaker` (max turns), `LoopDetector` (ping-pong), `TokenBudgetGuard` + `ExecutionTimeoutGuard` dengan interface `GuardrailResult{tripped, reason, action}`.
3. `agent/evaluator.py` memvalidasi `TestVerdict` (PASS/FAIL + evidence per layer) dengan **zero-hallucination rule**: PASS ditolak jika bukti cross-layer tidak lengkap/inkonsisten.
4. Seluruh unit test `tests/test_guardrails.py`, `tests/test_evaluator.py`, `tests/test_orchestrator.py` lulus 100%.
5. Demo `python -m agent.orchestrator_demo` (atau via orchestrator API) menjalankan 1 skenario checkout E2E tanpa LLM live (menggunakan scripted/mock planner dulu) dan menghasilkan verdict JSON.

---

## 2. 👥 Division of Work (Hermes & OpenClaw)

```
[ Orchestrator (ReAct Loop) ] ──► [ Guardrails (Circuit Breaker) ] ──► [ Evaluator (Verdict) ]
         (Hermes)                          (OpenClaw / ben)                     (Hermes)
                                              │
[ Integration Test test_orchestrator.py ] ◄───┴─── (Bersama)
```

| Step | Scope | Assignee | Deliverables / Files | Test Verification |
| :--- | :--- | :---: | :--- | :--- |
| **Step 1** | Guardrails & circuit breakers | **OpenClaw (ben)** | `agent/guardrails.py` | `pytest tests/test_guardrails.py` |
| **Step 2** | Evaluator & TestVerdict schema | **Hermes** | `agent/evaluator.py` | `pytest tests/test_evaluator.py` |
| **Step 3** | ReAct orchestrator loop | **Hermes** | `agent/orchestrator.py` | `pytest tests/test_orchestrator.py` (mock planner + mock tools) |
| **Step 4** | Integration & demo | **Bersama** | `agent/orchestrator_demo.py` (atau `demo_orchestrator.py`) | `python -m agent.orchestrator_demo` + full `pytest tests/` hijau |

---

## 3. 📐 Technical Specification & File Contracts

### 3.1 `agent/guardrails.py` (OpenClaw / ben)

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

Action = Literal["continue", "abort", "retry"]

@dataclass
class GuardrailResult:
    tripped: bool
    reason: Optional[str] = None
    action: Action = "continue"

@dataclass
class GuardrailState:
    turn_count: int = 0
    history: list[tuple[str, dict]] = field(default_factory=list)  # (tool_name, args)
    estimated_tokens: int = 0
    start_time_ms: int = 0
```

Komponen:
1. **`TurnBudgetGuard(max_turns: int = 12)`** — tiap turn `turn_count += 1`; jika `> max_turns` → `GuardrailResult(tripped=True, reason="max turns exceeded", action="abort")`.
2. **`LoopDetector(consecutive_identical_threshold: int = 2)`** — jika tool+args identik berulang N kali berturut-turut → `tripped=True, action="abort", reason="repetitive tool loop detected"`. Opsional: deteksi siklus A→B→A.
3. **`TokenBudgetGuard(max_tokens: int = 8000)`** — akumulasi `estimated_tokens` per turn (diisi orchestrator dari perkiraan prompt+completion); jika over → `abort`.
4. **`ExecutionTimeoutGuard(max_ms: int = 120000)`** — wall-clock sejak start; jika over → `abort`.
5. **Facade `Guardrails`** — menggabungkan ke-4 guard; method `check(state) -> GuardrailResult` mengembalikan trip pertama yang terpicu (prioritas: timeout → turns → loop → tokens).

### 3.2 `agent/evaluator.py` (Hermes)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class LayerEvidence(BaseModel):
    ui: Optional[dict] = None      # ex: {"order_number": "ORD-...", "total": "..."}
    api: Optional[dict] = None     # ex: {"status_code": 200, "body": {...}}
    db: Optional[dict] = None      # ex: {"row_count": 1, "rows": [...]}

class TestVerdict(BaseModel):
    status: Literal["PASS", "FAIL", "BLOCKED"]
    reason: str
    evidence: LayerEvidence = Field(default_factory=LayerEvidence)
    trace: list[dict] = Field(default_factory=list)  # tiap turn: {turn, thought, tool, args, observation}
```

Fungsi: `evaluate(evidence, trace, guardrail_result) -> TestVerdict`
- **Zero-hallucination rule:** `PASS` hanya jika `ui.order_number == api.body.order_number == db.rows[0].order_number` (atau kriteria skenario). Jika ada layer missing/inkonsisten → `FAIL` dengan reason eksplisit.
- `BLOCKED` hanya jika `guardrail_result.tripped` sebelum verdict tercapai.

### 3.3 `agent/orchestrator.py` (Hermes)

```python
class Orchestrator:
    def __init__(self, registry: ToolRegistry, guardrails, planner, evaluator_fn, max_turns=12): ...
    def run(self, goal: str, context: dict | None = None) -> TestVerdict: ...
```

Loop per turn:
1. `guardrails.check(state)` → jika trip → return `TestVerdict(status="BLOCKED", ...)`.
2. `planner.next_step(goal, history) -> {thought, tool, args}` — **Phase 3 awal: scripted/mock planner** (daftar langkah tetap untuk skenario checkout), bukan LLM live. LLM planner menyusul setelah loop stabil.
3. `registry.dispatch(tool, args)` → observation (`ToolResult`).
4. Append ke `trace` + update `GuardrailState` (turn_count, history, tokens, time).
5. `evaluator_fn(evidence_terkini, trace, ...)` — jika sudah decisive (PASS/FAIL) → return; jika belum → lanjut turn berikutnya.

Evidence terkini dibangun dari observasi: hasil `browser_action` → `evidence.ui`, `api_client` → `evidence.api`, `db_query` → `evidence.db`.

### 3.4 `agent/orchestrator_demo.py` (Bersama)

Scripted scenario tanpa LLM:
1. `browser_action(open_store)` → `api_client(GET /api/health)` → `db_query(SELECT products)` → `browser_action(checkout flow)` → `db_query(SELECT orders WHERE order_number=...)` → verdict.
2. Cetak verdict JSON + trace ringkas.

---

## 4. 🧪 Test Plan

| File | Kasus |
| :--- | :--- |
| `tests/test_guardrails.py` (ben) | max turns trip di turn 13; loop detector trip pada 2x panggilan identik; timeout trip; tokens trip; gabungan facade memprioritaskan timeout |
| `tests/test_evaluator.py` (Hermes) | PASS saat 3 layer konsisten; FAIL saat order_number mismatch; FAIL saat db missing; BLOCKED saat guardrail tripped |
| `tests/test_orchestrator.py` (bersama) | run sukses dengan mock planner+registry → PASS; infinite planner → BLOCKED via max turns; planner ngeloop tool sama → BLOCKED via loop detector |

---

## 5. 🚀 Execution Order

1. **OpenClaw (ben):** buat `agent/guardrails.py` + `tests/test_guardrails.py` → hijau.
2. **Hermes:** buat `agent/evaluator.py` + `tests/test_evaluator.py` → hijau.
3. **Hermes:** buat `agent/orchestrator.py` + `tests/test_orchestrator.py` (mock planner) → hijau.
4. **Bersama:** buat demo + jalankan full suite `pytest tests/` → semua hijau → update Plane AQA-3 ke Done.

---

*Dokumen ini adalah kontrak eksekusi resmi Phase 3 — implementasi mengikuti spec di atas.*
