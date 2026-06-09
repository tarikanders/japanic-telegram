#!/usr/bin/env python3
"""
Migration idempotente — ajout des colonnes Tier 3 sur la table listings :
  - lot_number          VARCHAR  (numéro de lot OCR)
  - lot_ocr_confidence  VARCHAR  (ocr_high / ocr_low / none)
  - report_photo_index  INTEGER  (index de la photo-fiche dans l'album)

Usage:
    cd backend && python scripts/migrate_lot_number.py --dry-run
    cd backend && python scripts/migrate_lot_number.py --apply
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine

COLS = [
    ("lot_number",         "VARCHAR"),
    ("lot_ocr_confidence", "VARCHAR"),
    ("report_photo_index", "INTEGER"),
    ("condition_score",    "VARCHAR"),
]

def main():
    apply = "--apply" in sys.argv
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"migrate_lot_number — {mode}")

    with engine.connect() as conn:
        existing = {r[1] for r in conn.execute(text("PRAGMA table_info(listings)"))}

    to_add = [(n, t) for n, t in COLS if n not in existing]
    already = [n for n, _ in COLS if n in existing]

    for n in already:
        print(f"  • listings.{n} déjà présent")
    for n, t in to_add:
        print(f"  + listings.{n} ({t}) {'→ ALTER TABLE' if apply else '→ à ajouter'}")

    if not to_add:
        print("Rien à faire.")
        return

    if apply:
        with engine.begin() as conn:
            for n, t in to_add:
                conn.execute(text(f"ALTER TABLE listings ADD COLUMN {n} {t}"))
        print("Migration appliquée.")
    else:
        print("\nDRY-RUN — rien écrit. Relancer avec --apply.")

if __name__ == "__main__":
    main()
