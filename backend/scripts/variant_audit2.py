"""Audit A0 part 2 : check listings for variant info (annonces ont souvent plus de détail)."""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "japan_auctions.db")
db = sqlite3.connect(DB_PATH)
cur = db.cursor()

suspects = [
    ("Cayman",       "cayman"),
    ("Boxster",      "boxster"),
    ("GranTurismo",  "granturismo"),
    ("Ghibli",       "ghibli"),
    ("Panamera",     "panamera"),
    ("Cayenne",      "cayenne"),
    ("911",          "911"),
    ("Lamborghini",  "lamborghini"),
]

print("=== LISTINGS model_raw (posted 2025+) ===\n")
for label, keyword in suspects:
    cur.execute("""
        SELECT model_raw, model_normalized, COUNT(*) AS cnt
        FROM listings
        WHERE posted_date >= '2025-01-01'
          AND LOWER(model_raw) LIKE ?
          AND model_raw IS NOT NULL
        GROUP BY model_raw, model_normalized
        ORDER BY cnt DESC
        LIMIT 15
    """, (f'%{keyword}%',))
    rows = cur.fetchall()
    if rows:
        total = sum(r[2] for r in rows)
        print(f"--- {label}  ({total} total listings) ---")
        for r in rows:
            print(f"  {r[2]:4d}  raw={r[0]!r:55s}  norm={r[1]!r}")
        print()

db.close()
