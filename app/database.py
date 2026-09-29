"""
Database schema and initialization for Agentic QA Lab Testbed.
Uses SQLite for zero-setup, high-reliability local & CI testing.
"""
import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.getenv("AQA_DB_PATH", os.path.join(os.path.dirname(__file__), "testbed.sqlite3"))

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target_path = db_path or os.getenv("AQA_DB_PATH", os.path.join(os.path.dirname(__file__), "testbed.sqlite3"))
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(reset: bool = False, db_path: Optional[str] = None):
    """Initialize database tables and seed initial test data."""
    target_path = db_path or os.getenv("AQA_DB_PATH", os.path.join(os.path.dirname(__file__), "testbed.sqlite3"))
    if reset and os.path.exists(target_path):
        try:
            os.remove(target_path)
        except OSError:
            pass

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        # 1. Products Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                category TEXT NOT NULL,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Vouchers Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vouchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_type TEXT NOT NULL, -- 'percent' or 'fixed'
                discount_value REAL NOT NULL,
                min_order_value REAL DEFAULT 0.0,
                max_discount_value REAL DEFAULT 999999.0,
                quota INTEGER NOT NULL,
                used_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Orders Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                shipping_address TEXT NOT NULL,
                subtotal REAL NOT NULL,
                discount_amount REAL DEFAULT 0.0,
                total_amount REAL NOT NULL,
                voucher_code TEXT,
                status TEXT NOT NULL, -- 'PAID', 'PENDING', 'FAILED'
                payment_method TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (voucher_code) REFERENCES vouchers(code)
            );
        """)

        # 4. Order Items Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                sku TEXT NOT NULL,
                product_name TEXT NOT NULL,
                unit_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """)

        # 5. Fault Injection & Audit Log Table (For testing agent detection)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fault_injection_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                simulate_silent_db_failure INTEGER DEFAULT 0, -- 1: API returns 200 but drops DB write
                simulate_slow_db_ms INTEGER DEFAULT 0,
                simulate_corrupted_stock INTEGER DEFAULT 0
            );
        """)
        conn.execute("INSERT OR IGNORE INTO fault_injection_config (id, simulate_silent_db_failure, simulate_slow_db_ms, simulate_corrupted_stock) VALUES (1, 0, 0, 0);")

    # Seed Default Data
    seed_default_data(conn)
    conn.close()

def seed_default_data(conn: sqlite3.Connection):
    """Seed clean initial catalog and promo vouchers."""
    # Seed Products
    products = [
        ("PROD-MEC-01", "Mechanical Keyboard Wireless Pro", "RGB Custom Hot-swappable tactile switch keyboard", 750000.0, 15, "Electronics", "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&q=80"),
        ("PROD-MOU-02", "Ergonomic Gaming Mouse Ultra", "Superlight 58g wireless gaming mouse with 26K DPI sensor", 450000.0, 20, "Electronics", "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=500&q=80"),
        ("PROD-HDP-03", "Noise Cancelling Headset Studio", "Active ANC over-ear headphones with 40h battery life", 1200000.0, 8, "Audio", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80"),
        ("PROD-MAT-04", "Deskmat Anti-Slip XL Minimalist", "Waterproof smooth micro-woven cloth desk pad 900x400mm", 150000.0, 50, "Accessories", "https://images.unsplash.com/photo-1616440347437-b1c73416efc2?w=500&q=80"),
    ]

    for sku, name, desc, price, stock, cat, img in products:
        conn.execute("""
            INSERT INTO products (sku, name, description, price, stock, category, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                name=excluded.name,
                price=excluded.price,
                stock=excluded.stock,
                category=excluded.category,
                image_url=excluded.image_url;
        """, (sku, name, desc, price, stock, cat, img))

    # Seed Vouchers
    vouchers = [
        ("DISKON10", "percent", 10.0, 100000.0, 50000.0, 100, 0, 1), # 10% off min 100k max 50k
        ("FLAT50K", "fixed", 50000.0, 300000.0, 50000.0, 10, 0, 1),   # 50k flat discount min 300k
        ("FLASH1", "percent", 50.0, 50000.0, 100000.0, 1, 0, 1),       # 1 quota flash voucher (for race condition tests)
        ("EXPIREDVOUCHER", "percent", 20.0, 0.0, 50000.0, 0, 0, 0),     # Inactive voucher
    ]

    for code, dtype, val, min_val, max_val, quota, used, active in vouchers:
        conn.execute("""
            INSERT INTO vouchers (code, discount_type, discount_value, min_order_value, max_discount_value, quota, used_count, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                discount_type=excluded.discount_type,
                discount_value=excluded.discount_value,
                min_order_value=excluded.min_order_value,
                max_discount_value=excluded.max_discount_value,
                quota=excluded.quota,
                used_count=excluded.used_count,
                is_active=excluded.is_active;
        """, (code, dtype, val, min_val, max_val, quota, used, active))

    conn.commit()

if __name__ == "__main__":
    init_db(reset=True)
    print("Database initialized successfully at:", DB_PATH)
