# Phase 2 Execution Plan & Collaboration Contract
## Multi-Tool & MCP Integration (AQA-2 / t_6fee897b)

> **Project:** Agentic QA Lab & Portfolio (AutoQA-Agent)  
> **Target Workspace:** `/home/zoeltea/my_work/agentic-qa-lab`  
> **Collaborators:** Hermes Agent & OpenClaw (ben)  
> **Status:** Approved for Implementation  

---

## 1. 🎯 Objective & Definition of Done

Membangun lapisan tooling yang **deterministik, modular (Constructor DI), resilient (Semantic POM), aman (Read-Only Guardrails), dan MCP-compatible** sehingga Orchestrator (Phase 3) hanya berinteraksi melalui interface `BaseTool` dengan standar output `ToolResult`.

### Definition of Done (DoD):
1. Ke-4 Tool (`DbTool`, `ApiTool`, `BrowserTool`, `LogTool`) mewarisi `BaseTool` dan mengimplementasikan metode `run(**kwargs) -> ToolResult`.
2. **Zero-Exception Contract:** Tidak ada tool yang me-raise unhandled exception ke LLM caller; semua kegagalan wajib ditangkap dan dikembalikan sebagai `ToolResult(ok=False, error="...")`.
3. **Semantic POM:** Selector UI terisolasi di `agent/tools/pages/` sehingga perubahan selector tidak merusak prompt LLM.
4. **Read-Only SQLite Guardrail:** `DbTool` hanya mengizinkan query `SELECT` pada 5 tabel allowlist (`products`, `vouchers`, `orders`, `order_items`, `fault_injection_config`).
5. **Constructor Dependency Injection:** `ToolRegistry(tools=[...])` memungkinkan swap mock `FakeTool` untuk pengujian.
6. Seluruh unit test di `tests/test_tools_*.py` lulus 100% dan demo mandiri `python -m agent.tools.demo` berjalan sukses tanpa LLM.

---

## 2. 👥 Division of Work (Hermes & OpenClaw)

```
[ Step 1: Base Contract ] ──► [ Step 2: Data & Backend Tools ] ──► [ Step 3: Semantic POM & Browser ]
       (Hermes)                        (Hermes)                             (OpenClaw / ben)
                                                                                    │
[ Step 5: Standalone Demo & Acceptance ] ◄── [ Step 4: Registry Integration & Test Suite ]
             (Bersama)                                             (Bersama)
```

| Step | Scope | Assignee | Deliverables / Files | Test Verification |
| :--- | :--- | :---: | :--- | :--- |
| **Step 1** | Config & Base Contract | **Hermes** | `agent/config.py`<br>`agent/tools/base.py` | `pytest tests/test_tools_base.py` |
| **Step 2** | Data & Backend Tools | **Hermes** | `agent/tools/db_tool.py`<br>`agent/tools/api_tool.py`<br>`agent/tools/log_tool.py` | `pytest tests/test_tools_db.py`<br>`pytest tests/test_tools_api.py`<br>`pytest tests/test_tools_log.py` |
| **Step 3** | Semantic POM & Browser Tool | **OpenClaw (ben)** | `agent/tools/pages/catalog_page.py`<br>`agent/tools/pages/checkout_page.py`<br>`agent/tools/browser_tool.py` | `pytest tests/test_tools_browser.py` |
| **Step 4** | Tool Registry & MCP Export | **Bersama** | `agent/tools/registry.py` | `pytest tests/test_tools_registry.py` |
| **Step 5** | Standalone Smoke Demo | **Bersama** | `agent/tools/demo.py` | `python -m agent.tools.demo` |

---

## 3. 📐 Technical Specification & File Contracts

### 3.1 `agent/config.py` (Hermes)
Mengelola konfigurasi lingkungan dari env variable:
```python
import os
from dataclasses import dataclass

@dataclass
class AgentConfig:
    base_url: str = os.getenv("AQA_BASE_URL", "http://127.0.0.1:8091")
    db_path: str = os.getenv("AQA_DB_PATH", "/home/zoeltea/my_work/agentic-qa-lab/app/testbed.sqlite3")
    log_file_path: str = os.getenv("AQA_LOG_PATH", "/home/zoeltea/my_work/agentic-qa-lab/server.log")
    browser_headless: bool = os.getenv("AQA_BROWSER_HEADLESS", "true").lower() == "true"
    browser_timeout_ms: int = int(os.getenv("AQA_BROWSER_TIMEOUT_MS", "10000"))

config = AgentConfig()
```

---

### 3.2 `agent/tools/base.py` (Hermes)
Kontrak dasar seluruh tool dan response schema:
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    ok: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: int = 0

class BaseTool(ABC):
    name: str
    description: str
    input_schema: Type[BaseModel]

    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """Execute the tool logic and return standardized ToolResult without raising unhandled exceptions."""
        pass

    def to_mcp_tool(self) -> dict:
        """Export tool definition for Model Context Protocol (MCP) compatibility."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema.model_json_schema()
        }
```

---

### 3.3 `agent/tools/db_tool.py` (Hermes)
- **Input Schema:** `DbToolInput(sql: str, params: list = [])`
- **Guardrails:**
  1. Regex: Wajib dimulai dengan `^\s*SELECT\b` (case-insensitive).
  2. Reject mutasi: Blokir kata kunci `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`.
  3. Table Allowlist: `products`, `vouchers`, `orders`, `order_items`, `fault_injection_config`.
- **Output:** `ToolResult(ok=True, data={"rows": [...], "row_count": n})`

---

### 3.4 `agent/tools/api_tool.py` (Hermes)
- **Input Schema:** `ApiToolInput(method: str, path: str, body: Optional[dict] = None)`
- **Allowlist Endpoint:**
  - `GET /api/health`
  - `GET /api/products` & `GET /api/products/{id}`
  - `POST /api/voucher/apply`
  - `POST /api/checkout`
  - `GET /api/orders/{order_number}`
- **Output:** `ToolResult(ok=True, data={"status_code": 200, "body": {...}})`

---

### 3.5 `agent/tools/log_tool.py` (Hermes)
- **Input Schema:** `LogToolInput(last_n_lines: int = 50, check_fault_config: bool = True)`
- **Fungsi:**
  1. Membaca baris terakhir dari `server.log` (jika ada).
  2. Membaca status `fault_injection_config` dari database (deteksi silent failure / artificial delay).
- **Output:** `ToolResult(ok=True, data={"fault_config": {...}, "logs": [...]})`

---

### 3.6 `agent/tools/pages/` & `agent/tools/browser_tool.py` (OpenClaw / ben)

#### A. `agent/tools/pages/catalog_page.py`
- Selector constants:
  - `GRID = "#product-grid"`
  - `CARD = "#product-card-{id}"`
  - `BTN_ADD = "#btn-add-{id}"`
  - `STOCK = "#stock-{id}"`
  - `BADGE = "#cart-badge"`
- Actions: `add_product_to_cart(page, product_id: int)`, `get_cart_badge_count(page) -> int`.

#### B. `agent/tools/pages/checkout_page.py`
- Selector constants:
  - `VOUCHER_INPUT = "#voucher-input"`
  - `BTN_APPLY = "#btn-apply-voucher"`
  - `FEEDBACK = "#voucher-feedback"`
  - `INPUT_NAME = "#input-customer-name"`
  - `INPUT_EMAIL = "#input-customer-email"`
  - `INPUT_ADDRESS = "#input-customer-address"`
  - `SELECT_PAYMENT = "#select-payment-method"`
  - `BTN_CHECKOUT = "#btn-checkout"`
  - `MODAL = "#order-success-modal"`
  - `ORDER_NUMBER = "#modal-order-number"`
  - `ORDER_TOTAL = "#modal-order-total"`
- Actions: `apply_voucher(page, code: str)`, `submit_checkout(page, customer_data: dict)`, `get_order_confirmation(page) -> dict`.

#### C. `agent/tools/browser_tool.py`
- **Input Schema:** `BrowserToolInput(action: str, params: dict = {})`
- **Action Dispatcher:**
  - `action="open_store"`
  - `action="add_to_cart"`, params: `{"product_id": 1}`
  - `action="apply_voucher"`, params: `{"code": "DISKON10"}`
  - `action="checkout"`, params: `{"name": "...", "email": "...", "address": "...", "payment_method": "qris"}`
  - `action="get_order_result"`
- Lifecycle: `Playwright.chromium.launch(headless=True)` di-reuse dan ditutup dengan `close()`.

---

### 3.7 `agent/tools/registry.py` (Bersama)
```python
from typing import List, Dict, Optional
from agent.tools.base import BaseTool, ToolResult

class ToolRegistry:
    def __init__(self, tools: List[BaseTool]):
        self._tools: Dict[str, BaseTool] = {tool.name: tool for tool in tools}

    def list_tools(self) -> List[dict]:
        return [tool.to_mcp_tool() for tool in self._tools.values()]

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def dispatch(self, name: str, args: dict) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(ok=False, error=f"Tool '{name}' not found in registry.")
        try:
            return tool.run(**args)
        except Exception as e:
            return ToolResult(ok=False, error=f"Unhandled tool error in '{name}': {str(e)}")
```

---

### 3.8 `agent/tools/demo.py` (Bersama)
CLI standalone smoke test:
```bash
python -m agent.tools.demo
```
Akan mengeksekusi secara berurutan:
1. `DbTool` ➔ Query data produk dari DB.
2. `ApiTool` ➔ Healthcheck & fetch products via REST API.
3. `BrowserTool` ➔ Buka browser, add item ke cart, pasang voucher, checkout E2E, ambil `ORD-XXXX`.
4. `LogTool` ➔ Cek fault injection status.
5. Verifikasi semua tool menghasilkan status `ok=True`.

---

## 4. 🚀 Next Execution Instructions for Hermes

File ini (`/home/zoeltea/my_work/agentic-qa-lab/phase2_execution_plan.md`) adalah **panduan eksekusi resmi**.

**Hermes** dapat langsung memulai pengerjaan **Step 1 & Step 2**:
1. Buat `agent/config.py` dan `agent/tools/base.py`.
2. Buat `agent/tools/db_tool.py`, `agent/tools/api_tool.py`, `agent/tools/log_tool.py`.
3. Buat dan jalankan test suite unit `tests/test_tools_db.py`, `tests/test_tools_api.py`, `tests/test_tools_log.py`.
4. Setelah Step 1 & 2 selesai dan hijau, **OpenClaw (ben)** akan melanjutkan **Step 3** (`pages/` POM & `browser_tool.py`).
