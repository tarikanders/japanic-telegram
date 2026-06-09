import asyncio
import logging
import os
import sys
from datetime import date, datetime
from io import BytesIO
from typing import Optional

from sqlalchemy.exc import IntegrityError as _IntegrityError
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Auction, AuctionStatus, Listing, SyncCheckpoint
from services.parser import parse_listing, parse_results_message, parse_results_header_date
from services.normalizer import normalize_model, extract_variant
from services.lot_ocr import extract_fiche_data, pick_report_photo

logger = logging.getLogger(__name__)


async def _process_album(
    client,
    channel: str,
    album_messages: list,
    db: Session,
    synced_count_ref: list,  # [int] — muable pour incrémentation depuis ici
    log_callback=None,
) -> None:
    """
    Traite un album complet (groupe de messages Telegram partageant un grouped_id).

    Si l'album contient un message texte parseable comme annonce :
    1. Télécharge toutes les photos de l'album (frères sans texte inclus).
    2. Tente l'OCR sur la photo-fiche pour extraire le numéro de lot.
    3. Crée le Listing avec lot_number + lot_ocr_confidence renseignés si disponibles.

    Messages résultats (Today's results…) : traités séparément via le flux principal.
    """
    if not album_messages:
        return

    # Identifier le message texte (celui qui a du texte parseable)
    listing_msg = None
    listing_parsed = None
    for msg in album_messages:
        text = msg.text or ""
        parsed = parse_listing(text)
        if parsed:
            listing_msg = msg
            listing_parsed = parsed
            break

    if not listing_parsed or not listing_msg:
        return  # pas une annonce (ou déjà ignoré par le flux principal)

    msg_id = listing_msg.id
    msg_date = listing_msg.date.date() if listing_msg.date else date.today()
    text = listing_msg.text or ""
    grouped_id = getattr(listing_msg, "grouped_id", None)

    existing = db.query(Listing).filter_by(telegram_message_id=msg_id).first()
    if existing:
        return  # déjà en DB

    # ── Télécharger uniquement la dernière photo (fiche-rapport) ─────────────
    # La fiche est TOUJOURS la dernière photo de l'album (confirmé par spike 20 albums).
    # On ne télécharge que celle-là : 1 appel Telegram au lieu de 7 → 6× plus rapide.
    fiche_bytes: Optional[bytes] = None
    report_photo_idx: Optional[int] = None

    sorted_msgs = sorted(album_messages, key=lambda m: m.id)
    photo_msgs = [m for m in sorted_msgs if m.media]
    if photo_msgs:
        report_photo_idx = len(photo_msgs) - 1  # index dans la séquence de photos
        try:
            buf = BytesIO()
            await photo_msgs[-1].download_media(file=buf)
            data = buf.getvalue()
            if data:
                fiche_bytes = data
        except Exception as e:
            logger.debug(f"download_media fiche msg#{photo_msgs[-1].id}: {e}")

    # ── OCR : extraire le numéro de lot + note d'état (un seul appel Vision) ──
    lot_number: Optional[str] = None
    lot_ocr_confidence = "none"
    condition_score: Optional[str] = None

    if fiche_bytes:
        lot_number, lot_ocr_confidence, condition_score = extract_fiche_data(fiche_bytes)

    if lot_number and log_callback:
        score_str = f" score={condition_score}" if condition_score else ""
        await log_callback(
            f"  OCR lot={lot_number} ({lot_ocr_confidence}){score_str} ← listing #{msg_id}"
        )

    # ── Conserver les photo_file_ids du message texte (compat existante) ──────
    photo_ids = []
    if hasattr(listing_msg, "media") and listing_msg.media:
        try:
            photo_ids = (
                [str(listing_msg.media.photo.id)]
                if hasattr(listing_msg.media, "photo") and listing_msg.media.photo
                else []
            )
        except Exception:
            pass

    _model_norm = normalize_model(listing_parsed.model_raw)
    listing = Listing(
        model_raw=listing_parsed.model_raw,
        model_normalized=_model_norm,
        year=listing_parsed.year,
        mileage_km=listing_parsed.mileage_km,
        start_price_eur=listing_parsed.start_price_eur,
        photo_file_ids=photo_ids,
        posted_date=msg_date,
        telegram_message_id=msg_id,
        raw_text=text,
        grouped_id=grouped_id,
        # Tier 3
        lot_number=lot_number,
        lot_ocr_confidence=lot_ocr_confidence,
        report_photo_index=report_photo_idx,
        condition_score=condition_score,
        variant=extract_variant(listing_parsed.model_raw, _model_norm),
    )
    try:
        sp = db.begin_nested()
        db.add(listing)
        db.flush()
        sp.commit()
        synced_count_ref[0] += 1
    except _IntegrityError:
        sp.rollback()  # listing already in DB (duplicate telegram_message_id), skip


async def run_sync(log_callback=None):
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    channel = os.getenv("TELEGRAM_CHANNEL")

    if not all([api_id, api_hash, channel]):
        msg = "Missing Telegram credentials in environment variables"
        logger.error(msg)
        if log_callback:
            await log_callback(msg)
        return {"error": msg}

    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError
    except ImportError:
        msg = "telethon not installed"
        logger.error(msg)
        if log_callback:
            await log_callback(msg)
        return {"error": msg}

    db = SessionLocal()
    try:
        checkpoint = db.query(SyncCheckpoint).first()
        if not checkpoint:
            checkpoint = SyncCheckpoint(last_message_id=0, records_synced=0, status="running")
            db.add(checkpoint)
        else:
            checkpoint.status = "running"
            checkpoint.error_message = None
        db.commit()

        _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        session_name = os.getenv("TELEGRAM_SESSION_FILE", "telegram_session")
        if os.path.isabs(session_name):
            session_file = session_name
        else:
            session_file = os.path.join(_backend_dir, session_name)

        if not os.path.exists(f"{session_file}.session"):
            msg = "Not authorized. Run `python telegram_login.py` first to create a session file."
            logger.error(msg)
            if log_callback:
                await log_callback(msg)
            checkpoint.status = "error"
            checkpoint.error_message = msg
            db.commit()
            return {"error": msg}

        client = TelegramClient(session_file, int(api_id), api_hash)

        try:
            await client.connect()
            authorized = await client.is_user_authorized()
        except (EOFError, OSError) as e:
            authorized = False

        if not authorized:
            msg = "Not authorized. Run `python telegram_login.py` first to create a session."
            logger.error(msg)
            if log_callback:
                await log_callback(msg)
            checkpoint.status = "error"
            checkpoint.error_message = msg
            db.commit()
            try:
                await client.disconnect()
            except Exception:
                pass
            return {"error": msg}

        if log_callback:
            await log_callback(
                f"Connected to Telegram. Last checkpoint: message_id={checkpoint.last_message_id}"
            )

        synced_count_ref = [0]   # liste muable pour passage par référence dans _process_album
        processed_count = 0
        min_id = checkpoint.last_message_id
        max_seen_id = min_id

        # ── Buffer d'album ────────────────────────────────────────────────────
        # Les membres d'un album arrivent en ordre croissant (reverse=True).
        # On les accumule dans current_album_buf jusqu'au changement de grouped_id.
        current_grouped_id: Optional[int] = None
        current_album_buf: list = []

        async def _flush_album():
            """Vide le buffer courant → _process_album."""
            if current_album_buf:
                await _process_album(
                    client, channel, current_album_buf,
                    db, synced_count_ref, log_callback,
                )

        async for message in client.iter_messages(channel, min_id=min_id, reverse=True):
            try:
                text = message.text or ""
                msg_id = message.id
                msg_date = message.date.date() if message.date else date.today()

                processed_count += 1
                if processed_count % 200 == 0 and log_callback:
                    await log_callback(
                        f"Scanning... {processed_count} messages read, "
                        f"{synced_count_ref[0]} records saved (msg_id={msg_id})"
                    )

                if msg_id > max_seen_id:
                    max_seen_id = msg_id

                # ── Gestion de l'album ────────────────────────────────────────
                msg_grouped_id = getattr(message, "grouped_id", None)

                if msg_grouped_id is not None:
                    # Message membre d'un album
                    if msg_grouped_id != current_grouped_id:
                        # Nouvel album : vider le buffer précédent
                        await _flush_album()
                        current_grouped_id = msg_grouped_id
                        current_album_buf = [message]
                    else:
                        current_album_buf.append(message)
                    # Ne pas traiter ce message individuellement (le traitement
                    # se fait à la fermeture de l'album via _flush_album)
                    # SAUF pour les messages résultats qui n'ont pas de grouped_id
                    # → continuer normalement ci-dessous.
                else:
                    # Message sans album → vider tout buffer en attente d'abord
                    if current_album_buf:
                        await _flush_album()
                        current_grouped_id = None
                        current_album_buf = []

                    # ── Annonce individuelle (sans album) ─────────────────────
                    listing_parsed = parse_listing(text)
                    if listing_parsed:
                        existing = db.query(Listing).filter_by(telegram_message_id=msg_id).first()
                        if not existing:
                            photo_ids = []
                            grouped_id = getattr(message, "grouped_id", None)
                            if hasattr(message, "media") and message.media:
                                try:
                                    photo_ids = (
                                        [str(message.media.photo.id)]
                                        if hasattr(message.media, "photo") and message.media.photo
                                        else []
                                    )
                                except Exception:
                                    pass

                            listing = Listing(
                                model_raw=listing_parsed.model_raw,
                                model_normalized=normalize_model(listing_parsed.model_raw),
                                year=listing_parsed.year,
                                mileage_km=listing_parsed.mileage_km,
                                start_price_eur=listing_parsed.start_price_eur,
                                photo_file_ids=photo_ids,
                                posted_date=msg_date,
                                telegram_message_id=msg_id,
                                raw_text=text,
                                grouped_id=grouped_id,
                                # lot non disponible (pas d'album → pas de fiche)
                                lot_number=None,
                                lot_ocr_confidence="none",
                                report_photo_index=None,
                            )
                            try:
                                _sp = db.begin_nested()
                                db.add(listing)
                                db.flush()
                                _sp.commit()
                                synced_count_ref[0] += 1
                            except _IntegrityError:
                                _sp.rollback()

                # ── Résultats (auctions) ──────────────────────────────────────
                # Les résultats n'ont jamais de grouped_id — traiter dans les deux branches.
                header_date = parse_results_header_date(
                    text, msg_date.year if msg_date else None
                )
                auction_date = header_date or msg_date

                results = parse_results_message(text)
                for r in results:
                    existing = db.query(Auction).filter_by(
                        lot_number=r.lot_number, auction_date=auction_date
                    ).first()
                    if not existing:
                        model_norm = normalize_model(r.model_raw)
                        try:
                            status_enum = AuctionStatus(r.status)
                        except ValueError:
                            status_enum = AuctionStatus.not_sold

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
                            grouped_id=getattr(message, "grouped_id", None),
                            # Variant depuis le model_raw du message résultat (souvent court).
                            # Sera écrasé par celui du listing si le listing est plus riche.
                            variant=extract_variant(r.model_raw, model_norm),
                        )

                        # Matching confiance-aware via linker (inclut le pont lot si disponible)
                        from services.linker import find_best_listing
                        matching, confidence = find_best_listing(
                            db, model_norm, auction.final_price_eur, auction_date,
                            lot_number=r.lot_number,
                        )
                        if confidence == "high" and matching:
                            auction.year = (
                                matching.year
                                if (matching.year and 1980 <= matching.year <= 2026)
                                else None
                            )
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

                        try:
                            _sp = db.begin_nested()
                            db.add(auction)
                            db.flush()
                            _sp.commit()
                            synced_count_ref[0] += 1
                        except _IntegrityError:
                            _sp.rollback()

                if processed_count % 100 == 0 and processed_count > 0:
                    db.commit()
                    checkpoint.last_message_id = max_seen_id
                    db.commit()
                    if log_callback:
                        await log_callback(
                            f"Checkpoint saved: {processed_count} msgs, "
                            f"{synced_count_ref[0]} records (msg_id={max_seen_id})"
                        )

            except FloodWaitError as e:
                wait_msg = f"FloodWait: sleeping {e.seconds}s"
                logger.warning(wait_msg)
                if log_callback:
                    await log_callback(wait_msg)
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error processing message {message.id}: {e}")
                db.rollback()

        # Vider le dernier album en buffer hors de la boucle
        await _flush_album()

        db.commit()

        checkpoint.last_message_id = max_seen_id
        checkpoint.last_sync_at = datetime.utcnow()
        checkpoint.status = "idle"
        db.commit()

        await client.disconnect()

        result = {"synced": synced_count_ref[0], "last_message_id": max_seen_id}
        if log_callback:
            await log_callback(f"Sync complete: {synced_count_ref[0]} new records")
        return result

    except Exception as e:
        logger.exception("Sync failed")
        if checkpoint:
            checkpoint.status = "error"
            checkpoint.error_message = str(e)
            # Sauvegarder la position atteinte pour permettre la reprise
            try:
                checkpoint.last_message_id = max_seen_id
            except NameError:
                pass  # crash avant le démarrage de la boucle — checkpoint inchangé
            db.commit()
        if log_callback:
            await log_callback(f"ERROR: {e}")
        return {"error": str(e)}
    finally:
        db.close()
