#!/usr/bin/env python3
"""
CLI sync enrichi : scanne le canal Telegram et sauvegarde en DB.

Usage:
  python sync.py                    # reprend depuis le dernier checkpoint
  python sync.py --from-scratch     # repart du msg_id=0
  python sync.py --limit 5000       # scanne au plus N messages
  python sync.py --dry-run          # lecture seule, aucune écriture

Enrichissements vs version précédente :
  - Album buffering : collecte les photos de tous les messages d'un même groupe
  - CLI flags : --from-scratch / --limit / --dry-run
  - Erreurs par message loguées (plus de swallow silencieux)
  - checkpoint.records_synced mis à jour à la fin
  - Rapport de confiance (high/review/sans) imprimé en fin de sync
"""
import argparse
import asyncio
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def _extract_photo_id(message) -> str | None:
    """Extrait le photo.id d'un message Telegram (photo seule ou membre d'album)."""
    try:
        if hasattr(message, "media") and message.media:
            if hasattr(message.media, "photo") and message.media.photo:
                return str(message.media.photo.id)
    except Exception:
        pass
    return None


async def main():
    parser = argparse.ArgumentParser(description="Sync Telegram → DB (enrichi)")
    parser.add_argument("--from-scratch", action="store_true",
                        help="Repart du début (checkpoint réinitialisé à 0)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Nombre max de messages à traiter")
    parser.add_argument("--dry-run", action="store_true",
                        help="Lecture seule — n'écrit rien en DB")
    args = parser.parse_args()

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    channel = os.getenv("TELEGRAM_CHANNEL")

    if not all([api_id, api_hash, channel]):
        print("ERREUR: variables manquantes dans .env (TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL)")
        sys.exit(1)

    from telethon import TelegramClient
    from telethon.errors import FloodWaitError
    from database import SessionLocal
    from models import Auction, AuctionStatus, Listing, SyncCheckpoint
    from services.parser import parse_listing, parse_results_message, parse_results_header_date
    from services.normalizer import normalize_model, extract_variant
    from services.linker import find_best_listing
    from datetime import date

    session_file = os.getenv("TELEGRAM_SESSION_FILE", os.path.join(os.path.dirname(__file__), "telegram_session"))
    if not os.path.exists(f"{session_file}.session"):
        print("ERREUR: pas de session. Lance d'abord: python telegram_login.py")
        sys.exit(1)

    client = TelegramClient(session_file, int(api_id), api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("ERREUR: session invalide. Lance d'abord: python telegram_login.py")
        sys.exit(1)

    db = SessionLocal()
    checkpoint = db.query(SyncCheckpoint).first()
    if not checkpoint:
        checkpoint = SyncCheckpoint(last_message_id=0, records_synced=0, status="running")
        db.add(checkpoint)
    else:
        checkpoint.status = "running"

    if args.from_scratch:
        checkpoint.last_message_id = 0
        print("[INFO] --from-scratch : checkpoint réinitialisé à 0")

    if not args.dry_run:
        db.commit()

    min_id = checkpoint.last_message_id
    mode_tag = "DRY-RUN" if args.dry_run else "ÉCRITURE"
    print(f"[{datetime.now():%H:%M:%S}] Connecté. Mode={mode_tag}. Reprise depuis msg_id={min_id}")

    last_msgs = await client.get_messages(channel, limit=1)
    max_id = last_msgs[0].id if last_msgs else 0
    total = max(1, max_id - min_id)
    if args.limit:
        total = min(total, args.limit)
    print(f"[{datetime.now():%H:%M:%S}] ~{total:,} messages à scanner (jusqu'à msg_id={max_id})")
    print("-" * 60)

    synced = 0
    processed = 0
    errors = 0
    max_seen = min_id
    start = time.time()

    # grouped_id → listing.id : pour ajouter les photos des messages suivants d'un album.
    # Albums Telegram = messages consécutifs (2-10) partageant le même grouped_id.
    # On itère oldest→newest (reverse=True), donc le message de caption vient en premier.
    pending_albums: dict[int, int] = {}

    iter_kwargs: dict = {"min_id": min_id, "reverse": True}
    if args.limit:
        iter_kwargs["limit"] = args.limit

    try:
        async for message in client.iter_messages(channel, **iter_kwargs):
            try:
                text = message.text or ""
                msg_id = message.id
                msg_date = message.date.date() if message.date else date.today()
                grouped_id = getattr(message, "grouped_id", None)
                processed += 1

                if msg_id > max_seen:
                    max_seen = msg_id

                # ── Album continuation : message sans texte appartenant à un album connu ──
                if grouped_id and grouped_id in pending_albums and not text.strip():
                    if not args.dry_run:
                        photo_id = _extract_photo_id(message)
                        if photo_id:
                            lst = db.query(Listing).filter_by(id=pending_albums[grouped_id]).first()
                            if lst:
                                current = lst.photo_file_ids or []
                                if photo_id not in current:
                                    lst.photo_file_ids = current + [photo_id]
                    # Message photo-only d'un album : rien d'autre à parser, continuer
                    continue

                # ── Annonce (listing) ─────────────────────────────────────────────────────
                listing_parsed = parse_listing(text)
                if listing_parsed:
                    existing = db.query(Listing).filter_by(telegram_message_id=msg_id).first()
                    if not existing:
                        photo_id = _extract_photo_id(message)
                        photo_ids = [photo_id] if photo_id else []

                        if not args.dry_run:
                            _lst_norm = normalize_model(listing_parsed.model_raw)
                            new_lst = Listing(
                                model_raw=listing_parsed.model_raw,
                                model_normalized=_lst_norm,
                                year=listing_parsed.year,
                                mileage_km=listing_parsed.mileage_km,
                                start_price_eur=listing_parsed.start_price_eur,
                                photo_file_ids=photo_ids,
                                posted_date=msg_date,
                                telegram_message_id=msg_id,
                                raw_text=text,
                                grouped_id=grouped_id,
                                variant=extract_variant(listing_parsed.model_raw, _lst_norm),
                            )
                            db.add(new_lst)
                            db.flush()
                            synced += 1
                            if grouped_id:
                                pending_albums[grouped_id] = new_lst.id
                        else:
                            synced += 1
                            if grouped_id:
                                pending_albums[grouped_id] = -1  # placeholder dry-run

                # ── Résultats (auctions) ──────────────────────────────────────────────────
                header_date = parse_results_header_date(text, msg_date.year if msg_date else None)
                auction_date = header_date or msg_date

                for r in parse_results_message(text):
                    existing = db.query(Auction).filter_by(lot_number=r.lot_number, auction_date=auction_date).first()
                    if not existing:
                        model_norm = normalize_model(r.model_raw)
                        try:
                            status_enum = AuctionStatus(r.status)
                        except ValueError:
                            status_enum = AuctionStatus.not_sold

                        if not args.dry_run:
                            _au_variant = extract_variant(r.model_raw, model_norm)
                            auction = Auction(
                                lot_number=r.lot_number,
                                model_raw=r.model_raw,
                                model_normalized=model_norm,
                                final_price_eur=r.price_eur,
                                status=status_enum,
                                auction_date=auction_date,
                                telegram_message_id=msg_id,
                                raw_text=text,
                                result_line_index=r.line_index,
                                grouped_id=grouped_id,
                                variant=_au_variant,
                            )
                            db.add(auction)
                            db.flush()
                            matching, confidence = find_best_listing(
                                db, model_norm, auction.final_price_eur, auction_date,
                                lot_number=r.lot_number,
                            )
                            if confidence == "high" and matching:
                                auction.year = matching.year if (matching.year and 1980 <= matching.year <= 2026) else None
                                auction.mileage_km = matching.mileage_km
                                auction.start_price_eur = matching.start_price_eur
                                auction.condition_score = matching.condition_score
                                # Le listing a un model_raw plus riche → son variant prime.
                                if matching.variant:
                                    auction.variant = matching.variant
                                auction.match_confidence = "high"
                                auction.matched_listing_id = matching.id
                                matching.linked_auction_id = auction.id
                            elif confidence == "review" and matching:
                                auction.match_confidence = "review"
                                auction.matched_listing_id = matching.id
                        synced += 1

                # Checkpoint + progress ───────────────────────────────────────────────────
                if processed % 500 == 0:
                    if not args.dry_run:
                        db.commit()
                        checkpoint.last_message_id = max_seen
                        db.commit()

                    # Éviction des albums trop anciens (fenêtre de 500 msgs >> 10 photos/album)
                    if len(pending_albums) > 30:
                        to_drop = list(pending_albums.keys())[:-20]
                        for k in to_drop:
                            del pending_albums[k]

                if processed % 200 == 0:
                    elapsed = time.time() - start
                    speed = processed / elapsed if elapsed > 0 else 1
                    done = msg_id - min_id
                    remaining = max(0, total - done)
                    eta_s = int(remaining / speed) if speed > 0 else 0
                    eta_str = f"{eta_s//60}m{eta_s%60:02d}s" if eta_s > 60 else f"{eta_s}s"
                    pct = min(100, done * 100 // total)
                    print(f"[{datetime.now():%H:%M:%S}] {pct:3d}% | {processed:,} msgs | "
                          f"{synced:,} records | {speed:.0f} msg/s | ETA ~{eta_str}")

            except FloodWaitError as e:
                print(f"[{datetime.now():%H:%M:%S}] FloodWait: pause {e.seconds}s...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                errors += 1
                print(f"[{datetime.now():%H:%M:%S}] WARN msg#{msg_id}: {type(e).__name__}: {e}")
                if not args.dry_run:
                    db.rollback()

    finally:
        if not args.dry_run:
            db.commit()
            checkpoint.last_message_id = max_seen
            checkpoint.last_sync_at = datetime.utcnow()
            checkpoint.records_synced = (checkpoint.records_synced or 0) + synced
            checkpoint.status = "idle"
            db.commit()
        await client.disconnect()
        db.close()

    elapsed = time.time() - start
    print("-" * 60)
    print(f"Terminé en {int(elapsed//60)}m{int(elapsed%60):02d}s | {processed:,} messages | "
          f"{synced:,} nouveaux records | {errors} erreurs")
    if args.dry_run:
        print("[DRY-RUN] Aucune écriture effectuée.")

    # ── Rapport final DB ──────────────────────────────────────────────────────────
    db2 = SessionLocal()
    try:
        n_auctions = db2.query(Auction).count()
        n_listings = db2.query(Listing).count()
        try:
            n_high = db2.query(Auction).filter(Auction.match_confidence == "high").count()
            n_review = db2.query(Auction).filter(Auction.match_confidence == "review").count()
            n_none = n_auctions - n_high - n_review
            pct = n_high * 100 // max(1, n_auctions)
            print(f"\nDB: {n_auctions:,} auctions | {n_listings:,} listings")
            print(f"    confidence → ✓ high={n_high:,} ({pct}%)  ⚠ review={n_review:,}  ∅ sans={n_none:,}")
            if pct < 20:
                print("    ↳ %high bas — lance: python scripts/fix_db.py --apply")
        except Exception:
            print(f"\nDB: {n_auctions:,} auctions | {n_listings:,} listings")
    finally:
        db2.close()


if __name__ == "__main__":
    asyncio.run(main())
