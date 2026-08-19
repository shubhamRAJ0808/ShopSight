"""
generate_synthetic_data.py
───────────────────────────────────────────────────────────────────────────
Seeds a shop's sales history with realistic synthetic data so the ML
forecasting model has enough signal to learn from (a linear regression on
4-7 rows is basically guessing).

What makes this "realistic" rather than random noise:
  • an underlying month-over-month growth trend per product
  • seasonality — electronics spike Oct-Dec (festive/holiday season) and
    dip during the monsoon months (Jun-Aug), matching typical Indian
    retail demand curves
  • weekday effect — more orders on weekends
  • per-order price jitter (small real-world price variation, not a
    single fixed price forever)
  • Poisson-distributed daily order counts, not a flat number every day

Usage:
    python generate_synthetic_data.py --username admin --months 24

  --username   the login username of the shop to seed data for (required)
  --months     how many months of history to generate (default 24)
  --seed       random seed for reproducibility (default 42)
  --wipe       delete this shop's existing sales rows first
"""
import os, argparse, random
from datetime import date, timedelta
import numpy as np
import mysql.connector

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'user':     os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'sales_dashboard'),
}

# product: (base_price, base_daily_demand, monthly_growth_pct, seasonal_products)
PRODUCTS = {
    'Laptop':      {'price': 50000, 'base_demand': 0.35, 'growth': 0.012},
    'Phone':       {'price': 20000, 'base_demand': 0.60, 'growth': 0.018},
    'Headphones':  {'price':  2000, 'base_demand': 1.10, 'growth': 0.008},
    'Tablet':      {'price': 15000, 'base_demand': 0.30, 'growth': 0.010},
    'Camera':      {'price': 30000, 'base_demand': 0.18, 'growth': 0.005},
    'Smartwatch':  {'price':  8000, 'base_demand': 0.45, 'growth': 0.020},
}

def seasonal_multiplier(d: date) -> float:
    """Festive-season bump (Oct-Dec), monsoon dip (Jun-Aug), for electronics retail."""
    m = d.month
    if m in (10, 11, 12): return 1.55       # Diwali / year-end shopping
    if m in (6, 7, 8):     return 0.75       # monsoon slowdown
    if m in (1, 2):         return 1.15       # new-year / republic-day sales
    return 1.0

def weekday_multiplier(d: date) -> float:
    return 1.35 if d.weekday() >= 5 else 1.0   # Sat/Sun bump

def get_shop_id(username: str):
    db = mysql.connector.connect(**DB_CONFIG)
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT shop_id FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    db.close()
    if not row:
        raise SystemExit(f"No user found with username '{username}'. Register that shop first.")
    return row['shop_id']

def generate(shop_id: int, months: int, seed: int, wipe: bool):
    random.seed(seed); np.random.seed(seed)

    end   = date.today()
    start = (end.replace(day=1) - timedelta(days=1)) # last day of prev month, walked back below
    start = date(end.year, end.month, 1)
    for _ in range(months):
        start = (start - timedelta(days=1)).replace(day=1)

    db = mysql.connector.connect(**DB_CONFIG)
    cur = db.cursor()

    if wipe:
        cur.execute("DELETE FROM sales WHERE shop_id=%s", (shop_id,))
        db.commit()

    rows = []
    day = start
    month_index = 0
    cur_month = start.month
    while day <= end:
        if day.month != cur_month:
            month_index += 1
            cur_month = day.month
        for product, cfg in PRODUCTS.items():
            trend       = (1 + cfg['growth']) ** month_index
            season      = seasonal_multiplier(day)
            weekday_adj = weekday_multiplier(day)
            lam = max(0.01, cfg['base_demand'] * trend * season * weekday_adj)
            n_orders = np.random.poisson(lam)
            for _ in range(n_orders):
                qty        = random.randint(1, 3)
                price_jit  = cfg['price'] * random.uniform(0.95, 1.06)
                rows.append((shop_id, product, qty, round(price_jit, 2), day))
        day += timedelta(days=1)

    cur.executemany(
        "INSERT INTO sales (shop_id, product, quantity, price, date) VALUES (%s,%s,%s,%s,%s)",
        rows)
    db.commit()
    db.close()
    print(f"Inserted {len(rows)} synthetic sales rows for shop_id={shop_id} "
          f"spanning {start} → {end}.")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--username', required=True, help='Login username of the shop to seed')
    ap.add_argument('--months', type=int, default=24)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--wipe', action='store_true', help="Delete this shop's existing sales first")
    args = ap.parse_args()

    sid = get_shop_id(args.username)
    generate(sid, args.months, args.seed, args.wipe)
