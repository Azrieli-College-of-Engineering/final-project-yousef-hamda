"""
FIXED Flask App - Flash Sale Inventory System
Fix: Atomic UPDATE with WHERE stock > 0 (no separate check/use race window)
     Wrapped in explicit transaction + WAL mode for SQLite concurrency safety.

The key fix: instead of CHECK then USE, we do a single atomic UPDATE that
only succeeds if stock > 0. The rowcount tells us if we "won" the race.
"""

from flask import Flask, request, jsonify
import sqlite3
import time
import os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "shop_fixed.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")   # Better concurrency
    conn.execute("PRAGMA busy_timeout=5000")  # Wait up to 5s on lock
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            stock INTEGER NOT NULL CHECK(stock >= 0)  -- DB-level guard
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
    conn.execute("DELETE FROM products")
    conn.execute("DELETE FROM purchases")
    conn.execute("INSERT INTO products (id, name, stock) VALUES (1, 'Limited Edition Sneaker', 1)")
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
def buy_fixed():
    """
    FIXED endpoint.
    Uses a single atomic UPDATE with a conditional WHERE clause.
    No separate SELECT is needed — the UPDATE itself is the check AND the use.
    SQLite serializes writes, so only one request can decrement at a time.
    
    Pattern: "Compare-and-Swap" / Optimistic Locking
    """
    user_id = request.json.get("user_id", "unknown")
    conn = get_db()

    try:
        conn.execute("BEGIN IMMEDIATE")  # Exclusive write lock from the start

        # ATOMIC: Check AND decrement in one statement.
        # If stock is 0, no row is updated => rowcount = 0 => sold out.
        cursor = conn.execute(
            "UPDATE products SET stock = stock - 1 WHERE id=1 AND stock > 0"
        )
        rows_updated = cursor.rowcount

        if rows_updated == 0:
            conn.execute("ROLLBACK")
            conn.close()
            return jsonify({"success": False, "message": "Out of stock!"}), 400

        # Only reaches here if we successfully decremented
        conn.execute(
            "INSERT INTO purchases (user_id, product_id, purchased_at) VALUES (?, 1, ?)",
            (user_id, time.time())
        )
        conn.execute("COMMIT")
        conn.close()
        return jsonify({"success": True, "message": f"Purchase successful! User {user_id} bought the sneaker."})

    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except:
            pass
        conn.close()
        return jsonify({"success": False, "message": f"Transaction error: {str(e)}"}), 500

if __name__ == "__main__":
    init_db()
    print("[FIXED] Flash Sale server running on http://localhost:5001")
    print("Stock initialized to 1 item")
    app.run(host="0.0.0.0", port=5001, threaded=True)