[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/Nt4zUlkt)
# Race Condition / TOCTOU — Flash Sale Inventory Oversell
## Web Systems Security — Final Project (Track A)
### Azrieli College of Engineering | 2026

---

## Student Information
| Field | Details |
|---|---|
| **Student** | Yousef Hamda |
| **College** | Azrieli College of Engineering |
| **Course** | Web Systems Security |
| **Track** | Track A — POC Attack Research & Implementation |
| **Vulnerability** | Race Condition / TOCTOU (Time-Of-Check to Time-Of-Use) |
| **Scenario** | Flash Sale Inventory Oversell |

---

## Project Overview

This project demonstrates a **Race Condition / TOCTOU** vulnerability in a flash sale web application.

When multiple users try to buy the last item simultaneously, a vulnerable server allows all of them to succeed — resulting in **negative stock (Oversell)**.

> ⚠️ **This scenario is different from the lecture examples.**
> The lecture covered: coupon reuse, MFA bypass, and cart manipulation.
> This project uses: Flash Sale Inventory Oversell — a different TOCTOU variant.

---

## Project Structure

```
final-project-yousef-hamda/
│
├── src/
│   ├── vulnerable/
│   │   └── app_vulnerable.py       ← Vulnerable Flask app (port 5000)
│   ├── fixed/
│   │   ├── app_fix1_pessimistic.py ← Fix 1: Pessimistic Lock (port 5001)
│   │   └── app_fix2_optimistic.py  ← Fix 2: Optimistic Lock / Version Counter (port 5002)
│   └── poc/
│       └── exploit.py              ← Attack script (Python threading.Barrier)
│
├── diagrams/
│   └── race_condition_diagram.png  ← 3-panel attack flow diagram
│
├── report/
│   └── Race_Condition_Report_FINAL.docx ← Full written report
│
├── .gitignore
├── LICENSE
└── README.md
```

---

## How to Run

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
# Terminal 4 — Run attack against all 3 servers
python src/poc/exploit.py --target all --threads 10

# Or test a specific server:
python src/poc/exploit.py --target vulnerable
python src/poc/exploit.py --target fixed
python src/poc/exploit.py --target optimistic

# Increase thread count:
python src/poc/exploit.py --target all --threads 20
```

---

## API Endpoints

Each server exposes the same 3 endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/status` | Returns current stock, version, and all purchases |
| `POST` | `/buy` | Purchase endpoint (body: `{"user_id": "alice"}`) |
| `POST` | `/reset` | Resets database: stock=1, purchases cleared |

---

## Expected Results

| Server | Port | Result | Final Stock | Purchases |
|---|---|---|---|---|
| Vulnerable | 5000 | 🔴 OVERSELL | -9 | 10 |
| Fix 1 — Pessimistic Lock | 5001 | 🟢 PROTECTED | 0 | 1 |
| Fix 2 — Optimistic Lock | 5002 | 🟢 PROTECTED | 0 (ver=1) | 1 |

---

## How the Attack Works

The vulnerable app has a **TOCTOU flaw** — three separate, non-atomic steps:

```
1. CHECK  → SELECT stock FROM products   (reads stock = 1)
2. DELAY  → time.sleep(0.05)             ← RACE WINDOW OPEN
3. USE    → UPDATE products SET stock-1  ← RACE WINDOW CLOSES
```

If 10 threads all complete **step 1** before any reaches **step 3**,
they all see `stock = 1`, all pass the check, and all decrement.

**Result: stock = 1 - 10 = -9**

---

## Defense Mechanisms

### Fix 1 — Pessimistic Lock (BEGIN IMMEDIATE)
```sql
BEGIN IMMEDIATE;  -- acquires exclusive write lock
UPDATE products SET stock = stock - 1 WHERE id=1 AND stock > 0;
-- rowcount = 0 → sold out, ROLLBACK
-- rowcount = 1 → success, COMMIT
```

### Fix 2 — Optimistic Lock / Version Counter *(not covered in lecture)*
```sql
-- Read current version (no lock)
SELECT stock, version FROM products WHERE id=1;

-- Conditional update — only succeeds if version unchanged
UPDATE products
   SET stock = stock - 1, version = version + 1
 WHERE id = 1 AND version = ? AND stock > 0;

-- rowcount = 0 → version changed (conflict detected) → retry
-- rowcount = 1 → success
```

---

## Attack Tool — vs. Lecture

| Aspect | Lecture | This Project |
|---|---|---|
| **Tool** | BurpSuite + Last-Byte Sync + Single-Packet (HTTP/2) | Python `threading.Barrier` |
| **Scenario** | Coupon reuse / MFA bypass / Cart manipulation | Flash Sale Inventory Oversell |
| **Language** | Node.js / Express | Python / Flask |
| **Database** | MongoDB | SQLite (WAL mode) |
| **Fix shown** | Theoretical only | Full working code (2 patterns) |

> `threading.Barrier` creates a rendezvous point for N threads —
> all threads wait until everyone is ready, then fire simultaneously.
> Same effect as BurpSuite's parallel attack, but at the OS thread level.

---

## Sources

- PortSwigger Web Security Academy — Race Conditions: https://portswigger.net/web-security/race-conditions
- OWASP Race Condition: https://owasp.org/www-community/vulnerabilities/Race_Condition
- Van Goethem et al. (2020) — Timeless Timing Attacks — USENIX Security
- Kettle, J. (2023) — Smashing the state machine — PortSwigger Research
- SQLite WAL mode: https://www.sqlite.org/wal.html
- Python threading.Barrier: https://docs.python.org/3/library/threading.html#threading.Barrier

