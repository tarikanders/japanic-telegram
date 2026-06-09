#!/usr/bin/env python3
"""
Correction BD : ré-associe les auctions à leur meilleur listing (1:1) via
le linker fuzzy, et NETTOIE les year/km fabriqués par l'ancien matching.

Usage:
    cd backend && python scripts/fix_db.py --dry-run   # n'écrit rien, montre le diff
    cd backend && python scripts/fix_db.py --apply      # backup + applique

Sécurités :
  - --apply crée d'abord un backup horodaté du fichier .db
  - --apply réinitialise d'abord tous les linked_auction_id (re-link global propre)
  - --dry-run par défaut si aucun flag fourni
  - affiche stats avant/après pour validation manuelle
"""
import os
import sys
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine
from models import Auction, Listing
from services.linker import link_auctions
from sqlalchemy import func


def _stats_snapshot(db):
    n = db.query(Auction).count()
    with_year = db.query(Auction).filter(Auction.year.isnot(None)).count()
    groups = (
        db.query(Auction.model_normalized, Auction.year, Auction.mileage_km)
        .filter(Auction.year.isnot(None))
        .group_by(Auction.model_normalized, Auction.year, Auction.mileage_km)
        .having(func.count() > 1)
        .count()
    )
    return {"total": n, "with_year": with_year, "overshared_groups": groups}


def _backup_db():
    db_path = engine.url.database
    if not db_path or not os.path.exists(db_path):
        print(f"  ⚠ chemin DB introuvable ({db_path}) — backup ignoré")
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = f"{db_path}.backup_{stamp}"
    shutil.copy2(db_path, dst)
    print(f"  ✓ backup : {dst}")
    return dst


def main():
    apply = "--apply" in sys.argv
    dry_run = not apply  # dry-run par défaut

    import os as _os
    mode = "APPLY (ecriture)" if apply else "DRY-RUN (aucune ecriture)"
    data_floor = _os.getenv("DATA_MIN_DATE", "2025-01-01") or "TOUT l'historique"
    print("=" * 64)
    print(f"FIX DB - mode : {mode}  |  DATA_MIN_DATE={data_floor}")
    print("=" * 64)

    db = SessionLocal()

    before = _stats_snapshot(db)
    print("\nAVANT :")
    print(f"  auctions={before['total']:,}  avec_annee={before['with_year']:,}  "
          f"triplets_sur-partages={before['overshared_groups']:,}")

    if apply:
        print("\nBackup :")
        _backup_db()
        # Réinitialise TOUS les liens pour un re-link global propre.
        # Sans ce reset, link_auctions ne voit que les listings libres (linked_auction_id IS NULL)
        # et ignore les listings déjà consommés → résultat partiel au lieu de global.
        n_reset = db.query(Listing).filter(Listing.linked_auction_id.isnot(None)).update(
            {"linked_auction_id": None}, synchronize_session=False
        )
        db.commit()
        print(f"\nRéinitialisation : {n_reset:,} listings déliés → pool complet disponible")

    print("\nRe-linking en cours...")
    stats = link_auctions(db, dry_run=dry_run, verbose=True)

    print("\nRESULTAT du matching :")
    print(f"  auctions traitees      : {stats['auctions_total']:,}")
    print(f"  OK FIABLES (year ecrit): {stats['linked_high']:,}")
    print(f"    dont pont-lot (T3)   : {stats.get('linked_by_lot', 0):,}")
    print(f"    dont positionnel(T2) : {stats.get('linked_positional', 0):,}")
    print(f"  ?? A VERIFIER (ambigu) : {stats['needs_review']:,}  (year laisse NULL)")
    print(f"  -- sans candidat       : {stats['unmatched']:,}")
    print(f"  annees changees        : {stats['year_changed']:,}")
    print(f"  annees remises NULL    : {stats['year_cleared']:,}  (etaient fabriquees)")

    print("\nExemples :")
    for ex in stats["examples"]:
        print(f"  {ex}")

    if apply:
        after = _stats_snapshot(db)
        print("\nAPRES :")
        print(f"  auctions={after['total']:,}  avec_annee={after['with_year']:,}  "
              f"triplets_sur-partages={after['overshared_groups']:,}")
        delta = before["overshared_groups"] - after["overshared_groups"]
        print(f"\n  OK contamination reduite : {delta:,} triplets sur-partages en moins")
    else:
        print("\n-> DRY-RUN termine. Rien ecrit.")
        print("  Si le diff te convient : python scripts/fix_db.py --apply")

    db.close()


if __name__ == "__main__":
    main()
