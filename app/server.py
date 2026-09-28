"""
FastAPI Server for Agentic QA Lab Testbed.
Provides REST APIs for E-Commerce flow + HTML Web UI + SDET Diagnostic endpoints.
"""
import os
import time
import uuid
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_db_connection, init_db, DB_PATH
from app.schemas import (
    ProductSchema,
    VoucherApplyRequest,
    VoucherApplyResponse,
    CheckoutRequest,
    CheckoutResponse,
    OrderDetailResponse,
    OrderItemSchema,
    FaultInjectionConfigSchema
)

app = FastAPI(
    title="Agentic QA Lab Testbed",
    description="Target E-Commerce Testbed Application for Multi-Layer Agentic QA Testing",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Templates & Static
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
def startup_event():
    # Ensure DB is initialized
    init_db(reset=False)

# --- WEB UI ROUTE ---
@app.get("/", response_class=HTMLResponse)
def index_view(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

# --- HEALTHCHECK & DIAGNOSTICS ---
@app.get("/api/health")
def healthcheck():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) as count FROM products")
        p_count = cur.fetchone()["count"]
        cur.execute("SELECT count(*) as count FROM orders")
        o_count = cur.fetchone()["count"]
        return {
            "status": "healthy",
            "service": "agentic-qa-testbed",
            "database": "connected",
            "products_count": p_count,
            "orders_count": o_count,
            "timestamp": time.time()
        }
    finally:
        conn.close()

# --- PRODUCT CATALOG APIS ---
@app.get("/api/products", response_model=List[ProductSchema])
def list_products():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, sku, name, description, price, stock, category, image_url FROM products ORDER BY id ASC")
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

@app.get("/api/products/{product_id}", response_model=ProductSchema)
def get_product(product_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, sku, name, description, price, stock, category, image_url FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return dict(row)
    finally:
        conn.close()

# --- VOUCHER VERIFICATION API ---
@app.post("/api/voucher/apply", response_model=VoucherApplyResponse)
def apply_voucher(payload: VoucherApplyRequest):
    code = payload.code.strip().upper()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM vouchers WHERE code = ?", (code,))
        v = cur.fetchone()

        if not v:
            return VoucherApplyResponse(
                valid=False,
                code=code,
                discount_amount=0.0,
                final_subtotal=payload.order_subtotal,
                message=f"Kode voucher '{code}' tidak ditemukan."
            )

        if v["is_active"] == 0:
            return VoucherApplyResponse(
                valid=False,
                code=code,
                discount_amount=0.0,
                final_subtotal=payload.order_subtotal,
                message=f"Voucher '{code}' sudah tidak aktif / expired."
            )

        if v["used_count"] >= v["quota"]:
            return VoucherApplyResponse(
                valid=False,
                code=code,
                discount_amount=0.0,
                final_subtotal=payload.order_subtotal,
                message=f"Kuota voucher '{code}' sudah habis ({v['used_count']}/{v['quota']})."
            )

        if payload.order_subtotal < v["min_order_value"]:
            return VoucherApplyResponse(
                valid=False,
                code=code,
                discount_amount=0.0,
                final_subtotal=payload.order_subtotal,
                message=f"Minimal belanja untuk voucher ini adalah Rp {v['min_order_value']:,.0f}."
            )

        # Calculate discount
        if v["discount_type"] == "percent":
            discount = (payload.order_subtotal * (v["discount_value"] / 100.0))
            if discount > v["max_discount_value"]:
                discount = v["max_discount_value"]
        else:
            discount = min(v["discount_value"], payload.order_subtotal)

        final_subtotal = max(0.0, payload.order_subtotal - discount)

        return VoucherApplyResponse(
            valid=True,
            code=code,
            discount_type=v["discount_type"],
            discount_value=v["discount_value"],
            discount_amount=discount,
            final_subtotal=final_subtotal,
            message=f"Voucher '{code}' berhasil dipasang! Diskon Rp {discount:,.0f}"
        )
    finally:
        conn.close()

# --- CHECKOUT & ORDER CREATION API ---
@app.post("/api/checkout", response_model=CheckoutResponse)
def process_checkout(payload: CheckoutRequest):
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Check Fault Injection status
        cur.execute("SELECT simulate_silent_db_failure, simulate_slow_db_ms FROM fault_injection_config WHERE id = 1")
        fault_cfg = cur.fetchone()
        simulate_silent_failure = bool(fault_cfg["simulate_silent_db_failure"]) if fault_cfg else False
        simulate_slow_ms = fault_cfg["simulate_slow_db_ms"] if fault_cfg else 0

        if simulate_slow_ms > 0:
            time.sleep(simulate_slow_ms / 1000.0)

        # 1. Validate Items & Stock Lock
        subtotal = 0.0
        validated_items = []

        for item in payload.items:
            cur.execute("SELECT id, sku, name, price, stock FROM products WHERE id = ?", (item.product_id,))
            prod = cur.fetchone()
            if not prod:
                raise HTTPException(status_code=400, detail=f"Produk ID {item.product_id} tidak ditemukan.")

            if prod["stock"] < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stok produk '{prod['name']}' tidak mencukupi (Tersedia: {prod['stock']}, Diminta: {item.quantity})."
                )

            line_total = prod["price"] * item.quantity
            subtotal += line_total
            validated_items.append({
                "product_id": prod["id"],
                "sku": prod["sku"],
                "name": prod["name"],
                "unit_price": prod["price"],
                "quantity": item.quantity,
                "line_total": line_total
            })

        # 2. Process Voucher (if applied)
        discount_amount = 0.0
        voucher_code = None

        if payload.voucher_code and payload.voucher_code.strip():
            voucher_code = payload.voucher_code.strip().upper()
            cur.execute("SELECT * FROM vouchers WHERE code = ?", (voucher_code,))
            v = cur.fetchone()
            if not v or v["is_active"] == 0 or v["used_count"] >= v["quota"] or subtotal < v["min_order_value"]:
                raise HTTPException(status_code=400, detail=f"Voucher '{voucher_code}' tidak valid atau kuota habis.")

            if v["discount_type"] == "percent":
                discount_amount = min(subtotal * (v["discount_value"] / 100.0), v["max_discount_value"])
            else:
                discount_amount = min(v["discount_value"], subtotal)

        total_amount = max(0.0, subtotal - discount_amount)
        order_number = f"ORD-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"

        # 3. Fault Injection: Silent DB Failure (Returns success to UI, but aborts DB write)
        if simulate_silent_failure:
            # We simulate backend returning 200 OK without writing to DB to test agent cross-layer detection!
            return CheckoutResponse(
                success=True,
                order_number=order_number,
                order_id=99999,
                total_amount=total_amount,
                message="Checkout berhasil (SIMULATED SILENT FAILURE ACTIVE)"
            )

        # 4. Atomic Transaction: Deduct Stock, Increment Voucher, Create Order
        # Deduct Stock
        for it in validated_items:
            cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (it["quantity"], it["product_id"]))

        # Increment Voucher Quota
        if voucher_code:
            cur.execute("UPDATE vouchers SET used_count = used_count + 1 WHERE code = ?", (voucher_code,))

        # Insert Order
        cur.execute("""
            INSERT INTO orders (
                order_number, customer_name, customer_email, shipping_address,
                subtotal, discount_amount, total_amount, voucher_code,
                status, payment_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_number, payload.customer_name, str(payload.customer_email), payload.shipping_address,
            subtotal, discount_amount, total_amount, voucher_code,
            "PAID", payload.payment_method
        ))
        order_id = cur.lastrowid

        # Insert Order Items
        for it in validated_items:
            cur.execute("""
                INSERT INTO order_items (
                    order_id, product_id, sku, product_name, unit_price, quantity, line_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, it["product_id"], it["sku"], it["name"],
                it["unit_price"], it["quantity"], it["line_total"]
            ))

        conn.commit()

        return CheckoutResponse(
            success=True,
            order_number=order_number,
            order_id=order_id,
            total_amount=total_amount,
            message=f"Order {order_number} berhasil dibuat dan dibayar!"
        )
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database transaction error: {str(e)}")
    finally:
        conn.close()

# --- ORDER DETAIL API ---
@app.get("/api/orders/{order_number}", response_model=OrderDetailResponse)
def get_order(order_number: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_number} tidak ditemukan.")

        cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
        items_rows = cur.fetchall()

        items = [OrderItemSchema(
            id=r["id"],
            order_id=r["order_id"],
            product_id=r["product_id"],
            sku=r["sku"],
            product_name=r["product_name"],
            unit_price=r["unit_price"],
            quantity=r["quantity"],
            line_total=r["line_total"]
        ) for r in items_rows]

        return OrderDetailResponse(
            id=order["id"],
            order_number=order["order_number"],
            customer_name=order["customer_name"],
            customer_email=order["customer_email"],
            shipping_address=order["shipping_address"],
            subtotal=order["subtotal"],
            discount_amount=order["discount_amount"],
            total_amount=order["total_amount"],
            voucher_code=order["voucher_code"],
            status=order["status"],
            payment_method=order["payment_method"],
            created_at=str(order["created_at"]),
            items=items
        )
    finally:
        conn.close()

# --- SDET ADMIN & FAULT INJECTION APIS ---
@app.get("/api/admin/fault-injection")
def get_fault_injection():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM fault_injection_config WHERE id = 1")
        cfg = cur.fetchone()
        return dict(cfg) if cfg else {}
    finally:
        conn.close()

@app.post("/api/admin/fault-injection")
def set_fault_injection(cfg: FaultInjectionConfigSchema):
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                UPDATE fault_injection_config
                SET simulate_silent_db_failure = ?,
                    simulate_slow_db_ms = ?,
                    simulate_corrupted_stock = ?
                WHERE id = 1
            """, (int(cfg.simulate_silent_db_failure), cfg.simulate_slow_db_ms, int(cfg.simulate_corrupted_stock)))
        return {"status": "success", "config": cfg.model_dump()}
    finally:
        conn.close()

@app.post("/api/admin/reset-db")
def reset_database():
    init_db(reset=True)
    return {"status": "success", "message": "Database successfully reset and re-seeded."}
