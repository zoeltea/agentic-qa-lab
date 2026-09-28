"""
Playwright E2E UI Test for AQA Testbed Application.
Simulates end-to-end browser user interactions: Catalog -> Add to Cart -> Voucher -> Checkout -> Modal Verification.
"""
import pytest
import os
import subprocess
import time
from playwright.sync_api import sync_playwright

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_e2e_testbed.sqlite3")

@pytest.fixture(scope="module")
def live_server():
    os.environ["AQA_DB_PATH"] = TEST_DB_PATH
    
    # Initialize DB
    from app.database import init_db
    init_db(reset=True)

    # Start uvicorn server on port 8091
    proc = subprocess.Popen(
        [
            "/home/zoeltea/my_work/agentic-qa-lab/.venv/bin/uvicorn",
            "app.server:app",
            "--host", "127.0.0.1",
            "--port", "8091"
        ],
        cwd="/home/zoeltea/my_work/agentic-qa-lab",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ, AQA_DB_PATH=TEST_DB_PATH)
    )
    
    # Wait for server ready by polling
    import urllib.request
    ready = False
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8091/api/health", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.2)
            
    if not ready:
        stdout, stderr = proc.communicate(timeout=2)
        raise RuntimeError(f"Server failed to start on 8091: stdout={stdout}, stderr={stderr}")
    
    yield "http://127.0.0.1:8091"
    
    # Teardown
    proc.terminate()
    proc.wait()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

def test_full_browser_checkout_flow(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 1. Navigate to Web UI
        page.goto(live_server)
        page.wait_for_selector("#product-grid")
        
        # Verify products rendered
        assert page.locator("#product-card-1").is_visible()
        
        # 2. Add Mechanical Keyboard to Cart
        page.click("#btn-add-1")
        
        # Verify Cart badge updated
        assert page.locator("#cart-badge").inner_text() == "1"
        assert "Mechanical Keyboard" in page.locator("#cart-items-container").inner_text()
        
        # 3. Apply Voucher 'DISKON10'
        page.fill("#voucher-input", "DISKON10")
        page.click("#btn-apply-voucher")
        
        # Verify Voucher success feedback
        page.wait_for_selector("#voucher-feedback:not(.hidden)")
        feedback_text = page.locator("#voucher-feedback").inner_text()
        assert "berhasil dipasang" in feedback_text
        
        # 4. Fill Checkout Form & Submit
        page.fill("#input-customer-name", "Zul SDET Automation")
        page.fill("#input-customer-email", "zul.automation@example.com")
        page.click("#btn-checkout")
        
        # 5. Assert Success Modal Appears
        page.wait_for_selector("#order-success-modal:not(.hidden)")
        order_num = page.locator("#modal-order-number").inner_text()
        assert order_num.startswith("ORD-")
        
        # Verify UI total
        modal_total = page.locator("#modal-order-total").inner_text()
        assert "Rp" in modal_total
        
        browser.close()
