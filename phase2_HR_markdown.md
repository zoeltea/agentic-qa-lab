# Phase 2 — Multi-Tool & MCP Integration — Architecture Design

> Project: Agentic QA Lab & Portfolio (AutoQA-Agent)
> Phase: 2 / 6 — Implement Multi-Tool & MCP Integration
> Owner: Zul Yatman | Co-pilot: Hermes + OpenClaw
> Workspace: `/home/zoeltea/my_work/agentic-qa-lab`
> Status: Design — Ready to Build

---

## 1. Tujuan Phase 2

Menyediakan **lapisan Tooling yang deterministik, testable, dan MCP-compatible** agar Orchestrator (Phase 3) tidak pernah memanggil Playwright / SQL / HTTP secara langsung, melainkan hanya memanggil 4 Tool dengan JSON schema ketat.

```
LLM / Orchestrator ──(JSON)──► ToolRegistry ──► BrowserTool / ApiTool / DbTool / LogTool
                                                        │
                                                        ▼
                                              POM (Page Object Model) — khusus BrowserTool
```

**Kenapa ini penting untuk SDET:** memisahkan *intent* LLM ("checkout dengan voucher DISKON10") dari *implementasi* selector/SQL. Kalau UI berubah, hanya 1 file POM yang diubah, prompt LLM tetap.

---

## 2. Prinsip Arsitektur

| Prinsip | Keputusan | Alasan |
|---|---|---|
| **Dependency Injection (DI)** | `Orchestrator(tools=[...])` di-inject via constructor, bukan `import` hardcode | Di test inject `FakeTool`, di prod inject real tool. Memudahkan Phase 4–5 mocking & benchmarking |
| **Tool Abstraction** | Semua tool inherit `BaseTool` → return `ToolResult` (tidak pernah raise ke LLM) | Guardrail anti-hallucination untuk Phase 3 |
| **POM untuk Browser** | LLM tidak tahu selector `#btn-add-1`. LLM panggil `add_product_to_cart(product_id=1)`, POM yang tahu selector | Anti-flaky, single source of truth untuk locator |
| **MCP-Ready tanpa over-engineering** | Setiap tool sudah punya `name / description / input_schema` yang kompatibel dengan MCP `FastMCP` | Phase 2 fokus internal dulu, tinggal bungkus `mcp.server` tanpa refactor di akhir phase |
| **Allowlist & Read-Only** | DbTool hanya `SELECT` ke 5 tabel, ApiTool hanya 3 endpoint, LogTool hanya baca fault config | Keamanan & determinisme |

---

## 3. Struktur Folder (Greenfield — `agent/tools/` saat ini kosong)

```
agent/
├── __init__.py
├── config.py                 # base_url, db_path, timeout dari env (AQA_DB_PATH, AQA_BASE_URL)
└── tools/
    ├── base.py               # BaseTool, ToolResult, ToolRegistry
    ├── browser_tool.py       # Wrap Playwright + POM
    ├── pages/
    │   ├── __init__.py
    │   ├── catalog_page.py   # POM: #product-grid, #product-card-1, #btn-add-1, #cart-badge
    │   └── checkout_page.py  # POM: #voucher-input, #btn-apply-voucher, #voucher-feedback,
    │                         #      #input-customer-name/email, #btn-checkout, #order-success-modal
    ├── api_tool.py           # httpx client → /api/products, /api/voucher/apply, /api/checkout
    ├── db_tool.py            # sqlite read-only + allowlist
    ├── log_tool.py           # baca fault_injection_config + log server
    └── demo.py               # python -m agent.tools.demo — smoke test tanpa LLM
```

---

## 4. Kontrak Base — Semua Tool Wajib Implement

```python
# agent/tools/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ToolResult(BaseModel):
    ok: bool
    data: dict = {}
    error: str | None = None
    latency_ms: int = 0

class BaseTool(ABC):
    name: str                          # ex: "db_query"
    description: str                   # dibaca LLM saat tool selection
    input_schema: type[BaseModel]      # JSON schema untuk function calling / MCP

    @abstractmethod
    def run(self, **kwargs) -> ToolResult: ...

class ToolRegistry:
    def __init__(self, tools: list[BaseTool]): ...
    def list_tools(self) -> list[dict]: ...   # → untuk prompt / MCP manifest
    def get(self, name: str) -> BaseTool: ...
    def dispatch(self, name: str, args: dict) -> ToolResult: ...
```

**Kontrak keras:**
- Tidak pernah `raise` exception ke caller LLM — selalu return `ToolResult(ok=False, error=...)`.
- Semua output `data` adalah JSON-serializable (untuk observability Phase 5).

---

## 5. Detail 4 Tool

### 5.1 DbTool — Fondasi Verifikasi (Build Pertama)

- **Reuse:** `app/database.py:get_db_connection()` — tidak duplikasi koneksi.
- **Input:** `{ sql: str, params: list }`
- **Guardrail:**
  - Hanya `SELECT` (regex `^\s*SELECT\b` case-insensitive).
  - Tabel harus ada di allowlist: `products, vouchers, orders, order_items, fault_injection_config`.
  - `INSERT / UPDATE / DELETE / DROP / ALTER` → `ok=False` langsung.
- **Output:** `{ ok, rows: list[dict], row_count, latency_ms }`
- **Contoh pakai (Phase 4):** verifikasi `SELECT * FROM orders WHERE order_number='ORD-xxx'` harus match dengan modal UI.

### 5.2 ApiTool — Verifikasi Payload Backend

- **Client:** `httpx` ke `http://127.0.0.1:8091` (diambil dari `config.base_url`).
- **Allowlist endpoint:**

  | Method | Path | Schema Validasi |
  |---|---|---|
  | GET | `/api/products` | `list[ProductSchema]` |
  | POST | `/api/voucher/apply` | `VoucherApplyResponse` |
  | POST | `/api/checkout` | `CheckoutResponse` |
  | GET | `/api/health` | `{status: ok}` |

- **Input:** `{ method, path, body?: dict }`
- **Output:** `{ ok, status_code, body: dict, latency_ms }`
- **Validasi:** response body divalidasi dengan `app/schemas.py`. Jika mismatch → `ok=False, error="schema mismatch"` (bukan hallucinate).

### 5.3 BrowserTool + POM — Lapisan Anti-Flaky

**LLM tidak tahu selector.** LLM hanya panggil aksi semantik:

```python
# Yang LLM lihat
browser_tool.run(action="add_product_to_cart", product_id=1)
browser_tool.run(action="apply_voucher", code="DISKON10")
browser_tool.run(action="checkout", customer_name="Zul", customer_email="zul@example.com")
browser_tool.run(action="get_order_number")
```

**Di dalam BrowserTool → delegasi ke POM:**

```python
# agent/tools/pages/catalog_page.py
class CatalogPage:
    URL = "/"
    GRID = "#product-grid"
    CARD = "#product-card-{id}"
    BTN_ADD = "#btn-add-{id}"
    BADGE = "#cart-badge"

    def add_to_cart(self, page, product_id: int): ...
    def get_cart_badge(self, page) -> int: ...

# agent/tools/pages/checkout_page.py
class CheckoutPage:
    VOUCHER_INPUT = "#voucher-input"
    BTN_APPLY = "#btn-apply-voucher"
    FEEDBACK = "#voucher-feedback"
    INPUT_NAME = "#input-customer-name"
    INPUT_EMAIL = "#input-customer-email"
    BTN_CHECKOUT = "#btn-checkout"
    MODAL = "#order-success-modal"
    ORDER_NUMBER = "#modal-order-number"
    ORDER_TOTAL = "#modal-order-total"
```

- **Lifecycle:** `launch(headless=True)` sekali saat `BrowserTool.__init__`, `close()` di teardown. Timeout 10s per aksi.
- **Keuntungan POM:** jika `#btn-add-1` berubah jadi `#add-to-cart-1`, hanya `catalog_page.py` yang diubah. 30 test + prompt LLM tidak tersentuh.

### 5.4 LogTool — Detektor Fault Injection

- **Input:** `{ last_n_lines: int = 50, include_fault_config: bool = True }`
- **Sumber:**
  1. `SELECT * FROM fault_injection_config WHERE id=1` — flag `simulate_silent_db_failure`, `simulate_slow_db_ms`, `simulate_corrupted_stock`.
  2. File log uvicorn (jika ada) — `tail -n {last_n_lines}`.
- **Output:** `{ ok, fault_config: dict, logs: list[str] }`
- **Peran di Phase 4:** mendeteksi skenario "API return 200 tapi DB tidak tertulis" (silent failure).

---

## 6. Aliran Dependency Injection

```python
# Prod
from agent.tools.db_tool import DbTool
from agent.tools.api_tool import ApiTool
from agent.tools.browser_tool import BrowserTool
from agent.tools.log_tool import LogTool
from agent.tools.base import ToolRegistry

registry = ToolRegistry(tools=[
    DbTool(db_path=config.db_path),
    ApiTool(base_url=config.base_url),
    BrowserTool(base_url=config.base_url),
    LogTool(db_path=config.db_path),
])

# Test — inject fake tanpa ubah Orchestrator
registry_test = ToolRegistry(tools=[FakeDbTool(), FakeApiTool()])
orchestrator = Orchestrator(tools=registry_test)
```

---

## 7. Strategi MCP (Model Context Protocol)

**Phase 2 tidak langsung deploy MCP server eksternal.** Alasan: POM lokal lebih cepat & deterministik untuk testbed.

Dua langkah:

1. **Internal (Phase 2):** semua tool sudah punya `name / description / input_schema` → kompatibel dengan spec MCP `tools/list` & `tools/call`.
2. **Akhir Phase 2 (opsional):** bungkus dengan `mcp.server.FastMCP` — tanpa refactor:

   ```python
   # agent/mcp_server.py (akhir Phase 2)
   from mcp.server import FastMCP
   mcp = FastMCP("agentic-qa-lab")
   for tool in registry.list_tools():
       mcp.add_tool(tool)
   ```

Belum perlu Playwright MCP server eksternal — itu Phase 6 jika mau showcase portfolio.

---

## 8. Dependensi Baru

Tambahan ke `requirements.txt`:

```
playwright>=1.44.0
httpx>=0.27.0
mcp>=1.2.0          # opsional, akhir Phase 2
```

Tanpa `langchain / crewai / autogen` — agar loop ReAct Phase 3 terlihat eksplisit.

---

## 9. Urutan Build & Acceptance Criteria

| Step | Deliverable | Test |
|---|---|---|
| 1 | `base.py` + `db_tool.py` | `pytest tests/test_tools_db.py` — query `ORD-xxx` match, reject `DROP TABLE` |
| 2 | `api_tool.py` | `pytest tests/test_tools_api.py` — checkout via tool == via raw httpx |
| 3 | `pages/*.py` + `browser_tool.py` | `pytest tests/test_tools_browser.py` — full checkout via tool 100% pass (bukan via raw playwright) |
| 4 | `log_tool.py` + `registry` | `pytest tests/test_tools_registry.py` — `registry.list_tools()` return 4 tool, semua punya JSON schema |
| 5 | `demo.py` | `python -m agent.tools.demo` — jalankan semua tool tanpa LLM, semua return `ToolResult` |

**Definition of Done Phase 2:**
- [ ] 4 tool implement `BaseTool`, return `ToolResult`, tidak pernah raise.
- [ ] POM memisahkan selector dari logic — 1 perubahan selector tidak menyentuh prompt.
- [ ] `ToolRegistry` bisa `dispatch(name, args)` dengan DI.
- [ ] Semua tool punya `input_schema` JSON yang valid untuk MCP.
- [ ] `python -m agent.tools.demo` + `pytest tests/test_tools_*.py` hijau.

---

## 10. Diagram Alir Lengkap

```
                           ┌─────────────────────┐
                           │   Orchestrator      │
                           │   (Phase 3)         │
                           │  ReAct Loop         │
                           └─────────┬───────────┘
                                     │ dispatch(name, args)
                                     ▼
                           ┌─────────────────────┐
                           │   ToolRegistry      │
                           │  list_tools()       │
                           │  dispatch()         │
                           └────┬───┬───┬───┬───┘
                                │   │   │   │
              ┌─────────────────┘   │   │   └──────────────────┐
              ▼                     ▼   ▼                      ▼
     ┌──────────────┐   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │  BrowserTool │   │   ApiTool    │  │   DbTool     │  │   LogTool    │
     │  + POM       │   │  httpx       │  │  sqlite R/O  │  │  fault cfg   │
     └──────┬───────┘   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
            │                  │                 │                 │
            ▼                  ▼                 ▼                 ▼
     ┌──────────────┐   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │ CatalogPage  │   │ /api/*       │  │  SQLite DB   │  │ fault_inj.   │
     │ CheckoutPage │   │ schemas.py   │  │  allowlist   │  │  + log file  │
     └──────────────┘   └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 11. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Selector UI berubah | POM: ubah 1 file, bukan 30 test |
| LLM hallucinate SQL | DbTool allowlist + regex SELECT-only |
| Playwright flaky di CI | Timeout 10s + `wait_for_selector` eksplisit + headless |
| MCP over-engineering | Tunda `mcp.server` sampai semua tool stabil |

---

*Dokumen ini adalah spec Phase 2 — implementasi menyusul setelah approval.*
