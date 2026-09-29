# Phase 4 Execution Plan & Collaboration Contract
## Multi-Layer Verification (UI + API + DB Reconciliation) — AQA-4 / 67882052

> **Project:** Agentic QA Lab & Portfolio (AutoQA-Agent)
> **Target Workspace:** `/home/zoeltea/my_work/agentic-qa-lab`
> **Collaborators:** Hermes Agent & OpenClaw (ben)
> **Status:** Approved for Implementation
> **Prerequisite:** Phase 3 DONE (51 test passed, orchestrator demo PASS verdict, cross-layer reconciliation verified)

---

## 1. 🎯 Objective & Definition of Done

Membangun **Multi-Layer Verification Engine** yang memverifikasi konsistensi state aplikasi di 3 layer sekaligus:
- **UI Layer:** DOM state yang ditangkap oleh BrowserTool (order modal, voucher feedback, cart badge)
- **API Layer:** HTTP response payload dari REST API (status code, body, headers)
- **DB Layer:** SQLite ground truth (orders, order_items, products, vouchers, fault_injection_config)

Selain itu, mengimplementasikan **Fault Injection scenarios** untuk menguji kemampuan agent mendeteksi anomaly (silent DB failure, slow DB response, corrupted stock).

### Definition of Done (DoD):
1. `agent/verifier.py` mengimplementasikan `Verifier` class dengan method: `verify_cross_layer(ui_evidence, api_evidence, db_evidence) -> Verdict`.
2. 3 Fault Injection scenarios aktif dan terverifikasi:
   - `simulate_silent_db_failure` → API return 200 tapi DB tidak tertulis → verifier DETECT & FAIL.
   - `simulate_slow_db_ms` → response time > threshold → verifier DETECT latency anomaly.
   - `simulate_corrupted_stock` → DB stock tidak match UI cart → verifier DETECT stock corruption.
3. `agent/verifier_guardrails.py` menyediakan guardrails khusus verifier (consistency maturity, data integrity, duplication detection).
4. Seluruh unit test `tests/test_verifier.py` & `tests/test_crosslayer_assertion.py` lulus 100%.
5. Demo `python -m agent.verifier_demo` menjalankan 3 fault injection scenarios & cross-layer assertion → menghasilkan verdict JSON.

---

## 2. 👥 Division of Work (Hermes & OpenClaw)

```
[ Fault Injection Engine ] ──► [ Cross-Layer Verifier ] ──► [ Assertion Scenarios ]
         (Hermes)                          (Hermes)                       (OpenClaw / ben)
                                              │
[ Integration Demo ] ◄───┴─── (Bersama)
```

| Step | Scope | Assignee | Deliverables / Files | Test Verification |
| :--- | :--- | :---: | :--- | :--- |
| **Step 1** | Fault Injection Engine & Verifier Core | **Hermes** | `agent/verifier.py` | `pytest tests/test_verifier.py` |
| **Step 2** | Cross-Layer Assertion Scenarios | **OpenClaw (ben)** | `agent/verifier_guardrails.py` | `pytest tests/test_crosslayer_assertion.py` |
| **Step 3** | Integration Demo & Full Test Suite | **Bersama** | `agent/verifier_demo.py` | `python -m agent.verifier_demo` + full `pytest tests/` hijau |

---

## 3. 📐 Technical Specification & File Contracts

### 3.1 `agent/verifier.py` (Hermes)

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class LayerEvidence(BaseModel):
    """Evidence captured dari masing-masing layer selama eksekusi ReAct loop."""
    ui: Optional[Dict[str, Any]] = None      # ex: {"order_number": "ORD-...", "total_amount_display": "...", "voucher_code": "..."}
    api: Optional[Dict[str, Any]] = None     # ex: {"status_code": 200, "body": {"order_number": "...", "status": "PAID"}}
    db: Optional[Dict[str, Any]] = None      # ex: {"rows": [{"order_number": "...", "status": "PAID", "total_amount": 700000}], "row_count": 1}
    logs: Optional[Dict[str, Any]] = None    # ex: {"fault_config": {...}, "error_count": 0}


class FaultInjectionConfig(BaseModel):
    """Keadaan fault injection saat ini — diambil dari DB via /api/admin/fault-injection."""
    simulate_silent_db_failure: bool = False
    simulate_slow_db_ms: int = 0
    simulate_corrupted_stock: bool = False


class Verdict(BaseModel):
    """Structured verdict untuk multi-layer verification."""
    status: str = Field(..., pattern="^(PASS|FAIL|BLOCKED|ANOMALY_DETECTED)$")
    reason: str
    evidence: LayerEvidence = Field(default_factory=LayerEvidence)
    fault_config: Optional[FaultInjectionConfig] = None
    trace: List[Dict[str, Any]] = Field(default_factory=list)


class Verifier:
    """Multi-layer cross-checker engine with fault injection awareness."""

    def __init__(self, fault_config: Optional[FaultInjectionConfig] = None):
        self.fault_config = fault_config or FaultInjectionConfig()

    def verify_cross_layer(
        self,
        ui: Optional[Dict[str, Any]],
        api: Optional[Dict[str, Any]],
        db: Optional[Dict[str, Any]],
        logs: Optional[Dict[str, Any]] = None,
        scenario_constraints: Optional[Dict[str, Any]] = None,
    ) -> Verdict:
        """
        Cross-layer verification logic:
        1. Jika fault injection silent_db_failure aktif & UI order_number ada tapi DB missing → ANOMALY_DETECTED (silent failure).
        2. Jika fault injection slow_db_ms aktif & latency > threshold → ANOMALY_DETECTED (latency anomaly).
        3. Jika fault injection corrupted_stock aktif & DB stock != UI cart stock → ANOMALY_DETECTED (stock corruption).
        4. Jika UI/API/DB order_number konsisten → PASS.
        5. Jika ada layer missing → FAIL.
        6. Jika order_number mismatch → FAIL.
        """
        pass  # Implementasi lengkap di file
```

**Metode tambahan:**
- `_detect_silent_failure(ui, db) -> Optional[str]` → return reason jika UI claim success tapi DB order missing.
- `_detect_latency_anomaly(logs, threshold_ms=5000) -> Optional[str]` → return reason jika fault slow_db_ms aktif & latency melebihi threshold.
- `_detect_stock_corruption(ui_stock, db_stock) -> Optional[str]` → return reason jika DB stock tidak match UI cart stock.

### 3.2 `agent/verifier_guardrails.py` (OpenClaw / ben)

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class GuardrailResult:
    tripped: bool
    reason: Optional[str] = None
    action: str = "continue"  # continue | abort | retry


class VerifierGuardrails:
    """Guardrails khusus untuk verifier — memastikan verifikasi konsisten & aman."""

    def __init__(
        self,
        max_cross_layer_checks: int = 5,
        min_evidence_layers: int = 2,
        duplication_threshold: int = 3,
    ):
        self.max_cross_layer_checks = max_cross_layer_checks
        self.min_evidence_layers = min_evidence_layers
        self.duplication_threshold = duplication_threshold
        self._check_history: list[str] = []

    def check_evidence_completeness(self, evidence_layers: int) -> GuardrailResult:
        """Minimal berapa layer harus ada sebelum verdict bisa diambil."""
        pass

    def check_duplication(self, check_description: str) -> GuardrailResult:
        """Mencegah verifier melakukan check yang sama berulang kali tanpa progress."""
        pass

    def check_maturity(self, verdict: str, checks_done: int) -> GuardrailResult:
        """Memastikan verifier tidak terlalu cepat verdict PASS sebelum semua layer terverifikasi."""
        pass
```

**Implementasi yang diharapkan:**
1. `check_evidence_completeness`: Jika `evidence_layers < min_evidence_layers` → `GuardrailResult(tripped=True, reason="insufficient evidence layers", action="abort")`.
2. `check_duplication`: Jika `check_description` muncul `>= duplication_threshold` kali di `_check_history` → `tripped=True, action="abort"`.
3. `check_maturity`: Jika `verdict == "PASS"` tapi `checks_done < 3` → `tripped=True, action="retry"`.

---

## 4. 🧪 Rencana Verifikasi & Acceptance Testing

### 4.1 `tests/test_verifier.py` (Hermes)
Kasus uji:
1. `test_silent_failure_detected`: Aktifkan `simulate_silent_db_failure=1`, checkout via UI → API return 200 → DB tidak ada order → verifier DETECT → `ANOMALY_DETECTED`.
2. `test_latency_anomaly_detected`: Aktifkan `simulate_slow_db_ms=10000`, query DB → verifier DETECT latency > 5000ms → `ANOMALY_DETECTED`.
3. `test_stock_corruption_detected`: Aktifkan `simulate_corrupted_stock=1`, UI cart show stock=5 → DB stock=10 → verifier DETECT → `ANOMALY_DETECTED`.
4. `test_pass_when_all_layers_consistent`: Normal checkout tanpa fault → verifier PASS.
5. `test_fail_when_layer_missing`: DB evidence None → verifier FAIL.
6. `test_fail_when_order_mismatch`: UI order "ORD-AAA" vs DB order "ORD-BBB" → verifier FAIL.

### 4.2 `tests/test_crosslayer_assertion.py` (OpenClaw / ben)
Kasus uji:
1. `test_guardrail_evidence_completeness`: 1 layer evidence → GuardrailResult tripped (insufficient).
2. `test_guardrail_duplication`: check_description "verify_order_number" dipanggil 3x → GuardrailResult tripped.
3. `test_guardrail_maturity`: verdict="PASS" dengan checks_done=1 → GuardrailResult tripped (retry).
4. `test_guardrail_all_clear`: 3 layers evidence, checks_done=3, no duplication → GuardrailResult not tripped.

---

## 4. 🚀 Execution Order & Demo

1. **Hermes:** buat `agent/verifier.py` + `tests/test_verifier.py` → hijau.
2. **OpenClaw:** buat `agent/verifier_guardrails.py` + `tests/test_crosslayer_assertion.py` → hijau.
3. **Bersama:** buat `agent/verifier_demo.py` yang:
   - Menjalankan 3 fault injection scenarios (silent failure, slow DB, corrupted stock).
   - Menjalankan normal checkout scenario (cross-layer assertion).
   - Cetak verdict JSON + trace ringkas.
4. Jalankan full suite `pytest tests/` → semua hijau → update Plane AQA-4 ke Done.

---

## 5. 📂 Struktur File Final Phase 4

```
agent/
├── verifier.py              # Hermes: Core verifier + FaultInjectionConfig + Verifier class
├── verifier_guardrails.py   # OpenClaw: VerifierGuardrails class + GuardrailResult
├── __init__.py
└── tools/                   # (sudah ada dari Phase 2)
tests/
├── test_verifier.py         # Hermes: Fault injection scenarios + cross-layer verdict tests
├── test_crosslayer_assertion.py # OpenClaw: Guardrail tests
└── test_verifier_demo.py    # Bersama: Demo integration test (opsional)
```

---

*Dokumen ini adalah kontrak eksekusi resmi Phase 4 — implementasi mengikuti spec di atas.*
