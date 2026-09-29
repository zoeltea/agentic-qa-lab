"""Checkout Page Object Model (POM) for Agentic QA Lab Testbed."""
from typing import Dict, Any, Optional
from playwright.sync_api import Page


class CheckoutPage:
    """Encapsulates locator selectors and semantic actions for Cart & Checkout flow."""

    CART_ITEMS = "#cart-items-container"
    CART_BADGE = "#cart-badge"
    CART_TOTAL_ITEMS = "#cart-total-items"
    
    # Voucher Elements
    VOUCHER_INPUT = "#voucher-input"
    BTN_APPLY_VOUCHER = "#btn-apply-voucher"
    VOUCHER_FEEDBACK = "#voucher-feedback"

    # Price Breakdown
    SUMMARY_SUBTOTAL = "#summary-subtotal"
    SUMMARY_DISCOUNT = "#summary-discount"
    SUMMARY_TOTAL = "#summary-total"

    # Form Inputs
    INPUT_NAME = "#input-customer-name"
    INPUT_EMAIL = "#input-customer-email"
    INPUT_ADDRESS = "#input-customer-address"
    SELECT_PAYMENT = "#select-payment-method"
    BTN_CHECKOUT = "#btn-checkout"
    CHECKOUT_ERROR = "#checkout-error"

    # Success Modal Elements
    MODAL_SUCCESS = "#order-success-modal"
    MODAL_ORDER_NUMBER = "#modal-order-number"
    MODAL_ORDER_TOTAL = "#modal-order-total"
    MODAL_VOUCHER_CODE = "#modal-voucher-code"
    MODAL_SUCCESS_TITLE = "#modal-success-title"

    @classmethod
    def apply_voucher(cls, page: Page, code: str) -> Dict[str, Any]:
        """Fill voucher code and click apply. Returns feedback text and status."""
        page.wait_for_selector(cls.VOUCHER_INPUT, state="visible", timeout=5000)
        page.fill(cls.VOUCHER_INPUT, code)
        page.click(cls.BTN_APPLY_VOUCHER)
        
        # Wait for feedback visibility
        page.wait_for_selector(cls.VOUCHER_FEEDBACK + ":not(.hidden)", state="visible", timeout=5000)
        feedback_el = page.locator(cls.VOUCHER_FEEDBACK)
        feedback_text = feedback_el.inner_text().strip()
        is_success = "text-emerald-700" in (feedback_el.get_attribute("class") or "")
        
        return {
            "applied": is_success,
            "message": feedback_text
        }

    @classmethod
    def fill_customer_info(
        cls,
        page: Page,
        name: str = "Budi Santoso",
        email: str = "budi.s@example.com",
        address: str = "Jl. Sudirman No. 45, Jakarta",
        payment_method: str = "qris"
    ):
        """Fill in customer details and select payment method."""
        page.wait_for_selector(cls.INPUT_NAME, state="visible", timeout=5000)
        page.fill(cls.INPUT_NAME, name)
        page.fill(cls.INPUT_EMAIL, email)
        page.fill(cls.INPUT_ADDRESS, address)
        page.select_option(cls.SELECT_PAYMENT, payment_method)

    @classmethod
    def submit_checkout(cls, page: Page) -> Dict[str, Any]:
        """Click pay button and wait for order success modal."""
        page.wait_for_selector(cls.BTN_CHECKOUT, state="visible", timeout=5000)
        btn = page.locator(cls.BTN_CHECKOUT)
        if btn.is_disabled():
            return {"success": False, "error": "Checkout button is disabled (cart empty or invalid state)"}

        btn.click()

        # Wait for either success modal or error box
        page.wait_for_selector(
            f"{cls.MODAL_SUCCESS}:not(.hidden), {cls.CHECKOUT_ERROR}:not(.hidden)",
            timeout=10000
        )

        if page.locator(cls.MODAL_SUCCESS).is_visible():
            order_num = page.locator(cls.MODAL_ORDER_NUMBER).inner_text().strip()
            total_str = page.locator(cls.MODAL_ORDER_TOTAL).inner_text().strip()
            voucher = page.locator(cls.MODAL_VOUCHER_CODE).inner_text().strip()
            return {
                "success": True,
                "order_number": order_num,
                "total_amount_display": total_str,
                "voucher_code": voucher if voucher != "-" else None
            }
        else:
            err_msg = page.locator(cls.CHECKOUT_ERROR).inner_text().strip()
            return {
                "success": False,
                "error": err_msg
            }
