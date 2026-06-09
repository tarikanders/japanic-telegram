import time, sys
sys.path.insert(0, ".")
from database import SessionLocal
from services.stats import compute_stats
from datetime import date

db = SessionLocal()

t0 = time.time()
r = compute_stats(db, model="cayenne")
t1 = time.time()
print(f"stats cayenne (no date): {t1-t0:.2f}s  count={r['count']}  scatter={len(r['price_by_mileage'])}  timeline={len(r['price_over_time'])}")

t0 = time.time()
r2 = compute_stats(db, model="cayenne", date_from=date(2025, 1, 1))
t1 = time.time()
print(f"stats cayenne (2025+):   {t1-t0:.2f}s  count={r2['count']}")

t0 = time.time()
r3 = compute_stats(db, model="911")
t1 = time.time()
print(f"stats 911 (no date):     {t1-t0:.2f}s  count={r3['count']}")

db.close()
