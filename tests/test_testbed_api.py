"""
Comprehensive Test Suite for Agentic QA Lab Testbed API.
Validates Database Seed, Catalog, Voucher Calculation, Stock Locking, Checkout Transaction, and Fault Injection.
"""
import pytest
import os
import sqlite3
from fastapi.testclient import TestClient

# Set test database path before importing app
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_testbed.sqlite3")
os.environ["AQA_DB_PATH"] = TEST_DB_PATH

from app.database import init_db, get_db_connection
from app.server import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    # Setup clean test database
    init_db(reset=True)
    yield
    # Teardown
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

def test_healthcheck():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["products_count"] == 4
    assert data["orders_count"] == 0

def test_list_and_get_products():
    response = client.get("/api/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 4
    assert products[0]["sku"] == "PROD-MEC-01"
    assert products[0]["stock"] == 15

    # Get single product
    prod_id = products[0]["id"]
    single_res = client.get(f"/api/products/{prod_id}")
    assert single_res.status_code == 200
    assert single_res.json()["sku"] == "PROD-MEC-01"

def test_voucher_validation_percent():
    # DISKON10: 10% off min 100,000 max 50,000
    payload = {"code": "DISKON10", "order_subtotal": 200000.0}
    res = client.post("/api/voucher/apply", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["discount_amount"] == 20000.0
    assert data["final_subtotal"] == 180000.0

def test_voucher_validation_capped_max():
    # DISKON10: 10% of 1,000,000 = 100k, but max_discount is 50,000
    payload = {"code": "DISKON10", "order_subtotal": 1000000.0}
    res = client.post("/api/voucher/apply", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["discount_amount"] == 50000.0
    assert data["final_subtotal"] == 950000.0

def test_voucher_expired_or_invalid():
    # EXPIREDVOUCHER
    res = client.post("/api/voucher/apply", json={"code": "EXPIREDVOUCHER", "order_subtotal": 200000.0})
    assert res.status_code == 200
    assert res.json()["valid"] is False

    # NONEXISTENT
    res2 = client.post("/api/voucher/apply", json={"code": "NOTFOUND", "order_subtotal": 200000.0})
    assert res2.status_code == 200
    assert res2.json()["valid"] is False

def test_successful_checkout_and_stock_deduction():
    # Fetch mechanical keyboard (price: 750,000, stock: 15)
    products_res = client.get("/api/products")
    prod = products_res.json()[0]
    initial_stock = prod["stock"]

    checkout_payload = {
        "customer_name": "Zul SDET Tester",
        "customer_email": "zul.sdet@example.com",
        "shipping_address": "Jl. Testing Otomasi No. 1",
        "payment_method": "qris",
        "voucher_code": "DISKON10",
        "items": [
            {"product_id": prod["id"], "sku": prod["sku"], "quantity": 2}
        ]
    }

    res = client.post("/api/checkout", json=checkout_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["order_number"].startswith("ORD-")
    # Subtotal = 1,500,000. 10% capped at 50,000 -> Total = 1,450,000
    assert data["total_amount"] == 1450000.0

    # Verify Stock in DB has decremented by 2
    updated_prod = client.get(f"/api/products/{prod['id']}").json()
    assert updated_prod["stock"] == initial_stock - 2

    # Verify Order Detail API
    order_res = client.get(f"/api/orders/{data['order_number']}")
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["customer_name"] == "Zul SDET Tester"
    assert order_data["status"] == "PAID"
    assert len(order_data["items"]) == 1
    assert order_data["items"][0]["quantity"] == 2

def test_checkout_insufficient_stock():
    products_res = client.get("/api/products")
    prod = products_res.json()[0]

    # Attempt to order quantity exceeding stock
    checkout_payload = {
        "customer_name": "Greedy Buyer",
        "customer_email": "greedy@example.com",
        "shipping_address": "Jl. Stock Out",
        "payment_method": "qris",
        "items": [
            {"product_id": prod["id"], "sku": prod["sku"], "quantity": prod["stock"] + 10}
        ]
    }

    res = client.post("/api/checkout", json=checkout_payload)
    assert res.status_code == 400
    assert "tidak mencukupi" in res.json()["detail"]

def test_fault_injection_silent_failure():
    # Enable silent failure
    client.post("/api/admin/fault-injection", json={
        "simulate_silent_db_failure": True,
        "simulate_slow_db_ms": 0,
        "simulate_corrupted_stock": False
    })

    products_res = client.get("/api/products")
    prod = products_res.json()[0]
    stock_before = prod["stock"]

    checkout_payload = {
        "customer_name": "Ghost Customer",
        "customer_email": "ghost@example.com",
        "shipping_address": "Jl. Phantom Road",
        "payment_method": "qris",
        "items": [
            {"product_id": prod["id"], "sku": prod["sku"], "quantity": 1}
        ]
    }

    res = client.post("/api/checkout", json=checkout_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # But verify DB order is NOT created (simulating silent backend bug)
    order_res = client.get(f"/api/orders/{data['order_number']}")
    assert order_res.status_code == 404 # Missing from DB!

    # Stock was also not decremented
    stock_after = client.get(f"/api/products/{prod['id']}").json()["stock"]
    assert stock_after == stock_before
