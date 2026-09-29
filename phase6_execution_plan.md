# Phase 6 Execution Plan & Collaboration Contract
## CI/CD Pipeline, Portfolio README & Demo Artifacts — AQA-6 / add3367b

> **Project:** Agentic QA Lab & Portfolio (AutoQA-Agent)  
> **Target Workspace:** `/home/zoeltea/my_work/agentic-qa-lab`  
> **Collaborators:** Hermes Agent & OpenClaw (ben)  
> **Status:** Draft / Ready for Implementation  
> **Prerequisite:** Phase 5 Completed (Observability, Benchmarks & Metrics ready)

---

## 1. 🎯 Objective & Definition of Done

Menyempurnakan repository `agentic-qa-lab` menjadi **Portfolio SDET & AI Engineering Berstandar Enterprise** yang siap dipamerkan di GitHub dan dilengkapi automated CI pipeline:
1. **GitHub Actions CI/CD Pipeline (`.github/workflows/ci.yml`):**
   - Menjalankan linting, type checks, dan full pytest test suite (unit + integration + live e2e UI) pada setiap Push dan Pull Request ke `master`.
   - Setup headless Playwright browser environment di runner GitHub Actions.
   - Menjalankan benchmarking matrix suite secara otomatis dan mengekspor `benchmark_report.json` sebagai CI build artifact.
2. **Enterprise Architectural README (`README.md`):**
   - Dokumentasi arsitektur komprehensif 4 pilar (Tooling/MCP, Guardrails/Orchestration, Multi-Layer Verification, Observability/Benchmarks).
   - ASCII / Mermaid diagram alur ReAct loop dan cross-layer state reconciliation (UI vs API vs DB).
   - Panduan Quickstart, CLI commands, fault-injection simulation, dan tabel hasil benchmark (Token, Latency, False-Pass Rate = 0%).
3. **Demo Artifacts & Release Generator (`scripts/generate_artifacts.py`):**
   - Script otomatisasi untuk generate report markdown, diagram visual, dan snapshot eksekusi demo.

### Definition of Done (DoD):
1. File `.github/workflows/ci.yml` siap dan valid untuk GitHub Actions runner.
2. File `README.md` lengkap, profesional, berstandar industri dengan badge, arsitektur, dan benchmark results.
3. Seluruh test suite `pytest tests/ -v` lolos secara headless.
4. Script `scripts/generate_artifacts.py` berhasil dieksekusi tanpa error.
5. Plane.so issue `AQA-6` di-update ke status `Done` dan PR final di-merge ke `master`.

---

## 2. 👥 Division of Work (Hermes & OpenClaw)

```
[ Step 1: CI/CD Pipeline Workflow ] ──► [ Step 2: Architecture & README ] ──► [ Step 3: Demo Artifacts & Release ]
          (OpenClaw / ben)                            (Hermes)                               (Bersama)
                 │                                       │                                       │
      .github/workflows/ci.yml                       README.md                       scripts/generate_artifacts.py
      scripts/run_ci_checks.sh                                                        Release Verification
```

| Step | Scope Pekerjaan | Assignee | File Deliverables | Target Verifikasi |
| :--- | :--- | :---: | :--- | :--- |
| **Step 1** | **GitHub Actions CI Pipeline & CI Scripts** | **OpenClaw (ben)** | • `.github/workflows/ci.yml`<br>• `scripts/run_ci_checks.sh` | Workflow YAML syntax valid & script lokal lolos 100% |
| **Step 2** | **Enterprise README & Architecture Docs** | **Hermes** | • `README.md` | Dokumentasi lengkap dengan diagram, benchmark, dan API spec |
| **Step 3** | **Demo Artifacts & Final Release Check** | **Bersama** | • `scripts/generate_artifacts.py`<br>• `docs/architecture.png` / diagrams | Script generate report berjalan & full suite hijau |

---

## 3. 📐 Technical Specification & File Contracts

### 3.1 `.github/workflows/ci.yml` (OpenClaw / ben)

```yaml
name: Agentic QA Lab CI

on:
  push:
    branches: [ master, feat/* ]
  pull_request:
    branches: [ master ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          playwright install chromium --with-deps

      - name: Run Full Pytest Suite
        run: |
          pytest tests/ -v --cov=agent --cov=app --cov-report=term-missing

      - name: Run Multi-Layer Verification Demo
        run: |
          python -m agent.verifier_demo

      - name: Run Benchmarking Suite
        run: |
          python -m agent.benchmark_demo

      - name: Upload Benchmark & Coverage Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: qa-benchmark-artifacts
          path: |
            server.log
```

### 3.2 `README.md` (Hermes)

Struktur dokumen `README.md` yang harus dipenuhi:
1. **Header & Badges:** Python 3.11, Playwright, FastAPI, SQLite, MCP Protocol, CI Status, Zero-Hallucination Verified.
2. **Project Overview & Motivation:** Mengapa traditional E2E automation (Selenium/Cypress) rentan terhadap *silent backend failure* dan bagaimana Agentic SDET merekonsiliasi 3 layer (DOM + REST + DB).
3. **Core Architectural Pillars:**
   - *Pillar 1: Multi-Tool & MCP Integration* (`DbTool`, `ApiTool`, `BrowserTool`, `LogTool`).
   - *Pillar 2: ReAct Orchestrator & Strict Guardrails* (`TurnBudget`, `LoopDetector`, `TokenBudget`, `ExecutionTimeout`).
   - *Pillar 3: Multi-Layer Verification Engine* (`Verifier` & Fault-Injection Detectors).
   - *Pillar 4: Observability & Benchmarking Suite* (Latency profiler, Token cost meter, False-Pass Rate = 0%).
4. **Architecture Diagram (Mermaid / ASCII).**
5. **Quickstart & Local Setup:**
   - Clone, venv setup, `playwright install`.
   - Menjalankan testbed app (`python -m app.server` di port 8091).
   - Menjalankan full automated test suite (`pytest tests/ -v`).
   - Menjalankan standalone demos (`orchestrator_demo`, `verifier_demo`, `benchmark_demo`).
6. **Benchmark Results Table:**
   - Matriks perbandingan 4 skenario (Normal, Silent DB Fail, Corrupted Stock, Slow DB).
   - Metrik akurasi: FPR = 0.0%, Anomaly Recall = 100.0%.
7. **License & Author Info:** Zul Yatman (@zulyatman).

### 3.3 `scripts/generate_artifacts.py` (Bersama)

Script Python mandiri untuk mengeksekusi semua demo, mengumpulkan log dan metrik, serta menulis ringkasan `DEMO_REPORT.md` secara otomatis.

---

## 4. 🧪 Test Plan & Acceptance Criteria

1. **Syntax & Workflow Linting:** Validasi syntax file YAML `.github/workflows/ci.yml`.
2. **Headless Execution Verification:** Verifikasi seluruh test suite dan demo script dapat berjalan mulus tanpa visual browser display (headless mode).
3. **Artifact Generation:** Memastikan `scripts/generate_artifacts.py` menghasilkan laporan yang valid dan komprehensif.

---

## 5. 🚀 Execution Order

1. Simpan dokumen `phase6_execution_plan.md` ke git repository.
2. Selesaikan **Phase 5** terlebih dahulu (Metrics, Benchmarking, Demo, PR & Merge).
3. Masuk ke **Phase 6**:
   - OpenClaw: Buat `.github/workflows/ci.yml` & `scripts/run_ci_checks.sh`.
   - Hermes: Tulis `README.md` berstandar portfolio enterprise.
   - Bersama: Buat `scripts/generate_artifacts.py` & verifikasi final.
4. Buat PR final Phase 6 dan merge ke `master`.

---

*Dokumen ini adalah kontrak eksekusi resmi Phase 6 — implementasi mengikuti spec di atas.*
