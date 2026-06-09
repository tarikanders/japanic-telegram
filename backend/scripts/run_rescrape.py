#!/usr/bin/env python3
"""
Script terminal pour le re-scrape complet avec gestion de crash/reprise.

Usage depuis backend/ :
    python scripts/run_rescrape.py             # reprend depuis le dernier checkpoint
    python scripts/run_rescrape.py --fresh     # backup + wipe + repart de 0
    python scripts/run_rescrape.py --status    # affiche l'état actuel sans lancer

Crash recovery :
    Si le script est interrompu (Ctrl+C, crash réseau, etc.), relancer la même commande
    reprendra automatiquement depuis le dernier checkpoint sauvegardé (toutes les 100 msgs).
"""
import asyncio
import argparse
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_root, ".env"))


def _get_status(db):
    from models import SyncCheckpoint, Listing, Auction
    checkpoint = db.query(SyncCheckpoint).first()
    listing_count = db.query(Listing).count()
    auction_count = db.query(Auction).count()
    last_id = checkpoint.last_message_id if checkpoint else 0
    status = checkpoint.status if checkpoint else "no checkpoint"
    return listing_count, auction_count, last_id, status


async def main(fresh: bool, status_only: bool, yes: bool = False):
    from database import SessionLocal, engine
    from sqlalchemy import text

    db = SessionLocal()
    listing_count, auction_count, last_id, ckpt_status = _get_status(db)

    print(f"\n{'='*60}")
    print(f"  Listings en DB      : {listing_count:,}")
    print(f"  Auctions en DB      : {auction_count:,}")
    print(f"  Checkpoint msg_id   : {last_id:,}")
    print(f"  Statut checkpoint   : {ckpt_status}")
    print(f"{'='*60}\n")

    if status_only:
        db.close()
        return

    if fresh:
        print("Mode : FRESH RE-SCRAPE (efface tout + repart de 0)")
        if not yes:
            confirm = input(
                f"Efface {listing_count:,} listings + {auction_count:,} auctions. Un backup sera créé.\nConfirmer ? [y/N] "
            ).strip().lower()
            if confirm != "y":
                print("Annulé.")
                db.close()
                return

        db_path = engine.url.database
        if db_path and os.path.exists(db_path):
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            bak = f"{db_path}.backup_{stamp}"
            shutil.copy2(db_path, bak)
            print(f"Backup créé : {os.path.basename(bak)}")

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM listings"))
            conn.execute(text("DELETE FROM auctions"))
            conn.execute(text("DELETE FROM sync_checkpoints"))
        db.close()
        db = SessionLocal()
        print("Tables vidées. Démarrage depuis msg_id=0...\n")

    elif last_id > 0:
        print(f"Mode : REPRISE depuis msg_id={last_id:,}")
        print(f"({listing_count:,} listings déjà en DB — seules les nouvelles données seront ajoutées)\n")
    else:
        print("Mode : DÉMARRAGE INITIAL depuis msg_id=0\n")

    db.close()

    from services.scraper import run_sync

    async def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)

    try:
        result = await run_sync(log_callback=log)
    except KeyboardInterrupt:
        print("\n\nInterrompu par Ctrl+C — checkpoint sauvegardé.")
        print("Relancer `python scripts/run_rescrape.py` pour reprendre.")
        sys.exit(0)

    if "error" in result:
        print(f"\nERREUR: {result['error']}")
        print("Relancer `python scripts/run_rescrape.py` pour reprendre depuis le checkpoint.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Terminé : {result.get('synced', 0):,} nouveaux records")
    print(f"  Dernier msg_id : {result.get('last_message_id', 0):,}")
    print(f"{'='*60}")
    print("\nProchain step : lancer le re-link")
    print("  python scripts/fix_db.py --apply")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-scrape complet avec reprise sur crash")
    parser.add_argument("--fresh", action="store_true",
                        help="Efface la DB et repart de 0 (backup auto créé)")
    parser.add_argument("--status", action="store_true",
                        help="Affiche l'état sans lancer le scrape")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip la confirmation interactive (pour usage script/CI)")
    args = parser.parse_args()

    asyncio.run(main(fresh=args.fresh, status_only=args.status, yes=args.yes))
