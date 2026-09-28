"""
Pydantic Schemas for Target Testbed Application.
Strict models for Products, Vouchers, Cart, Checkout, and Orders.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

# --- Product Models ---
class ProductSchema(BaseModel):
    id: int
    sku: str
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    category: str
    image_url: Optional[str] = None

# --- Voucher Models ---
class VoucherApplyRequest(BaseModel):
    code: str
    order_subtotal: float = Field(..., gt=0)

class VoucherApplyResponse(BaseModel):
    valid: bool
    code: str
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    discount_amount: float = 0.0
    final_subtotal: float
    message: str

# --- Checkout & Order Models ---
class CartItemRequest(BaseModel):
    product_id: int
    sku: str
    quantity: int = Field(..., gt=0)

class CheckoutRequest(BaseModel):
    customer_name: str = Field(..., min_length=2)
    customer_email: EmailStr
    shipping_address: str = Field(..., min_length=5)
    payment_method: str = Field(..., pattern="^(qris|bank_transfer|credit_card|cod)$")
    voucher_code: Optional[str] = None
    items: List[CartItemRequest] = Field(..., min_length=1)

class OrderItemSchema(BaseModel):
    id: int
    order_id: int
    product_id: int
    sku: str
    product_name: str
    unit_price: float
    quantity: int
    line_total: float

class OrderDetailResponse(BaseModel):
    id: int
    order_number: str
    customer_name: str
    customer_email: str
    shipping_address: str
    subtotal: float
    discount_amount: float
    total_amount: float
    voucher_code: Optional[str] = None
    status: str
    payment_method: str
    created_at: str
    items: List[OrderItemSchema]

class CheckoutResponse(BaseModel):
    success: bool
    order_number: Optional[str] = None
    order_id: Optional[int] = None
    total_amount: Optional[float] = None
    message: str

# --- Fault Injection & Simulation Models ---
class FaultInjectionConfigSchema(BaseModel):
    simulate_silent_db_failure: bool = False
    simulate_slow_db_ms: int = 0
    simulate_corrupted_stock: bool = False
