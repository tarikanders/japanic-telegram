#!/usr/bin/env python3
"""
Resync complet + re-link.

1. Remet SyncCheckpoint.last_message_id a 0 (ou a --from-id N)
   => le prochain sync Telegram traite TOUS les messages depuis le debut.
   Les listings et auctions deja en DB sont proteges par deduplication
   (telegram_message_id UNIQUE pour listings ; lot_number+date pour auctions).

2. Affiche les stats de listings et auctions avant/apres pour mesurer le gain.

Usage:
    cd backend && python scripts/resync_and_relink.py --dry-run
    cd backend && python scripts/resync_and_relink.py --apply
    cd backend && python scripts/resync_and_relink.py --apply --from-id 88700
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import SyncCheckpoint, Listing, Auction


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",   action="store_true", help="Applique le reset")
    parser.add_argument("--from-id", type=int, default=0,
                        help="Repart depuis ce message_id (defaut: 0 = debut du canal)")
    args = parser.parse_args()
    dry_run = not args.apply

    db = SessionLocal()

    ck = db.query(SyncCheckpoint).first()
    current_id = ck.last_message_id if ck else None

    n_listings = db.query(Listing).count()
    n_au       = db.query(Auction).count()
    n_au_null  = db.query(Auction).filter(
        Auction.auction_date >= "2025-01-01",
        Auction.year.is_(None),
        Auction.match_confidence.is_(None),
    ).count()

    print("=" * 64)
    print(f"RESYNC - mode : {'DRY-RUN' if dry_run else 'APPLY'}")
    print("=" * 64)
    print(f"  SyncCheckpoint.last_message_id actuel : {current_id}")
    print(f"  Repart depuis                         : {args.from_id}")
    print(f"  Listings en DB                        : {n_listings:,}")
    print(f"  Auctions en DB                        : {n_au:,}")
    print(f"  Auctions 2025+ sans year/confidence   : {n_au_null:,}")
    print()

    if dry_run:
        print("DRY-RUN : rien n'a ete modifie.")
        print()
        print("Pour appliquer :")
        print("  python scripts/resync_and_relink.py --apply")
        print()
        print("Ensuite :")
        print("  1. Declencher le sync Telegram (endpoint /admin/sync ou relancer le serveur)")
        print("  2. Attendre la fin du sync")
        print("  3. python scripts/fix_db.py --apply")
    else:
        if ck:
            ck.last_message_id = args.from_id
        else:
            db.add(SyncCheckpoint(last_message_id=args.from_id))
        db.commit()
        print(f"OK SyncCheckpoint reset a {args.from_id}")
        print()
        print("Etapes suivantes :")
        print("  1. Declencher le sync Telegram : appel /admin/sync ou restart serveur Cloud Run")
        print("  2. Attendre la fin du sync (les nouveaux listings/auctions seront ajoutes)")
        print("  3. Relancer le re-link :")
        print("     python scripts/fix_db.py --apply")

    db.close()


if __name__ == "__main__":
    main()
