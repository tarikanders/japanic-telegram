#!/usr/bin/env python3
"""
Migration idempotente — Tier 3 (condition_score + variant) :
  1. Ajoute auctions.condition_score   VARCHAR  (note d'état propagée depuis listings)
  2. Ajoute auctions.variant           VARCHAR  (finition propagée depuis listings)
  3. Ajoute listings.variant           VARCHAR  (finition extraite du model_raw)
  4. Backfill listings.variant via normalizer.extract_variant (best-effort).

Sans ces colonnes, link_auctions (qui écrit au.condition_score / au.variant
et lit best.variant) échoue en OperationalError → year/km impossibles à propager.

Usage:
    cd backend && python scripts/migrate_auction_tier3.py            # dry-run
    cd backend && python scripts/migrate_auction_tier3.py --apply    # écrit
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import SessionLocal, engine
from models import Listing
from services.normalizer import normalize_model, extract_variant


# Colonnes à ajouter par table
_AUCTION_COLS = [
    ("condition_score", "VARCHAR"),
    ("variant",         "VARCHAR"),
]
_LISTING_COLS = [
    ("variant", "VARCHAR"),
]


def _add_columns(apply: bool):
    """ALTER TABLE idempotent (SQLite — ne fait rien si la colonne existe déjà)."""
    with engine.begin() as conn:
        acols = {r[1] for r in conn.execute(text("PRAGMA table_info(auctions)"))}
        for name, typ in _AUCTION_COLS:
            if name not in acols:
                if apply:
                    conn.execute(text(f"ALTER TABLE auctions ADD COLUMN {name} {typ}"))
                print(f"  {'OK ajoutee' if apply else '-> manquante, sera ajoutee'} : auctions.{name}")
            else:
                print(f"  . deja presente : auctions.{name}")

        lcols = {r[1] for r in conn.execute(text("PRAGMA table_info(listings)"))}
        for name, typ in _LISTING_COLS:
            if name not in lcols:
                if apply:
                    conn.execute(text(f"ALTER TABLE listings ADD COLUMN {name} {typ}"))
                print(f"  {'OK ajoutee' if apply else '-> manquante, sera ajoutee'} : listings.{name}")
            else:
                print(f"  . deja presente : listings.{name}")


def _backfill_listing_variant(apply: bool):
    """
    Remplit listings.variant là où il est NULL, via extract_variant(model_raw, model_normalized).
    Best-effort : si model_raw est None ou si aucune règle ne matche, reste NULL.
    """
    db = SessionLocal()
    listings = db.query(Listing).filter(Listing.variant.is_(None)).all()
    filled = 0
    for lst in listings:
        raw = lst.model_raw or ""
        norm = lst.model_normalized or normalize_model(raw)
        v = extract_variant(raw, norm)
        if v:
            filled += 1
            if apply:
                lst.variant = v
    if apply:
        db.commit()
    db.close()
    print(f"  {'OK remplis' if apply else '-> a remplir'} : {filled:,} listings.variant (sur {len(listings):,} NULL)")


def main():
    apply = "--apply" in sys.argv
    print("=" * 64)
    print(f"MIGRATION Tier 3 — mode : {'APPLY' if apply else 'DRY-RUN'}")
    print("=" * 64)

    print("\n1. Colonnes :")
    _add_columns(apply)

    print("\n2. Backfill listings.variant :")
    _backfill_listing_variant(apply)

    if not apply:
        print("\n→ DRY-RUN. Rien écrit.")
        print("  Pour appliquer : python scripts/migrate_auction_tier3.py --apply")
    else:
        print("\nOK Migration appliquee.")
        print("  Étape suivante : python scripts/fix_db.py --dry-run")


if __name__ == "__main__":
    main()
