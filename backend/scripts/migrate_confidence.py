#!/usr/bin/env python3
"""
Migration idempotente :
  1. Ajoute les colonnes auctions.match_confidence et auctions.matched_listing_id
     (no-op si déjà présentes).
  2. Re-normalise model_normalized pour TOUTES les auctions avec le normalizer
     courant → fusionne les doublons d'affichage ('Carera' → 'Porsche 911 Carrera').

Usage:
    cd backend && python scripts/migrate_confidence.py            # dry-run renormalize
    cd backend && python scripts/migrate_confidence.py --apply    # écrit
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import SessionLocal, engine
from models import Auction
from services.normalizer import normalize_model


def _add_columns():
    """ALTER TABLE idempotent (SQLite)."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(auctions)"))}
        if "match_confidence" not in cols:
            conn.execute(text("ALTER TABLE auctions ADD COLUMN match_confidence VARCHAR"))
            print("  ✓ colonne match_confidence ajoutée")
        else:
            print("  • match_confidence déjà présente")
        if "matched_listing_id" not in cols:
            conn.execute(text("ALTER TABLE auctions ADD COLUMN matched_listing_id INTEGER"))
            print("  ✓ colonne matched_listing_id ajoutée")
        else:
            print("  • matched_listing_id déjà présente")


def _renormalize(apply: bool):
    db = SessionLocal()
    auctions = db.query(Auction).all()
    changed = 0
    examples = Counter()
    for au in auctions:
        new = normalize_model(au.model_raw or "")
        if new != (au.model_normalized or ""):
            if changed < 30:
                examples[f"{au.model_normalized!r} → {new!r}"] += 1
            changed += 1
            if apply:
                au.model_normalized = new
    if apply:
        db.commit()

    distinct_before = len({a.model_normalized for a in auctions})
    distinct_after = len({normalize_model(a.model_raw or "") for a in auctions})
    print(f"  modèles re-normalisés : {changed:,} auctions")
    print(f"  clés distinctes : {distinct_before} → {distinct_after} "
          f"({distinct_before - distinct_after:+d} doublons fusionnés)")
    print("  exemples de fusion :")
    for ex, n in examples.most_common(12):
        print(f"    {ex}")
    db.close()


def main():
    apply = "--apply" in sys.argv
    print("=" * 64)
    print(f"MIGRATION — mode : {'APPLY' if apply else 'DRY-RUN'}")
    print("=" * 64)
    print("\n1. Colonnes de fiabilité :")
    _add_columns()  # toujours sûr (idempotent), même en dry-run
    print("\n2. Re-normalisation des modèles :")
    _renormalize(apply)
    if not apply:
        print("\n→ DRY-RUN. Colonnes ajoutées (sûr), re-normalisation NON écrite.")
        print("  Pour appliquer : python scripts/migrate_confidence.py --apply")


if __name__ == "__main__":
    main()
