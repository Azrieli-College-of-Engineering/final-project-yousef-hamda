[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/Nt4zUlkt)
# Race Condition / TOCTOU — Flash Sale Inventory Oversell
## Web Systems Security — Final Project (Track A)
### Scenario different from lecture: Flash Sale (NOT coupon reuse)
### Attack tool different from lecture: Python threading.Barrier (NOT BurpSuite)
### Fix 2 (Optimistic Lock) NOT covered in lecture — original addition

## How to Run
```bash
pip install flask requests

# Terminal 1 - Vulnerable App
python src/vulnerable/app_vulnerable.py

# Terminal 2 - Fix 1: Pessimistic Lock
python src/fixed/app_fix1_pessimistic.py

# Terminal 3 - Fix 2: Optimistic Lock
python src/fixed/app_fix2_optimistic.py

# Terminal 4 - Run the Attack
python src/poc/exploit.py --target all --threads 10
```

## Expected Results
| Server       | Result             | Final Stock | Purchases |
|-------------|-------------------|-------------|-----------|
| Vulnerable  | OVERSELL           | -8          | 9         |
| Fix 1 (Pessimistic) | PROTECTED  | 0           | 1         |
| Fix 2 (Optimistic)  | PROTECTED  | 0 (ver=1)   | 1         |