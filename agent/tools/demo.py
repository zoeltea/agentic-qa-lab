"""Phase 2 Standalone Demo: Executes all 4 tools sequentially without LLM."""
import json
import time
from agent.config import config
from agent.tools.db_tool import DbTool
from agent.tools.api_tool import ApiTool
from agent.tools.browser_tool import BrowserTool
from agent.tools.log_tool import LogTool
from agent.tools.registry import ToolRegistry


def run_demo():
    print("=" * 65)
    print("🚀 AGENTIC QA LAB — PHASE 2 TOOLING & MCP DEMO")
    print("=" * 65)
    print(f"Target Base URL : {config.base_url}")
    print(f"Target SQLite DB: {config.db_path}\n")

    # Inisialisasi Registry via Constructor DI
    registry = ToolRegistry(
        tools=[
            DbTool(),
            ApiTool(),
            BrowserTool(),
            LogTool(),
        ]
    )

    print("📋 Registered Tools in MCP Registry:")
    for t in registry.list_tools():
        print(f"  • [{t['name']}] — {t['description'][:70]}...")
    print("-" * 65)

    all_passed = True

    # 1. DbTool Demo
    print("\n[1/4] 📦 Testing DbTool (SELECT ground-truth products):")
    res_db = registry.dispatch("db_query", {"sql": "SELECT id, sku, name, price, stock FROM products ORDER BY id ASC"})
    print(f"  Status: {'✅ OK' if res_db.ok else '❌ FAILED'} (Latency: {res_db.latency_ms}ms)")
    if res_db.ok:
        print(f"  Rows count: {res_db.data['row_count']}")
        for r in res_db.data["rows"][:2]:
            print(f"    - {r['sku']}: {r['name']} (Rp {r['price']:,.0f}, Stock: {r['stock']})")
    else:
        print(f"  Error: {res_db.error}")
        all_passed = False

    # 2. ApiTool Demo
    print("\n[2/4] 🌐 Testing ApiTool (GET /api/health & POST /api/voucher/apply):")
    res_api = registry.dispatch("api_client", {"method": "GET", "path": "/api/health"})
    print(f"  Healthcheck: {'✅ OK' if res_api.ok else '❌ FAILED'} -> {res_api.data.get('body')}")
    
    res_voucher = registry.dispatch("api_client", {
        "method": "POST",
        "path": "/api/voucher/apply",
        "body": {"code": "DISKON10", "order_subtotal": 500000.0}
    })
    print(f"  Voucher apply: {'✅ OK' if res_voucher.ok else '❌ FAILED'} -> {res_voucher.data.get('body', {}).get('message')}")
    if not (res_api.ok and res_voucher.ok):
        all_passed = False

    # 3. LogTool Demo
    print("\n[3/4] 📋 Testing LogTool (Read fault_injection_config):")
    res_log = registry.dispatch("log_inspector", {"check_fault_config": True, "last_n_lines": 5})
    print(f"  Status: {'✅ OK' if res_log.ok else '❌ FAILED'}")
    if res_log.ok:
        print(f"  Fault Config: {res_log.data.get('fault_config')}")
    else:
        all_passed = False

    # 4. BrowserTool Demo (UI E2E flow)
    print("\n[4/4] 🎭 Testing BrowserTool (Semantic POM E2E Checkout Flow):")
    b_tool = registry.get("browser_action") or registry.get("browser")
    if b_tool:
        # Step 4a: Open Store
        res_open = b_tool.run(action="open_store")
        print(f"  4a. Open store : {'✅ OK' if res_open.ok else '❌ FAILED'}")

        # Step 4b: Add Mechanical Keyboard
        res_add = b_tool.run(action="add_to_cart", product_id=1)
        print(f"  4b. Add to cart: {'✅ OK' if res_add.ok else '❌ FAILED'}")

        # Step 4c: Apply Voucher
        res_vouch = b_tool.run(action="apply_voucher", code="DISKON10")
        print(f"  4c. Apply vouch: {'✅ OK' if res_vouch.ok else '❌ FAILED'} -> {res_vouch.data.get('message')}")

        # Step 4d: Submit Checkout
        res_checkout = b_tool.run(
            action="checkout",
            customer_name="Phase 2 Automated Runner",
            customer_email="runner.phase2@example.com",
            shipping_address="Jl. Standalone Runner No. 2",
            payment_method="qris",
        )
        print(f"  4d. Checkout   : {'✅ OK' if res_checkout.ok else '❌ FAILED'}")
        if res_checkout.ok:
            print(f"      🎉 Order Number: {res_checkout.data.get('order_number')} (Total: {res_checkout.data.get('total_amount')})")
        else:
            all_passed = False

        if hasattr(b_tool, "close"):
            b_tool.close()
    else:
        print("  ❌ BrowserTool not found in registry")
        all_passed = False

    print("\n" + "=" * 65)
    if all_passed:
        print("🏆 ALL 4 TOOLS & MCP REGISTRY VERIFIED SUCCESSFULLY! (Phase 2 DONE)")
    else:
        print("⚠️ SOME TOOL CHECKS FAILED. Please review above logs.")
    print("=" * 65)


if __name__ == "__main__":
    run_demo()
