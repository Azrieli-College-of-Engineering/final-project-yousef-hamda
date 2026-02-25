"""
FIXED v2 - Flask App: Optimistic Locking with Version Counter
==============================================================
This is a SECOND, independent fix pattern that was NOT shown in the lecture.

Pattern: Optimistic Locking (also called Versioned CAS - Compare-And-Swap)
---------------------------------------------------------------------------
Each row carries a `version` integer. To update a row:
  1. Read: SELECT stock, version FROM products WHERE id=1
  2. Compute new values
  3. UPDATE ... WHERE id=1 AND version = <old_version>
  4. If rowcount == 0 → someone else updated first → RETRY or REJECT

Unlike pessimistic locking (BEGIN IMMEDIATE), optimistic locking never blocks
other readers. It only fails at the moment of writing if a conflict is detected.
This is the preferred pattern in high-read, low-write systems.

Why it's different from Fix 1 (BEGIN IMMEDIATE):
  - Fix 1 (pessimistic): locks the DB immediately, blocks all concurrent writers
  - Fix 2 (optimistic): allows concurrent reads, fails ONLY if version changed

Key advantage: scales better under heavy read load (e.g. browsing product page).
"""

from flask import Flask, request, jsonify
import sqlite3
import time
import os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "shop_optimistic.db")
MAX_RETRIES = 3  # How many times to retry on version conflict

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id      INTEGER PRIMARY KEY,
            name    TEXT    NOT NULL,
            stock   INTEGER NOT NULL CHECK(stock >= 0),
            version INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT    NOT NULL,
            product_id   INTEGER NOT NULL,
            purchased_at REAL    NOT NULL
        )
    """)
    conn.execute("DELETE FROM products")
    conn.execute("DELETE FROM purchases")
    # version starts at 0
    conn.execute("INSERT INTO products (id, name, stock, version) VALUES (1, 'Limited Edition Sneaker', 1, 0)")
    conn.close()

@app.route("/status")
def status():
    conn = get_db()
    product  = conn.execute("SELECT * FROM products WHERE id=1").fetchone()
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
    return jsonify({"message": "Database reset. Stock = 1, version = 0"})

@app.route("/buy", methods=["POST"])
def buy_optimistic():
    """
    OPTIMISTIC LOCKING fix.

    Algorithm:
      Loop up to MAX_RETRIES times:
        1. READ current stock + version (no lock held)
        2. If stock == 0  → sold out, return 400
        3. Try UPDATE ... WHERE id=1 AND version = <seen_version>
              SET stock = stock-1, version = version+1
        4. If rowcount == 1  → success (we won the race)
           If rowcount == 0  → version changed under us, someone else bought it first
                              → retry

    The WHERE version = <seen_version> is the "guard clause".
    If two threads both read version=5 and both try to update:
      - Thread A wins first: version becomes 6
      - Thread B's UPDATE finds version=6 ≠ 5 → rowcount=0 → retry
      - On retry, Thread B reads version=6, stock=0 → sold out
    """
    user_id = request.json.get("user_id", "unknown")

    for attempt in range(1, MAX_RETRIES + 1):
        conn = get_db()
        try:
            # Step 1: READ (no lock)
            row = conn.execute(
                "SELECT stock, version FROM products WHERE id=1"
            ).fetchone()

            if not row:
                conn.close()
                return jsonify({"success": False, "message": "Product not found"}), 404

            current_stock   = row["stock"]
            current_version = row["version"]

            # Step 2: Availability check
            if current_stock <= 0:
                conn.close()
                return jsonify({"success": False, "message": "Out of stock!"}), 400

            # Step 3: Conditional UPDATE — only succeeds if version unchanged
            conn.execute("BEGIN EXCLUSIVE")
            cursor = conn.execute(
                """UPDATE products
                      SET stock   = stock - 1,
                          version = version + 1
                    WHERE id = 1
                      AND version = ?       -- the guard clause
                      AND stock > 0""",
                (current_version,)
            )
            rows_updated = cursor.rowcount

            if rows_updated == 1:
                # Step 4a: Won the race — record the purchase
                conn.execute(
                    "INSERT INTO purchases (user_id, product_id, purchased_at) VALUES (?, 1, ?)",
                    (user_id, time.time())
                )
                conn.execute("COMMIT")
                conn.close()
                return jsonify({
                    "success": True,
                    "message": f"Purchase successful! User {user_id} bought the sneaker. (attempt {attempt}, version {current_version}→{current_version+1})"
                })
            else:
                # Step 4b: Lost the race — version changed, retry
                conn.execute("ROLLBACK")
                conn.close()
                # Small backoff before retry
                time.sleep(0.005 * attempt)
                continue

        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except:
                pass
            conn.close()
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

    return jsonify({"success": False, "message": f"Could not complete purchase after {MAX_RETRIES} attempts (high contention)."}), 409


if __name__ == "__main__":
    init_db()
    print("[OPTIMISTIC] Flash Sale server running on http://localhost:5002")
    print("Stock=1, version=0 — Optimistic Locking pattern")
    app.run(host="0.0.0.0", port=5002, threaded=True)