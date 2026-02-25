"""
VULNERABLE Flask App - Flash Sale Inventory System
Demonstrates: Race Condition / TOCTOU (Time-Of-Check to Time-Of-Use)

Scenario: A flash sale with only 1 item in stock.
Vulnerable because: check stock -> sleep -> decrement happen NON-atomically.
An attacker sending concurrent requests can all pass the check before any update runs.
"""

from flask import Flask, request, jsonify
import sqlite3
import time
import os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            stock INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            purchased_at REAL NOT NULL
        )
    """)
    # Reset: 1 item in stock
    conn.execute("DELETE FROM products")
    conn.execute("DELETE FROM purchases")
    conn.execute("INSERT INTO products (id, name, stock) VALUES (1, 'Limited Edition Sneaker', 1)")
    conn.commit()
    conn.close()

@app.route("/status")
def status():
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id=1").fetchone()
    purchases = conn.execute("SELECT * FROM purchases").fetchall()
    conn.close()
    return jsonify({
        "product": dict(product),
        "total_purchases": len(purchases),
        "purchases": [dict(p) for p in purchases]
    })

@app.route("/reset", methods=["POST"])
def reset():
    init_db()
    return jsonify({"message": "Database reset. Stock = 1"})

@app.route("/buy", methods=["POST"])
def buy_vulnerable():
    """
    VULNERABLE endpoint.
    TOCTOU bug: check and update are NOT atomic.
    1. Read stock  (CHECK)
    2. Sleep a bit  (simulates processing delay / DB round-trip latency)
    3. Decrement stock  (USE)
    
    If 10 requests all hit step 1 before any reaches step 3,
    all of them see stock=1 and all succeed => oversell!
    """
    user_id = request.json.get("user_id", "unknown")
    conn = get_db()

    # STEP 1: CHECK
    product = conn.execute("SELECT * FROM products WHERE id=1").fetchone()
    stock = product["stock"]

    if stock <= 0:
        conn.close()
        return jsonify({"success": False, "message": "Out of stock!"}), 400

    # STEP 2: Simulate processing delay (payment gateway, etc.)
    time.sleep(0.05)  # 50ms delay — makes race condition reliable

    # STEP 3: USE (decrement) - by now another thread may have already decremented!
    conn.execute("UPDATE products SET stock = stock - 1 WHERE id=1")
    conn.execute(
        "INSERT INTO purchases (user_id, product_id, purchased_at) VALUES (?, 1, ?)",
        (user_id, time.time())
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Purchase successful! User {user_id} bought the sneaker."})

if __name__ == "__main__":
    init_db()
    print("[VULNERABLE] Flash Sale server running on http://localhost:5000")
    print("Stock initialized to 1 item")
    app.run(host="0.0.0.0", port=5000, threaded=True)