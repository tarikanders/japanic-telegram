#!/usr/bin/env python3
"""
Audit BD : rapport d'incohérences (lecture seule, ne modifie rien).

Usage:
    cd backend && python scripts/audit_db.py

Détecte :
  - year/km aberrants
  - auctions sans année (non liées à une annonce)
  - listings jamais consommés (linked_auction_id NULL)
  - contamination : groupes (model,year,km) sur-partagés = signe d'un même
    listing recopié sur N auctions (le bug principal)
  - faux positifs de normalisation (un même modèle sous plusieurs clés)
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Auction, Listing
from sqlalchemy import func


def section(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def main():
    db = SessionLocal()

    n_auctions = db.query(Auction).count()
    n_listings = db.query(Listing).count()

    section("VOLUMÉTRIE")
    print(f"  auctions : {n_auctions:,}")
    print(f"  listings : {n_listings:,}")

    section("1. ANNÉE / KM ABERRANTS (auctions)")
    bad_year = db.query(Auction).filter(
        Auction.year.isnot(None), (Auction.year < 1980) | (Auction.year > 2026)
    ).count()
    low_km = db.query(Auction).filter(
        Auction.mileage_km.isnot(None), Auction.mileage_km < 100
    ).count()
    high_km = db.query(Auction).filter(Auction.mileage_km > 500_000).count()
    print(f"  année hors [1980,2026] : {bad_year}")
    print(f"  km < 100               : {low_km}")
    print(f"  km > 500 000           : {high_km}")
    for a in db.query(Auction).filter(
        Auction.year.isnot(None), (Auction.year < 1980) | (Auction.year > 2026)
    ).limit(5):
        print(f"    ex: AU#{a.id} {a.lot_number} '{a.model_raw}' year={a.year}")

    section("2. AUCTIONS SANS ANNÉE (non liées à une annonce)")
    no_year = db.query(Auction).filter(Auction.year.is_(None)).count()
    print(f"  auctions year=NULL : {no_year:,}  ({no_year*100//max(1,n_auctions)}%)")
    for a in db.query(Auction).filter(Auction.year.is_(None)).limit(5):
        print(f"    ex: AU#{a.id} {a.lot_number} '{a.model_raw}' price={a.final_price_eur}")

    section("3. LISTINGS JAMAIS CONSOMMÉS (linked_auction_id NULL)")
    orphan = db.query(Listing).filter(Listing.linked_auction_id.is_(None)).count()
    print(f"  listings orphelins : {orphan:,}  ({orphan*100//max(1,n_listings)}%)")
    if orphan == n_listings:
        print("  ⚠ AUCUN listing n'est lié → le lien listing↔auction n'est jamais écrit.")

    section("4. CONTAMINATION : (model,year,km) SUR-PARTAGÉS")
    print("  Un même triplet partagé par N auctions = listing recopié N fois.")
    rows = (
        db.query(
            Auction.model_normalized, Auction.year, Auction.mileage_km,
            func.count().label("n"),
        )
        .filter(Auction.year.isnot(None))
        .group_by(Auction.model_normalized, Auction.year, Auction.mileage_km)
        .having(func.count() > 1)
        .order_by(func.count().desc())
        .limit(12)
        .all()
    )
    n_groups = (
        db.query(Auction.model_normalized, Auction.year, Auction.mileage_km)
        .filter(Auction.year.isnot(None))
        .group_by(Auction.model_normalized, Auction.year, Auction.mileage_km)
        .having(func.count() > 1)
        .count()
    )
    print(f"  groupes sur-partagés : {n_groups:,}")
    for model, year, km, n in rows:
        flag = "  ⚠ suspect" if n > 10 else ""
        print(f"    {n:4d}× {model} | {year} | {km} km{flag}")

    section("5. NORMALISATION : CARDINALITÉ DES MODÈLES")
    n_norm = db.query(func.count(func.distinct(Auction.model_normalized))).scalar()
    print(f"  model_normalized distincts : {n_norm}")
    top = (
        db.query(Auction.model_normalized, func.count())
        .group_by(Auction.model_normalized)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )
    for m, c in top:
        print(f"    {c:5d}  {m}")
    # heuristique faux positifs : modèles quasi-identiques sous clés différentes
    norms = [m for (m,) in db.query(Auction.model_normalized).distinct() if m]
    title_cased_only = [m for m in norms if m and m[0].isupper() and " " not in m]
    print(f"  modèles non aliasés (juste title-cased, ex 'Carera','Glk350') : "
          f"{len(title_cased_only)}  → candidats à enrichir dans normalizer.py")

    section("6. FIABILITÉ DU MATCHING (confidence)")
    # Colonnes ajoutées par migrate_confidence.py — tolère leur absence.
    try:
        n_high = db.query(Auction).filter(Auction.match_confidence == "high").count()
        n_review = db.query(Auction).filter(Auction.match_confidence == "review").count()
        n_none = db.query(Auction).filter(Auction.match_confidence.is_(None)).count()
        print(f"  ✓ high   (fiable)     : {n_high:,}")
        print(f"  ⚠ review (à vérifier) : {n_review:,}")
        print(f"  ∅ non classé / sans candidat : {n_none:,}")
        if n_high == 0 and n_review == 0:
            print("  ⚠ Aucune confiance renseignée → lance scripts/fix_db.py --apply")
    except Exception as e:
        print(f"  (colonnes de confiance absentes — lance migrate_confidence.py) [{e}]")

    section("RÉSUMÉ")
    print(f"  • {no_year:,} auctions sans année (matching impossible/à refaire)")
    print(f"  • {orphan:,} listings non consommés")
    print(f"  • {n_groups:,} triplets (model,year,km) sur-partagés = contamination")
    print(f"  • {len(title_cased_only)} modèles non normalisés (alias manquants)")
    print("\n  → lance le re-linking : python scripts/fix_db.py --dry-run")

    db.close()


if __name__ == "__main__":
    main()
