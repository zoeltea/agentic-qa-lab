# Phase 2: Multi-Tool & MCP Integration Design Document
## Operational Architecture, Dependency Injection, Semantic POM, and Tool Registry

**Project:** Agentic QA Lab & Portfolio (AutoQA-Agent)  
**Issue Reference:** Plane `AQA-2` | Hermes `t_6fee897b`  
**Location:** `/home/zoeltea/my_work/agentic-qa-lab/`  
**Status:** Planning / Specification  

---

## 1. 🏛️ Architectural Overview & Design Principles

Tujuan dari Phase 2 adalah membangun antarmuka tool (*Tooling & Connectors*) yang menghubungkan **AI Agent Reasoning Loop (Phase 3)** dengan **Target Application under Test (Phase 1)** secara deterministik, bebas *flakiness*, aman (*safe execution*), dan mendukung standar protokol modern (**MCP / Model Context Protocol**).

```
+-------------------------------------------------------------------------------+
|                             AI Agent Orchestrator                             |
+-------------------------------------------------------------------------------+
                                        │ (Calls via JSON Schema)
+-------------------------------------------------------------------------------+
|                         Tool Registry & MCP Gateway                           |
|  - Tool Discovery & Pydantic Schema Serialization (OpenAI / MCP format)       |
|  - Dynamic Tool Invocation & Argument Parsing / Error Interception            |
+-------------------------------------------------------------------------------+
                                        │ (Dependency Injection)
+-------------------------------------------------------------------------------+
|                          Abstract Tool Interface (Base)                       |
|  - BaseTool (name, description, args_schema, execute(), to_mcp_definition())  |
+-------------------------------------------------------------------------------+
        │                       │                       │                       │
+---------------+       +---------------+       +---------------+       +---------------+
| Browser Tool  |       | DB Assertion  |       |  API Client   |       | Log Inspector |
| (Playwright + |       |     Tool      |       |     Tool      |       |     Tool      |
|  Semantic POM)|       | (SQLite Read) |       | (HTTPX/Sniff) |       | (Uvicorn Log) |
+---------------+       +---------------+       +---------------+       +---------------+
```

### Pilar Utama Desain:
1. **Separation of Concerns (SoC):** Logic interaksi DOM, logic query database, dan logic HTTP request terisolasi dalam modul masing-masing.
2. **Read-Only Database Enforcement:** Database tool hanya mengizinkan query `SELECT` untuk mencegah mutasi state tidak disengaja oleh LLM.
3. **Resilient DOM Selectors:** Menggunakan atribut data semantik (`[data-sku]`, `#id`, ARIA roles) melalui Page Object Model (POM).
4. **Structured Error Handling:** Setiap eksekusi tool mengembalikan `ToolResult(success, data, error, execution_time_ms)` terstandarisasi.

---

## 2. 💉 Dependency Injection (DI) & Runtime Context

Untuk menghindari *hardcoding* environment URL, database connection string, atau browser session, kita menerapkan **Inversion of Control (IoC)** via `ToolContext`.

### 2.1 `ToolContext` Container Specification

```python
from dataclasses import dataclass
from typing import Optional
import httpx
import sqlite3
from playwright.sync_api import Page, Browser, Playwright

@dataclass
class ToolContext:
    """
    Dependency Injection Container passed to every tool execution.
    Manages resource lifecycles (DB connections, HTTP clients, Browser instances).
    """
    base_url: str = "http://127.0.0.1:8091"
    db_path: str = "/home/zoeltea/my_work/agentic-qa-lab/app/testbed.sqlite3"
    log_file_path: str = "/home/zoeltea/my_work/agentic-qa-lab/server.log"
    
    # Injected runtime sessions
    http_client: Optional[httpx.Client] = None
    playwright_instance: Optional[Playwright] = None
    browser_instance: Optional[Browser] = None
    browser_page: Optional[Page] = None

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_http_client(self) -> httpx.Client:
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.Client(base_url=self.base_url, timeout=10.0)
        return self.http_client

    def cleanup(self):
        """Gracefully release all allocated I/O and process resources."""
        if self.http_client and not self.http_client.is_closed:
            self.http_client.close()
        if self.browser_page:
            self.browser_page.close()
        if self.browser_instance:
            self.browser_instance.close()
        if self.playwright_instance:
            self.playwright_instance.stop()
```

### 2.2 Manfaat Pola DI:
* **Unit Testing Isolation:** Test suite dapat menginjeksi mock database (`test_temp.sqlite3`) atau base URL lokal tanpa memodifikasi kode tool.
* **Session Reuse:** Mengurangi latency Playwright startup (browser dibuka sekali per scenario run, bukan per single tool call).

---

## 3. 🎭 Semantic Page Object Model (POM) untuk AI Agent

LLM rentan mengalami halusinasi atau kegagalan jika diberikan raw HTML DOM yang kompleks. Pola **Semantic POM** memetakan interaksi web UI menjadi aksi tingkat tinggi (*high-level semantic intent*).

```
[ LLM Agent ] 
     │ (Memanggil Semantic Action: `ui_add_product`, `ui_apply_voucher`, `ui_checkout`)
     ▼
[ Browser Tool Interface (`agent/tools/browser_tool.py`) ]
     │ (Menginjeksi Page Instance & Memanggil Page Object Method)
     ▼
[ Page Objects: CatalogPage, CheckoutPage (`agent/pages/`) ]
     │ (Mengenkapsulasi Selector tangguh: [data-sku], #id, modal triggers)
     ▼
[ Playwright Engine (Headless Chromium) ]
```

### 3.1 Spesifikasi Komponen POM

#### A. `BasePage` (`agent/pages/base_page.py`)
- `navigate(path: str)`: Membuka endpoint URL target dan menunggu `domcontentloaded`.
- `take_screenshot(name: str) -> str`: Menyimpan screenshot visual ke folder `reports/screenshots/`.
- `get_visible_text(selector: str) -> str`: Mengambil text bersih dari elemen visible.

#### B. `CatalogPage` (`agent/pages/catalog_page.py`)
- `get_rendered_products() -> List[Dict]`: Ekstraksi seluruh item yang tampil di UI (SKU, nama, harga, stok).
- `add_to_cart(sku: str) -> bool`: Mengklik tombol `+ Keranjang` pada card yang memiliki atribut `data-sku="<SKU>"`.
- `get_cart_badge_count() -> int`: Membaca jumlah item pada badge header keranjang.

#### C. `CheckoutPage` (`agent/pages/checkout_page.py`)
- `apply_voucher(code: str) -> Dict[str, Any]`: Mengetik kode voucher, mengklik `Gunakan`, dan mengembalikan status validitas serta pesan feedback.
- `fill_checkout_form(name: str, email: str, address: str, payment_method: str)`: Mengisi seluruh form customer.
- `click_pay_and_wait_modal() -> Dict[str, Any]`: Mengklik tombol bayar dan mengekstrak nomor order `ORD-XXXX`, total bayar, dan status dari modal popup sukses.

---

## 4. 🛠️ Rincian 4 Tool Utama & Contract Schema

Setiap tool mewarisi abstract class `BaseTool` dengan signature Pydantic:

### 4.1 Tool 1: Browser Controller (`BrowserTool`)
* **Purpose:** Menjalankan interaksi UI end-to-end melalui Playwright Semantic POM.
* **Methods:**
  - `open_store()`: Buka katalog toko.
  - `add_item_to_cart(sku: str, quantity: int = 1)`
  - `apply_voucher_code(code: str)`
  - `submit_checkout(name: str, email: str, address: str, payment_method: str)`
  - `capture_evidence(label: str)`

### 4.2 Tool 2: Database State Asserter (`DbAssertionTool`)
* **Purpose:** Memverifikasi integritas data (*Ground Truth*) langsung di SQLite.
* **Safety Rules:**
  - Strict read-only query (hanya statement yang diawali dengan `SELECT`).
  - Mencegah SQL injection dan mutation (`DROP`, `DELETE`, `UPDATE`, `INSERT`).
* **Methods:**
  - `query_product_by_sku(sku: str)`: Mengambil snapshot data produk & stok terkini.
  - `query_order_by_number(order_number: str)`: Mengambil relasi `orders` dan item `order_items`.
  - `query_voucher_usage(code: str)`: Mengambil data `quota` dan `used_count`.

### 4.3 Tool 3: REST API Client & Inspector (`ApiClientTool`)
* **Purpose:** Menjalankan HTTP request langsung ke backend dan menginspeksi status code, latency, dan payload.
* **Methods:**
  - `get_health()`
  - `get_products()`
  - `validate_voucher(code: str, order_subtotal: float)`
  - `post_checkout(payload: dict)`
  - `get_order_details(order_number: str)`

### 4.4 Tool 4: Log Inspector Tool (`LogInspectorTool`)
* **Purpose:** Membaca log file server (`server.log`) untuk mendeteksi runtime crash, traceback, atau warning.
* **Methods:**
  - `read_recent_logs(max_lines: int = 50)`
  - `search_error_patterns(pattern: str = "ERROR|Exception|Traceback")`

---

## 5. 🔌 Standarisasi Tool Registry & MCP Protocol Gateway

Semua tool didaftarkan ke dalam `ToolRegistry` yang memiliki 2 adapter serializer:
1. **OpenAI / Claude Tool Calling Format** (digunakan untuk Phase 3 Orchestrator loop).
2. **MCP (Model Context Protocol) Server Format** (digunakan untuk integrasi eksternal Claude Desktop / Cursor / Hermes via MCP JSON-RPC).

### 5.1 Format MCP Tools Export Contoh:
```json
{
  "name": "db_query_order",
  "description": "Query order record and items directly from SQLite database by order number",
  "inputSchema": {
    "type": "object",
    "properties": {
      "order_number": {
        "type": "string",
        "description": "Order number string starting with ORD-"
      }
    },
    "required": ["order_number"]
  }
}
```

---

## 6. 📂 Struktur File Phase 2

```
agent/
├── __init__.py
├── context.py              # Dependency Injection Container (ToolContext)
├── pages/                  # Semantic Page Object Model (POM)
│   ├── __init__.py
│   ├── base_page.py        # Base Page helper (Playwright)
│   ├── catalog_page.py     # Product Catalog POM
│   └── checkout_page.py    # Cart & Checkout Modal POM
├── tools/                  # Concrete Tools Implementations
│   ├── __init__.py
│   ├── base.py             # BaseTool abstract class & ToolResult schema
│   ├── browser_tool.py     # Browser UI Testing Tool
│   ├── db_tool.py          # SQLite Read-Only Assertion Tool
│   ├── api_tool.py         # REST API Client & Network Inspector Tool
│   ├── log_tool.py         # Server Log Reader Tool
│   └── registry.py         # Central Tool Registry & Dispatcher
└── mcp/                    # Model Context Protocol (MCP) Server
    ├── __init__.py
    └── server.py           # FastMCP / JSON-RPC Server runner
```

---

## 7. 🧪 Rencana Verifikasi & Acceptance Testing

Sebelum Phase 2 dinyatakan selesai (*Done*), seluruh rangkaian pengujian berikut wajib lulus (`tests/test_agent_tools.py`):
1. **`test_db_tool_read_only_safety`**: Memastikan query `SELECT` berhasil, dan query destruktif (`DELETE/DROP`) ditolak.
2. **`test_api_tool_endpoints`**: Memastikan request ke endpoint target berjalan lancar dengan response parsing yang valid.
3. **`test_pom_browser_interactions`**: Memastikan Playwright POM dapat melakukan *Add to cart*, *Apply voucher*, dan *Checkout* tanpa error selector.
4. **`test_log_inspector_reads`**: Memastikan tool dapat membaca log server dan mendeteksi keyword error.
5. **`test_tool_registry_mcp_export`**: Memastikan seluruh tool berhasil di-export ke format JSON schema MCP standar.
