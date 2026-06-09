"""
Audit A0 : distribution des model_raw 2025+ pour identifier les variants perdus.
Usage: python scripts/variant_audit.py
"""
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "japan_auctions.db")

db = sqlite3.connect(DB_PATH)
cur = db.cursor()

print("=== TOP 40 model_normalized (auctions 2025+) ===")
cur.execute("""
    SELECT model_normalized, COUNT(*) AS cnt
    FROM auctions
    WHERE auction_date >= '2025-01-01' AND model_normalized IS NOT NULL
    GROUP BY model_normalized
    ORDER BY cnt DESC
    LIMIT 40
""")
for row in cur.fetchall():
    print(f"  {row[1]:5d}  {row[0]}")

print()

suspects = [
    ("Porsche Cayman",       "cayman"),
    ("Porsche Boxster",      "boxster"),
    ("Maserati GranTurismo", "granturismo"),
    ("Maserati GranCabrio",  "grancabrio"),
    ("Maserati Ghibli",      "ghibli"),
    ("Porsche Macan",        "macan"),
    ("Porsche Panamera",     "panamera"),
    ("Porsche Cayenne",      "cayenne"),
    ("Lamborghini",          "lamborghini"),
    ("Ferrari",              "ferrari"),
    ("Porsche 911 Carrera",  "911"),
    ("BMW",                  "competition"),
]
for label, keyword in suspects:
    cur.execute("""
        SELECT model_raw, model_normalized, COUNT(*) AS cnt
        FROM auctions
        WHERE auction_date >= '2025-01-01'
          AND LOWER(model_raw) LIKE ?
          AND model_raw IS NOT NULL
        GROUP BY model_raw, model_normalized
        ORDER BY cnt DESC
        LIMIT 20
    """, (f'%{keyword}%',))
    rows = cur.fetchall()
    if rows:
        total = sum(r[2] for r in rows)
        print(f"--- {label}  ({total} total) ---")
        for r in rows:
            print(f"  {r[2]:4d}  raw={r[0]!r:55s}  norm={r[1]!r}")
        print()

db.close()
