# 🤖 AutoQA-Agent: Autonomous Agentic QA & Multi-Layer Verification Framework

[![CI Pipeline](https://github.com/zoeltea/agentic-qa-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/zoeltea/agentic-qa-lab/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-1.50+-2EAD33.svg?logo=playwright&logoColor=white)](https://playwright.dev)
[![MCP Protocol](https://img.shields.io/badge/MCP-Standard%20Tooling-blueviolet.svg)](https://modelcontextprotocol.io)
[![Zero Hallucination](https://img.shields.io/badge/False--Pass%20Rate-0.0%25-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, multi-tool **Agentic QA System** engineered by Senior SDET to overcome the vulnerabilities of traditional UI automation (e.g., silent backend drops, state desynchronization, and false-pass hallucinations) by orchestrating **ReAct reasoning loops**, **Model Context Protocol (MCP)** tools, and **Cross-Layer Ground-Truth Reconciliation (UI ↔ API ↔ DB)**.

---

## 📑 Table of Contents
- [The Problem: Why Traditional E2E QA Fails](#-the-problem-why-traditional-e2e-qa-fails)
- [Architecture & 4 Core Pillars](#-architecture--4-core-pillars)
- [Multi-Layer Reconciliation Flow](#-multi-layer-reconciliation-flow)
- [Fault-Injection Resilience Matrix](#-fault-injection-resilience-matrix)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Running Demos & Benchmarks](#-running-demos--benchmarks)
- [Quality & Performance Metrics](#-quality--performance-metrics)
- [Author](#-author)

---

## 💥 The Problem: Why Traditional E2E QA Fails

In conventional E2E testing (Selenium, Cypress, standard Playwright):
1. **Silent Backend Failures:** The frontend UI renders a success modal with an order ID, but the backend dropped the database transaction or wrote partial records. Traditional tests assert DOM visibility and yield a **False-Pass**.
2. **State Desynchronization:** Cart state displays 5 items left, while the SQLite database holds 10 (or 0) due to race conditions.
3. **Flaky & Opaque Retries:** When tests fail, traditional runners blindly retry without inspecting database locks or system logs.

**AutoQA-Agent** solves this by mandating **Zero-Hallucination Multi-Layer Verification**: a test only receives a `PASS` verdict if DOM, API response payload, and Database records are cryptographically/semantically reconciled.

---

## 🏛️ Architecture & 4 Core Pillars

```
                     ┌────────────────────────────────────────────────────────┐
                     │              🤖 ReAct Orchestration Loop                │
                     │          (Thought ➔ Plan ➔ Act ➔ Observe)              │
                     └──────────────────────────┬─────────────────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
  ┌───────────────────────────────┐                             ┌───────────────────────────────┐
  │   🛡️ Pillar 1: Guardrails     │                             │   🧰 Pillar 2: MCP Toolset    │
  │  • TurnBudgetGuard (max 12)   │                             │  • BrowserTool (DOM / Page)   │
  │  • LoopDetector (Cycle/Ping)  │                             │  • ApiTool (REST Client)      │
  │  • TokenBudgetGuard (60k cap) │                             │  • DbTool (Read-Only SQL)     │
  │  • ExecutionTimeoutGuard (60s)│                             │  • LogTool (Fault/Log Reader) │
  └───────────────────────────────┘                             └───────────────┬───────────────┘
                                                                                │
                                ┌───────────────────────────────────────────────┘
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │         🔍 Pillar 3: Multi-Layer Verification Engine        │
  │  • UI Evidence      ➔ [order_number, total, cart_badge]     │
  │  • API Evidence     ➔ [status: 200, payload: order_number]  │
  │  • DB Ground Truth  ➔ [SELECT * FROM orders / order_items]  │
  │  ═════════════════════════════════════════════════════════  │
  │  Verdict: PASS | FAIL | BLOCKED | ANOMALY_DETECTED          │
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │         📊 Pillar 4: Observability & Benchmarking Suite     │
  │  • Token & USD Cost Meter ($/turn)                          │
  │  • Latency Decomposition (UI vs API vs DB profiler)         │
  │  • False-Pass Rate (FPR = 0.0%) & Recall Asserter (100.0%)  │
  └─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Multi-Layer Reconciliation Flow

```
[Agent Action] ──► 1. UI Checkout Click ──► Captures Modal Order Number (e.g. ORD-1001)
               ──► 2. API Intercept     ──► Captures HTTP 200 Payload (ORD-1001)
               ──► 3. DB Direct Query   ──► Executes SELECT WHERE order_number = 'ORD-1001'
               ──► 4. Cross-Reconcile   ──► If UI == API == DB ➔ Verdict: PASS
                                        ──► If UI != DB        ➔ Verdict: ANOMALY_DETECTED
```

---

## 🧪 Fault-Injection Resilience Matrix

AutoQA-Agent includes an embedded Chaos/Fault-Injection testbed engine with 3 fault scenarios:

| Fault Scenario | Simulated Condition | Traditional Test Result | AutoQA-Agent Result |
| :--- | :--- | :---: | :---: |
| **Silent DB Failure** | API returns `200 OK`, UI renders modal, but DB insert is dropped | 🟢 **False PASS** (Dangerous) | 🚨 `ANOMALY_DETECTED` (Intercepted) |
| **Corrupted Stock** | UI display shows stock=3, but DB holds stock=8 (tampered state) | 🟢 **False PASS** | 🚨 `ANOMALY_DETECTED` (Intercepted) |
| **Slow DB Query** | Database query latency exceeds timeout threshold (>5000ms) | 🔴 Unhandled Timeout Error | 🚨 `ANOMALY_DETECTED` (Logged & Profiled) |

---

## 📁 Project Structure

```
agentic-qa-lab/
├── agent/
│   ├── benchmark.py            # Phase 5: Benchmark Matrix Runner & Quality Reporter
│   ├── benchmark_demo.py       # Phase 5: Standalone Benchmark Suite CLI
│   ├── evaluator.py            # Phase 3: Zero-Hallucination Cross-Layer Evaluator
│   ├── guardrails.py           # Phase 3: Circuit Breakers (Turn, Loop, Token, Timeout)
│   ├── metrics.py              # Phase 5: Token Cost Tracker & Latency Profiler
│   ├── orchestrator.py         # Phase 3: Core ReAct Autonomous Loop
│   ├── orchestrator_demo.py    # Phase 3: End-to-End ReAct Checkout Demo
│   ├── verifier.py             # Phase 4: Multi-Layer Verification & Fault Injection Engine
│   ├── verifier_demo.py        # Phase 4: 4-Scenario Fault Detection Demo
│   ├── verifier_guardrails.py  # Phase 4: Verifier Guardrails (Maturity, Completeness)
│   └── tools/
│       ├── api_tool.py         # MCP REST API Tool
│       ├── base.py             # BaseTool contract & MCP Schema Exporter
│       ├── browser_tool.py     # Playwright DOM Tool & Page Object Model
│       ├── db_tool.py          # Read-Only SQLite Tool with Parameterization
│       ├── log_tool.py         # Testbed Log & Fault Config Inspector
│       ├── registry.py         # Tool Registry & Dispatcher
│       └── pages/              # Clean Page Object Model (CatalogPage, CheckoutPage)
├── app/
│   ├── database.py             # SQLite Schema & Seed Data (Products, Vouchers, Orders)
│   ├── schemas.py              # Pydantic Schemas & Fault Injection Config
│   ├── server.py               # FastAPI Testbed Server (Port 8091)
│   └── static/                 # Modern Tailwind CSS / Vanilla JS Frontend
├── tests/                      # 67 Automated Unit, Integration & E2E Tests
├── scripts/
│   ├── generate_artifacts.py   # CI/CD Demo Report Generator
│   └── run_ci_checks.sh        # Local CI Automation Script
├── .github/workflows/ci.yml    # Automated GitHub Actions CI/CD Pipeline
└── pyproject.toml              # Project Config & Dependencies
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Installation
```bash
git clone https://github.com/zoeltea/agentic-qa-lab.git
cd agentic-qa-lab

# Create & activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies & Playwright browser
pip install -r requirements.txt
playwright install chromium
```

### 3. Start Testbed Application
```bash
python -m app.server
# Server running at: http://127.0.0.1:8091
```

---

## 🎮 Running Demos & Benchmarks

```bash
# 1. Run full automated test suite (67 tests)
pytest tests/ -v

# 2. Run ReAct Autonomous Orchestrator Demo (Phase 3)
python -m agent.orchestrator_demo

# 3. Run Multi-Layer Fault Injection Demo (Phase 4)
python -m agent.verifier_demo

# 4. Run Observability & Benchmarking Matrix (Phase 5)
python -m agent.benchmark_demo

# 5. Run Local CI Pipeline Validation (Phase 6)
./scripts/run_ci_checks.sh
```

---

## 📈 Quality & Performance Metrics

Benchmarked on 4-scenario matrix (1 Normal + 3 Fault Injections):

```markdown
| Scenario | Fault Injected | Verdict | Tokens | Cost ($) | Latency (s) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Scenario 1: Normal E2E Checkout Flow | No | ✅ `PASS` | 1,570 | $0.00111 | 0.185s |
| Scenario 2: Silent DB Failure | Yes (silent_db_failure) | ✅ `ANOMALY_DETECTED` | 1,380 | $0.00097 | 0.155s |
| Scenario 3: Corrupted Stock | Yes (corrupted_stock) | ✅ `ANOMALY_DETECTED` | 1,220 | $0.00085 | 0.140s |
| Scenario 4: Slow DB Latency | Yes (slow_db_ms) | ✅ `ANOMALY_DETECTED` | 1,310 | $0.00092 | 0.240s |
```

- **False-Pass Rate (FPR):** `0.0%` (Zero-Hallucination)
- **Anomaly Detection Recall:** `100.0%`
- **Average Turn Latency:** `< 0.20s`
- **Mean Cost per Test:** `~$0.00095 USD`

---

## 👨💻 Author

**Zul Yatman**  
*Senior SDET & AI-Augmented QA Engineer (10+ Years Experience)*  
- GitHub: [@zoeltea](https://github.com/zoeltea)  
- Email: `zoeltea@gmail.com`  
- Specialization: Test Automation Frameworks (Playwright, Appium, Robot Framework), AI Agent Orchestration, Model Context Protocol (MCP), and Multi-Layer System Verification.

---
*Built with ❤️ in Agentic QA Lab.*
