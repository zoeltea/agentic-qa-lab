# ROADMAP & ARCHITECTURE SPECIFICATION
## Project: Agentic QA Lab & Portfolio (AutoQA-Agent)
**Owner / Lead Engineer:** Zul Yatman (@zulyatman)  
**Coordinated by:** ben (OpenClaw) & Hermes Agent  
**Workspace:** `/home/zoeltea/my_work/agentic-qa-lab`  
**Hermes Kanban Board:** `agentic-qa-lab`

---

## 🎯 Project Objective
Membangun framework **Agentic QA Testing & SDET Orchestration** end-to-end berstandar industri dengan 4 pilar utama:
1. **Multi-Tool & MCP Integration** (Browser/Playwright, REST API, Database Query, Log Inspector).
2. **Deterministic Orchestration & Prompt Guardrails** (ReAct / Plan-and-Execute loop, Pydantic/Zod schema assertion, circuit breakers).
3. **Multi-Layer Cross-Verification** (State verification: UI Banner + HTTP Response + DB Records).
4. **Observability, Benchmarking & CI/CD Pipeline** (Token/Cost tracking, False-Pass rate metrics, GitHub Actions CI).

---

## 🏗️ Architecture & Component Layers

```
+--------------------------------------------------------------------------+
|                        Agentic QA Orchestrator Engine                    |
|  - ReAct / Plan-and-Execute Loop                                         |
|  - Strict Structured Schema Validation (Pydantic / Zod)                  |
|  - Circuit Breakers (Max Turns, Timeout, Anti-Hallucination Guardrails)  |
+--------------------------------------------------------------------------+
                                    |
           +------------------------+------------------------+
           |                                                 |
+----------------------+                         +----------------------+
|     Tooling & MCP    |                         |    Observability &   |
|       Connectors     |                         |      Benchmarking    |
+----------------------+                         +----------------------+
| 1. Browser (Playwright)|                        | - Token & Cost Meter |
| 2. DB Connector (SQL)|                         | - Latency Profiler   |
| 3. API & Net Monitor |                         | - False-Pass Asserter|
| 4. Log File Reader   |                         | - Flakiness Analyzer |
+----------------------+                         +----------------------+
           |
+--------------------------------------------------------------------------+
|                  Target App under Test (E-Commerce Testbed)              |
|  - Frontend Web UI (Checkout, Discount Voucher, Cart)                   |
|  - Backend REST API (Inventory, Order Processing)                        |
|  - Database (SQLite / Postgres Order & Stock State)                      |
+--------------------------------------------------------------------------+
```

---

## 📋 Phased Execution Plan & Hermes Kanban Mapping

| Task ID (Hermes) | Phase / Milestones | Description & Deliverables | Status |
| :--- | :--- | :--- | :--- |
| `t_6d0434aa` | **Phase 1: Workspace & Testbed Setup** | Menyiapkan repository, target web application under test (e-commerce flow: cart -> voucher -> checkout -> order creation), database schema, dan seeded test data. | 🟡 Ready |
| `t_6fee897b` | **Phase 2: Tooling & MCP Integration** | Implementasi tool connectors: 1) Playwright browser driver, 2) Direct DB assertion client, 3) REST API client, 4) Log reader. | 🟡 Ready |
| `t_4ecb4d5a` | **Phase 3: Core Orchestrator & Guardrails** | Implementasi core agent loop: ReAct reasoning, tool dispatching, schema enforcement, boundary rules, dan circuit breaker (max turns, retry logic). | 🟡 Ready |
| `t_f6505b8b` | **Phase 4: Multi-Layer Verification** | Membangun skenario cross-layer assertion (verifikasi UI + payload HTTP + integritas data DB) dan fault injection test cases. | 🟡 Ready |
| `t_1670e0af` | **Phase 5: Observability & Benchmark Suite** | Setup metrics instrumentation: token usage meter, execution cost tracker, latency logging, dan false-pass rate benchmarking runner. | 🟡 Ready |
| `t_6a3f56eb` | **Phase 6: CI/CD Pipeline & Portfolio Artifacts** | Konfigurasi GitHub Actions workflow, README arsitektural komprehensif, demo recorder, dan packaging release. | 🟡 Ready |

---

## 🛠️ Verification & Acceptance Criteria
- **Zero Hallucination Tolerance:** Agent tidak boleh menyatakan test PASS jika query DB gagal atau tidak match dengan UI.
- **Circuit Breaker:** Agent otomatis berhenti dan memicu alarm jika melebihi batas turn atau terdeteksi tool-calling looping.
- **CI Testability:** Seluruh test suite dan verification engine dapat dijalankan secara headless di GitHub Actions.
