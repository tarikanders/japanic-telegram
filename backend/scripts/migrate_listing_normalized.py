#!/usr/bin/env python3
"""
Migration idempotente :
  1. Ajoute la colonne listings.model_normalized (no-op si déjà présente).
  2. Backfille model_normalized = normalize_model(model_raw) pour toutes les annonces.
  3. Crée un index ix_listings_model_normalized après le backfill.

Doit être exécuté AVANT fix_db.py --apply pour que le linker compare
normalisé↔normalisé.

Usage:
    cd backend && python scripts/migrate_listing_normalized.py            # dry-run
    cd backend && python scripts/migrate_listing_normalized.py --apply    # écrit
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import SessionLocal, engine
from models import Listing
from services.normalizer import normalize_model


def _add_column():
    """ALTER TABLE idempotent (SQLite)."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(listings)"))}
        if "model_normalized" not in cols:
            conn.execute(text("ALTER TABLE listings ADD COLUMN model_normalized VARCHAR"))
            print("  ✓ colonne model_normalized ajoutée")
        else:
            print("  • model_normalized déjà présente")


def _backfill(apply: bool):
    db = SessionLocal()
    listings = db.query(Listing).all()
    changed = 0
    blank = 0
    examples: Counter = Counter()

    for lst in listings:
        new = normalize_model(lst.model_raw or "")
        if not new:
            blank += 1
        if new != (lst.model_normalized or ""):
            if len(examples) < 30:
                examples[f"{lst.model_normalized!r} → {new!r}"] += 1
            changed += 1
            if apply:
                lst.model_normalized = new

    if apply:
        db.commit()

    distinct_raw = len({lst.model_raw for lst in listings})
    distinct_norm_before = len({lst.model_normalized for lst in listings if lst.model_normalized})
    distinct_norm_after = len({normalize_model(lst.model_raw or "") for lst in listings})

    print(f"  listings totaux      : {len(listings):,}")
    print(f"  model_raw distincts  : {distinct_raw:,}")
    print(f"  normalisés avant     : {distinct_norm_before:,}")
    print(f"  normalisés après     : {distinct_norm_after:,}  "
          f"({distinct_raw - distinct_norm_after:+d} doublons fusionnés)")
    print(f"  rows à backfiller    : {changed:,}  (blank raw: {blank})")
    print("  exemples :")
    for ex, _ in list(examples.most_common(12)):
        print(f"    {ex}")

    db.close()


def _create_index():
    """Index APRÈS backfill pour ne pas reécrire à chaque UPDATE."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_listings_model_normalized "
            "ON listings(model_normalized)"
        ))
    print("  ✓ index ix_listings_model_normalized créé (ou déjà présent)")


def main():
    apply = "--apply" in sys.argv
    print("=" * 64)
    print(f"MIGRATION listings.model_normalized — mode : {'APPLY' if apply else 'DRY-RUN'}")
    print("=" * 64)

    print("\n1. Colonne model_normalized :")
    _add_column()  # toujours sûr (idempotent), même en dry-run

    print("\n2. Backfill normalize_model(model_raw) :")
    _backfill(apply)

    print("\n3. Index :")
    if apply:
        _create_index()
    else:
        print("  (index créé uniquement en mode --apply)")

    if not apply:
        print("\n→ DRY-RUN. Colonne ajoutée (sûr), backfill et index NON écrits.")
        print("  Pour appliquer : python scripts/migrate_listing_normalized.py --apply")


if __name__ == "__main__":
    main()
