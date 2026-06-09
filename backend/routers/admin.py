import asyncio
import logging
import os
import secrets
import time
from datetime import datetime
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import get_db
from models import Auction, Listing, SyncCheckpoint
from routers.auth import verify_token

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

_sync_logs: list[str] = []
_sync_running = False
_ws_clients: list[WebSocket] = []

# Short-lived one-time tickets for WebSocket auth (avoids JWT in query params / server logs)
_ws_tickets: dict[str, float] = {}  # ticket → expiry timestamp
_TICKET_TTL = 60  # seconds


@router.get("/status")
def get_status(db: Session = Depends(get_db), _=Depends(verify_token)):
    checkpoint = db.query(SyncCheckpoint).first()
    total_auctions = db.query(Auction).count()
    total_listings = db.query(Listing).count()

    return {
        "last_sync_at": checkpoint.last_sync_at.isoformat() if checkpoint and checkpoint.last_sync_at else None,
        "last_message_id": checkpoint.last_message_id if checkpoint else 0,
        "records_synced_total": total_auctions + total_listings,
        "sync_status": checkpoint.status if checkpoint else "idle",
        "error_message": checkpoint.error_message if checkpoint else None,
        "total_auctions": total_auctions,
        "total_listings": total_listings,
    }


@router.post("/logs/ticket")
def issue_ws_ticket(_=Depends(verify_token)):
    """Issue a one-time ticket valid for 60s to authenticate the WebSocket connection."""
    now = time.time()
    # Prune expired tickets
    expired = [t for t, exp in _ws_tickets.items() if now > exp]
    for t in expired:
        del _ws_tickets[t]

    ticket = secrets.token_urlsafe(32)
    _ws_tickets[ticket] = now + _TICKET_TTL
    return {"ticket": ticket, "expires_in": _TICKET_TTL}


@router.post("/sync")
async def force_sync(_=Depends(verify_token)):
    global _sync_running
    if _sync_running:
        return {"message": "Sync already running"}

    _sync_running = True
    _sync_logs.clear()

    async def broadcast(msg: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        _sync_logs.append(line)
        dead = []
        for ws in _ws_clients:
            try:
                await ws.send_text(line)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _ws_clients.remove(ws)

    async def do_sync():
        global _sync_running
        try:
            from services.scraper import run_sync
            await run_sync(log_callback=broadcast)
        except Exception as e:
            await broadcast(f"ERROR: {e}")
        finally:
            _sync_running = False

    asyncio.create_task(do_sync())
    return {"message": "Sync started"}


@router.post("/fresh-rescrape")
async def fresh_rescrape(
    force: bool = False,
    db: Session = Depends(get_db),
    _=Depends(verify_token),
):
    """
    Efface toutes les données existantes et relance un scrape complet depuis msg_id=0.

    Séquence :
      1. Backup horodaté du fichier .db (GCS FUSE)
      2. DELETE FROM auctions / listings / sync_checkpoints
      3. Lance run_sync(log_callback=...) en background

    Si la DB contient déjà des données (re-scrape interrompu), renvoie une erreur 409
    sauf si force=true — utiliser /resume-rescrape pour reprendre sans perte.
    """
    global _sync_running
    if _sync_running:
        return {"message": "Sync already running — wait for it to finish"}

    if not force:
        listing_count = db.query(Listing).count()
        checkpoint = db.query(SyncCheckpoint).first()
        if listing_count > 0 and checkpoint and checkpoint.last_message_id > 0:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Re-scrape interrompu détecté : {listing_count:,} listings en DB, "
                    f"checkpoint msg_id={checkpoint.last_message_id:,}. "
                    "Utilise /resume-rescrape pour reprendre sans perte, "
                    "ou relance avec force=true pour tout effacer."
                ),
            )

    _sync_running = True
    _sync_logs.clear()

    async def broadcast(msg: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        _sync_logs.append(line)
        for ws in list(_ws_clients):
            try:
                await ws.send_text(line)
            except Exception:
                pass

    async def do_fresh_rescrape():
        global _sync_running
        import shutil
        from database import engine
        from sqlalchemy import text

        try:
            # ── Backup ────────────────────────────────────────────────────────
            db_path = engine.url.database
            if db_path and os.path.exists(db_path):
                stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                bak = f"{db_path}.backup_{stamp}"
                shutil.copy2(db_path, bak)
                await broadcast(f"Backup: {os.path.basename(bak)}")
            else:
                await broadcast("Backup ignoré (fichier DB introuvable en local)")

            # ── Truncate data, keep schema ────────────────────────────────────
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM listings"))
                conn.execute(text("DELETE FROM auctions"))
                conn.execute(text("DELETE FROM sync_checkpoints"))
            await broadcast("Tables vidées (auctions, listings, sync_checkpoints)")

            # ── Re-scrape from scratch ────────────────────────────────────────
            await broadcast("Démarrage du scrape complet depuis msg_id=0...")
            from services.scraper import run_sync
            result = await run_sync(log_callback=broadcast)
            if "error" in result:
                await broadcast(f"ERREUR: {result['error']}")
            else:
                await broadcast(
                    f"Scrape terminé : {result.get('synced', 0):,} records, "
                    f"msg_id={result.get('last_message_id', 0):,}"
                )
        except Exception as e:
            logger.exception("fresh-rescrape failed")
            await broadcast(f"ERREUR: {e}")
        finally:
            _sync_running = False

    asyncio.create_task(do_fresh_rescrape())
    return {"message": "Fresh re-scrape started — follow logs via WebSocket /api/admin/logs"}


@router.post("/resume-rescrape")
async def resume_rescrape(db: Session = Depends(get_db), _=Depends(verify_token)):
    """
    Reprend un re-scrape interrompu depuis le dernier checkpoint sauvegardé.
    Ne touche pas aux données existantes — continue là où le crash s'est produit.
    """
    global _sync_running
    if _sync_running:
        return {"message": "Sync already running — wait for it to finish"}

    checkpoint = db.query(SyncCheckpoint).first()
    resume_from = checkpoint.last_message_id if checkpoint else 0

    _sync_running = True
    _sync_logs.clear()

    async def broadcast(msg: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        _sync_logs.append(line)
        for ws in list(_ws_clients):
            try:
                await ws.send_text(line)
            except Exception:
                pass

    async def do_resume():
        global _sync_running
        try:
            await broadcast(f"Reprise du re-scrape depuis msg_id={resume_from:,}...")
            from services.scraper import run_sync
            result = await run_sync(log_callback=broadcast)
            if "error" in result:
                await broadcast(f"ERREUR: {result['error']}")
            else:
                await broadcast(
                    f"Scrape terminé : {result.get('synced', 0):,} nouveaux records, "
                    f"msg_id={result.get('last_message_id', 0):,}"
                )
        except Exception as e:
            logger.exception("resume-rescrape failed")
            await broadcast(f"ERREUR: {e}")
        finally:
            _sync_running = False

    asyncio.create_task(do_resume())
    return {
        "message": f"Reprise depuis msg_id={resume_from:,} — follow logs via WebSocket /api/admin/logs"
    }


@router.post("/relink")
async def run_relink(db: Session = Depends(get_db), _=Depends(verify_token)):
    """
    Re-link toutes les auctions vers leur meilleur listing (1:1) via le linker optimisé.
    Réinitialise d'abord linked_auction_id pour un re-link global propre.
    Opération non-bloquante : démarre en arrière-plan, résultat dans les logs admin.
    """
    global _sync_running
    if _sync_running:
        return {"message": "A sync is already running — relink blocked"}

    _sync_running = True
    _sync_logs.clear()

    async def broadcast(msg: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        _sync_logs.append(line)
        for ws in list(_ws_clients):
            try:
                await ws.send_text(line)
            except Exception:
                _ws_clients.discard(ws) if hasattr(_ws_clients, "discard") else None

    async def do_relink():
        global _sync_running
        from database import SessionLocal
        from models import Listing
        from services.linker import link_auctions
        import asyncio

        db2 = SessionLocal()
        try:
            await broadcast("Réinitialisation des liens existants...")
            n_reset = db2.query(Listing).filter(Listing.linked_auction_id.isnot(None)).update(
                {"linked_auction_id": None}, synchronize_session=False
            )
            db2.commit()
            await broadcast(f"  {n_reset:,} listings déliés — pool complet disponible")

            await broadcast("Re-linking en cours (assignation optimale)...")
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                None, lambda: link_auctions(db2, dry_run=False, verbose=False)
            )
            pct = stats["linked_high"] * 100 // max(1, stats["auctions_total"])
            await broadcast(
                f"Re-link terminé : ✓ high={stats['linked_high']:,} ({pct}%)  "
                f"⚠ review={stats['needs_review']:,}  ∅ sans={stats['unmatched']:,}"
            )
        except Exception as e:
            logger.exception("Relink failed")
            await broadcast(f"ERREUR relink: {e}")
        finally:
            db2.close()
            _sync_running = False

    asyncio.create_task(do_relink())
    return {"message": "Re-link started — follow progress via WebSocket /api/admin/logs"}


@router.post("/migrate")
async def run_migrations(db: Session = Depends(get_db), _=Depends(verify_token)):
    """
    Applique toutes les migrations idempotentes : Tier 2 columns + listings.model_normalized.
    Sûr à appeler plusieurs fois. N'écrase rien si déjà présent.
    """
    from database import engine, SessionLocal
    from sqlalchemy import text
    from services.normalizer import normalize_model

    results = []

    # ── Tier 2 columns ──────────────────────────────────────────────────────────
    tier2_cols = {
        "auctions": [("raw_text", "TEXT"), ("result_line_index", "INTEGER"), ("grouped_id", "BIGINT")],
        "listings": [("raw_text", "TEXT"), ("grouped_id", "BIGINT")],
    }
    # ── Tier 3 columns — pont déterministe lot OCR ──────────────────────────────
    tier3_cols = {
        "listings": [
            ("lot_number", "VARCHAR"),
            ("lot_ocr_confidence", "VARCHAR"),
            ("report_photo_index", "INTEGER"),
            ("condition_score", "VARCHAR"),
            # Finition extraite du model_raw (ex : "GTS", "GT4", "Turbo S").
            ("variant", "VARCHAR"),
        ],
        "auctions": [
            # Note d'état dénormalisée depuis le listing relié (copiée lors du match "high").
            ("condition_score", "VARCHAR"),
            # Finition dénormalisée depuis le listing relié ou extraite du model_raw.
            ("variant", "VARCHAR"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in {**tier2_cols, **tier3_cols}.items():
            existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            for col_name, col_type in cols:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                    results.append(f"✓ {table}.{col_name} ajouté")
                else:
                    results.append(f"• {table}.{col_name} déjà présent")

    # ── listings.model_normalized backfill ──────────────────────────────────────
    with engine.begin() as conn:
        existing = {r[1] for r in conn.execute(text("PRAGMA table_info(listings)"))}
        if "model_normalized" not in existing:
            conn.execute(text("ALTER TABLE listings ADD COLUMN model_normalized VARCHAR"))
            results.append("✓ listings.model_normalized ajouté")

    db2 = SessionLocal()
    try:
        from models import Listing
        listings = db2.query(Listing).filter(Listing.model_normalized.is_(None)).all()
        n = 0
        for lst in listings:
            lst.model_normalized = normalize_model(lst.model_raw or "")
            n += 1
        db2.commit()
        results.append(f"✓ {n:,} listings backfillés (model_normalized)")
    finally:
        db2.close()

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_listings_model_normalized ON listings(model_normalized)"
        ))
    results.append("✓ index ix_listings_model_normalized (ou déjà présent)")

    return {"applied": results}


@router.post("/renormalize")
async def run_renormalize(db: Session = Depends(get_db), _=Depends(verify_token)):
    """
    Backfill idempotent : recalcule model_normalized ET variant sur tous les Listings et Auctions.
    Opération non-bloquante — résultat dans les logs WebSocket.
    """
    global _sync_running
    if _sync_running:
        return {"message": "A sync is already running — renormalize blocked"}

    _sync_running = True
    _sync_logs.clear()

    async def broadcast(msg: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        _sync_logs.append(line)
        for ws in list(_ws_clients):
            try:
                await ws.send_text(line)
            except Exception:
                pass

    async def do_renormalize():
        global _sync_running
        from database import SessionLocal
        from models import Listing, Auction
        from services.normalizer import normalize_model, extract_variant
        import asyncio

        db2 = SessionLocal()
        try:
            # ── Listings ────────────────────────────────────────────────────────
            listings = db2.query(Listing).all()
            n_lst = 0
            for lst in listings:
                raw = lst.model_raw or ""
                norm = normalize_model(raw)
                variant = extract_variant(raw, norm)
                if lst.model_normalized != norm or lst.variant != variant:
                    lst.model_normalized = norm
                    lst.variant = variant
                    n_lst += 1
            db2.commit()
            await broadcast(f"Listings recalculés : {n_lst:,} mis à jour / {len(listings):,} total")

            # ── Auctions ────────────────────────────────────────────────────────
            auctions = db2.query(Auction).all()
            n_au = 0
            for au in auctions:
                raw = au.model_raw or ""
                norm = normalize_model(raw)
                variant = extract_variant(raw, norm)
                changed = False
                if au.model_normalized != norm:
                    au.model_normalized = norm
                    changed = True
                # Ne pas écraser un variant déjà propagé depuis le listing (plus riche)
                if au.variant is None and variant is not None:
                    au.variant = variant
                    changed = True
                if changed:
                    n_au += 1
            db2.commit()
            await broadcast(f"Auctions recalculées : {n_au:,} mises à jour / {len(auctions):,} total")
            await broadcast("Renormalisation terminée ✓")
        except Exception as e:
            logger.exception("Renormalize failed")
            await broadcast(f"ERREUR renormalize: {e}")
        finally:
            db2.close()
            _sync_running = False

    asyncio.create_task(do_renormalize())
    return {"message": "Renormalization started — follow progress via WebSocket /api/admin/logs"}


@router.websocket("/logs")
async def ws_logs(websocket: WebSocket):
    ticket = websocket.query_params.get("ticket")
    if not ticket or ticket not in _ws_tickets:
        await websocket.close(code=4001)
        return

    if time.time() > _ws_tickets[ticket]:
        del _ws_tickets[ticket]
        await websocket.close(code=4001)
        return

    # Consume ticket — one-time use only
    del _ws_tickets[ticket]

    await websocket.accept()
    _ws_clients.append(websocket)

    for log in _sync_logs[-50:]:
        try:
            await websocket.send_text(log)
        except Exception:
            break

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
