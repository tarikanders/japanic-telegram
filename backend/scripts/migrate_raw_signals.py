#!/usr/bin/env python3
"""
Migration idempotente — Tier 2 : colonnes de signaux bruts.

Tables modifiées :
  auctions : raw_text, result_line_index, grouped_id
  listings : raw_text, grouped_id

Ces colonnes sont NULL sur les données existantes ; elles se rempliront lors
du prochain re-scrape enrichi (scraper.py mis à jour).

Usage:
    cd backend && python scripts/migrate_raw_signals.py            # dry-run (inspecte)
    cd backend && python scripts/migrate_raw_signals.py --apply    # écrit
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine


_AUCTION_COLS = [
    ("raw_text",           "TEXT"),
    ("result_line_index",  "INTEGER"),
    ("grouped_id",         "BIGINT"),
]

_LISTING_COLS = [
    ("raw_text",   "TEXT"),
    ("grouped_id", "BIGINT"),
]


def _add_columns(table: str, cols: list[tuple[str, str]]):
    with engine.begin() as conn:
        existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
        for col_name, col_type in cols:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                print(f"  ✓ {table}.{col_name} ajouté")
            else:
                print(f"  • {table}.{col_name} déjà présent")


def main():
    apply = "--apply" in sys.argv
    print("=" * 64)
    print(f"MIGRATION raw_signals — mode : {'APPLY' if apply else 'DRY-RUN'}")
    print("=" * 64)

    if apply:
        print("\nauctions :")
        _add_columns("auctions", _AUCTION_COLS)
        print("\nlistings :")
        _add_columns("listings", _LISTING_COLS)
        print("\n✓ Migration appliquée. Les colonnes sont NULL sur les données")
        print("  existantes ; elles se rempliront lors du re-scrape enrichi.")
    else:
        print("\nColonnes à ajouter :")
        with engine.connect() as conn:
            for table, cols in [("auctions", _AUCTION_COLS), ("listings", _LISTING_COLS)]:
                existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
                for col_name, col_type in cols:
                    status = "déjà présente" if col_name in existing else "À AJOUTER"
                    print(f"  {table}.{col_name} ({col_type}) — {status}")
        print("\n→ DRY-RUN. Rien écrit.")
        print("  Pour appliquer : python scripts/migrate_raw_signals.py --apply")


if __name__ == "__main__":
    main()
