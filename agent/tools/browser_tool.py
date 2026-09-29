"""Browser Tool with Semantic POM integration for Agentic QA Lab."""
import time
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright, Playwright, Browser, Page

from agent.config import config
from agent.tools.base import BaseTool, ToolResult
from agent.tools.pages.catalog_page import CatalogPage
from agent.tools.pages.checkout_page import CheckoutPage


class BrowserToolInput(BaseModel):
    """Input arguments for BrowserTool actions."""
    action: str = Field(
        ...,
        description="Semantic browser action: 'open_store', 'get_products', 'add_to_cart', 'apply_voucher', 'checkout', 'get_cart_count', 'close'"
    )
    product_id: Optional[int] = Field(None, description="Product ID to add or inspect (e.g. 1)")
    code: Optional[str] = Field(None, description="Voucher code to apply (e.g. 'DISKON10')")
    customer_name: Optional[str] = Field(None, description="Customer full name for checkout")
    customer_email: Optional[str] = Field(None, description="Customer email for checkout")
    shipping_address: Optional[str] = Field(None, description="Customer shipping address for checkout")
    payment_method: Optional[str] = Field("qris", description="Payment method: 'qris', 'bank_transfer', 'credit_card', 'cod'")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional raw params dictionary")


class BrowserTool(BaseTool):
    """Controls headless Chromium browser and executes UI actions via Semantic Page Object Models (POM)."""

    name: str = "browser_action"
    description: str = (
        "Interact with the web UI via semantic actions: 'open_store', 'get_products', "
        "'add_to_cart', 'apply_voucher', 'checkout', 'get_cart_count', 'close'."
    )
    input_schema: Type[BaseModel] = BrowserToolInput

    def __init__(self, base_url: Optional[str] = None, headless: Optional[bool] = None):
        self.base_url = (base_url or config.base_url).rstrip("/")
        self.headless = config.browser_headless if headless is None else headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    def _ensure_browser(self) -> Page:
        """Lazy-initialize and return active browser page."""
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        if self._browser is None:
            self._browser = self._playwright.chromium.launch(headless=self.headless)
        if self._page is None or self._page.is_closed():
            self._page = self._browser.new_page()
            self._page.set_default_timeout(config.browser_timeout_ms)
        return self._page

    def close(self):
        """Clean up and close browser instance."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        finally:
            self._page = None
            self._browser = None
            self._playwright = None

    def run(self, **kwargs) -> ToolResult:
        """Execute browser semantic action and return ToolResult."""
        start_time = time.perf_counter()
        try:
            # Parse inputs
            action = kwargs.get("action", "").strip().lower()
            params = kwargs.get("params") or {}
            
            # Helper to retrieve arg from kwargs or nested params
            def get_arg(key: str, default=None):
                return kwargs.get(key) if kwargs.get(key) is not None else params.get(key, default)

            page = self._ensure_browser()

            if action == "open_store":
                CatalogPage.navigate(page, self.base_url)
                products = CatalogPage.get_rendered_products(page)
                elapsed = int((time.perf_counter() - start_time) * 1000)
                return self._success({
                    "url": self.base_url + "/",
                    "rendered_products_count": len(products),
                    "products": products
                }, latency=elapsed)

            elif action == "get_products":
                products = CatalogPage.get_rendered_products(page)
                elapsed = int((time.perf_counter() - start_time) * 1000)
                return self._success({"products": products}, latency=elapsed)

            elif action == "add_to_cart":
                prod_id = get_arg("product_id")
                if prod_id is None:
                    elapsed = int((time.perf_counter() - start_time) * 1000)
                    return self._error("Missing required parameter 'product_id'", latency=elapsed)

                success = CatalogPage.add_product_to_cart(page, int(prod_id))
                badge_count = CatalogPage.get_cart_badge_count(page)
                elapsed = int((time.perf_counter() - start_time) * 1000)
                if success:
                    return self._success({
                        "product_id": int(prod_id),
                        "cart_badge_count": badge_count,
                        "added": True
                    }, latency=elapsed)
                else:
                    return self._error(f"Failed to add product {prod_id} (out of stock or disabled)", latency=elapsed)

            elif action == "get_cart_count":
                badge_count = CatalogPage.get_cart_badge_count(page)
                elapsed = int((time.perf_counter() - start_time) * 1000)
                return self._success({"cart_badge_count": badge_count}, latency=elapsed)

            elif action == "apply_voucher":
                code = get_arg("code")
                if not code:
                    elapsed = int((time.perf_counter() - start_time) * 1000)
                    return self._error("Missing required parameter 'code'", latency=elapsed)

                result = CheckoutPage.apply_voucher(page, str(code))
                elapsed = int((time.perf_counter() - start_time) * 1000)
                return self._success(result, latency=elapsed)

            elif action == "checkout":
                name = get_arg("customer_name", "Budi Santoso")
                email = get_arg("customer_email", "budi.s@example.com")
                address = get_arg("shipping_address", "Jl. Sudirman No. 45, Jakarta")
                payment = get_arg("payment_method", "qris")

                CheckoutPage.fill_customer_info(
                    page,
                    name=name,
                    email=email,
                    address=address,
                    payment_method=payment
                )
                checkout_res = CheckoutPage.submit_checkout(page)
                elapsed = int((time.perf_counter() - start_time) * 1000)

                if checkout_res.get("success"):
                    return self._success(checkout_res, latency=elapsed)
                else:
                    return self._error(checkout_res.get("error", "Checkout failed"), latency=elapsed)

            elif action == "close":
                self.close()
                elapsed = int((time.perf_counter() - start_time) * 1000)
                return self._success({"closed": True}, latency=elapsed)

            else:
                elapsed = int((time.perf_counter() - start_time) * 1000)
                return self._error(
                    f"Unknown action '{action}'. Supported actions: 'open_store', 'get_products', 'add_to_cart', 'apply_voucher', 'checkout', 'get_cart_count', 'close'",
                    latency=elapsed
                )

        except Exception as e:
            elapsed = int((time.perf_counter() - start_time) * 1000)
            return self._error(f"Browser action error: {str(e)}", latency=elapsed)
