"""Catalog Page Object Model (POM) for Agentic QA Lab Testbed."""
from typing import List, Dict, Any, Optional
from playwright.sync_api import Page


class CatalogPage:
    """Encapsulates locator selectors and semantic actions for Product Catalog."""

    URL_PATH = "/"
    GRID = "#product-grid"
    PRODUCT_COUNT = "#product-count"
    CARD_PATTERN = "#product-card-{id}"
    BTN_ADD_PATTERN = "#btn-add-{id}"
    STOCK_PATTERN = "#stock-{id}"
    CART_BADGE = "#cart-badge"

    @classmethod
    def navigate(cls, page: Page, base_url: str):
        """Navigate to catalog homepage and wait for product grid to be ready."""
        url = base_url.rstrip("/") + cls.URL_PATH
        page.goto(url)
        page.wait_for_selector(cls.GRID, state="visible", timeout=10000)

    @classmethod
    def get_rendered_products(cls, page: Page) -> List[Dict[str, Any]]:
        """Extract all rendered product cards from the DOM."""
        page.wait_for_selector(cls.GRID, state="visible", timeout=5000)
        cards = page.locator("[id^='product-card-']").all()
        products = []
        for card in cards:
            card_id_str = card.get_attribute("id") or ""
            prod_id = int(card_id_str.replace("product-card-", "")) if "product-card-" in card_id_str else None
            sku = card.get_attribute("data-sku") or ""
            name = card.locator("h3").inner_text().strip() if card.locator("h3").count() > 0 else ""
            stock_el = card.locator(f"#stock-{prod_id}") if prod_id else None
            stock = int(stock_el.inner_text().strip()) if stock_el and stock_el.count() > 0 else 0

            products.append({
                "id": prod_id,
                "sku": sku,
                "name": name,
                "stock": stock
            })
        return products

    @classmethod
    def add_product_to_cart(cls, page: Page, product_id: int) -> bool:
        """Click the add to cart button for the specified product id."""
        btn_selector = cls.BTN_ADD_PATTERN.format(id=product_id)
        page.wait_for_selector(btn_selector, state="visible", timeout=5000)
        btn = page.locator(btn_selector)
        if btn.is_disabled():
            return False
        btn.click()
        # Wait briefly for cart badge to update
        page.wait_for_selector(cls.CART_BADGE, state="visible", timeout=5000)
        return True

    @classmethod
    def get_cart_badge_count(cls, page: Page) -> int:
        """Get the item count badge displayed in header."""
        badge = page.locator(cls.CART_BADGE)
        if not badge.is_visible():
            return 0
        text = badge.inner_text().strip()
        return int(text) if text.isdigit() else 0

    @classmethod
    def get_stock(cls, page: Page, product_id: int) -> int:
        """Get currently displayed stock count on product card."""
        stock_sel = cls.STOCK_PATTERN.format(id=product_id)
        page.wait_for_selector(stock_sel, state="visible", timeout=5000)
        text = page.locator(stock_sel).inner_text().strip()
        return int(text) if text.isdigit() else 0
