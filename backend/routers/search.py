from fastapi import APIRouter, Depends, Query, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
from typing import Optional

from database import get_db
from models import Auction, Listing, AuctionStatus
from services.stats import compute_stats, build_filters
from services.phases import derive_phase

router = APIRouter(prefix="/api", tags=["search"])
_limiter = Limiter(key_func=get_remote_address)


@router.get("/models")
@_limiter.limit("60/minute")
def get_models(request: Request, db: Session = Depends(get_db)):
    rows = db.query(Auction.model_normalized).distinct().order_by(Auction.model_normalized).all()
    return [r[0] for r in rows if r[0]]


@router.get("/model-options")
@_limiter.limit("60/minute")
def get_model_options(request: Request, model: str, db: Session = Depends(get_db)):
    """
    Retourne les options disponibles pour un modèle donné :
      - variants  : liste des finitions distinctes (non nulles) dans les données
      - years     : bornes min/max des années véhicule
      - phases    : bandes d'années curées (depuis WatchlistEntry) — liste vide si non curé
    Sert la divulgation progressive dans l'UI.
    """
    from sqlalchemy import func
    from models import WatchlistEntry

    base_q = db.query(Auction).filter(Auction.model_normalized.ilike(f"%{model}%"))

    # Variants distinctes
    variant_rows = (
        base_q.with_entities(Auction.variant)
        .filter(Auction.variant.isnot(None))
        .distinct()
        .order_by(Auction.variant)
        .all()
    )
    variants = [r[0] for r in variant_rows]

    # Bornes d'années
    year_bounds = base_q.with_entities(
        func.min(Auction.year), func.max(Auction.year)
    ).first()
    years = {
        "min": year_bounds[0] if year_bounds else None,
        "max": year_bounds[1] if year_bounds else None,
    }

    # Phases depuis WatchlistEntry (clé auction_model_key ⊂ model)
    watchlist_entry = (
        db.query(WatchlistEntry)
        .filter(Auction.model_normalized.ilike(f"%{model}%"))
        .first()
    )
    # Chercher l'entrée watchlist dont auction_model_key est contenu dans model
    all_wl = db.query(WatchlistEntry).filter(WatchlistEntry.auction_model_key.isnot(None)).all()
    phases = []
    gen_code = None
    for wl in all_wl:
        key = (wl.auction_model_key or "").lower()
        if key and key in model.lower():
            phases = wl.phases or []
            gen_code = wl.generation_code
            break

    return {
        "model": model,
        "variants": variants,
        "years": years,
        "phases": phases,
        "generation_code": gen_code,
    }


@router.get("/search")
@_limiter.limit("30/minute")
def search(
    request: Request,
    model: Optional[str] = None,
    variant: Optional[str] = None,
    mileage_min: Optional[int] = None,
    mileage_max: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    confidence: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort_by: str = Query("date", pattern="^(date|price|mileage)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    filters = build_filters(db, model, mileage_min, mileage_max, status, date_from, date_to, year_min, year_max, confidence, variant)
    query = db.query(Auction)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    sort_col = {"date": Auction.auction_date, "price": Auction.final_price_eur, "mileage": Auction.mileage_km}.get(sort_by, Auction.auction_date)
    order_fn = sort_col.asc() if sort_order == "asc" else sort_col.desc()
    auctions = query.order_by(order_fn).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "results": [
            {
                "id": a.id,
                "lot_number": a.lot_number,
                "model": a.model_normalized,
                "variant": a.variant,
                "year": a.year,
                "mileage_km": a.mileage_km,
                "start_price_eur": a.start_price_eur,
                "final_price_eur": a.final_price_eur,
                "status": a.status.value if a.status else None,
                "auction_date": a.auction_date.isoformat() if a.auction_date else None,
                # Fiabilité : "high" = year/km certains ; "review" = à vérifier
                # (année non fiable, plusieurs annonces équivalentes) ; None = sans annonce.
                "match_confidence": a.match_confidence,
                # Note d'état du véhicule (fiche OCR) — ex: "4.5", "5", "R", None
                "condition_score": a.condition_score,
            }
            for a in auctions
        ],
    }


@router.get("/stats")
@_limiter.limit("30/minute")
def get_stats(
    request: Request,
    model: Optional[str] = None,
    variant: Optional[str] = None,
    mileage_min: Optional[int] = None,
    mileage_max: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    confidence: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return compute_stats(db, model, mileage_min, mileage_max, status, date_from, date_to, year_min, year_max, confidence, variant)


@router.get("/lot/{lot_id}")
@_limiter.limit("60/minute")
def get_lot(request: Request, lot_id: int, db: Session = Depends(get_db)):
    auction = db.query(Auction).filter(Auction.id == lot_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Lot not found")

    similar = (
        db.query(Auction)
        .filter(
            Auction.model_normalized == auction.model_normalized,
            Auction.id != auction.id,
            Auction.mileage_km.between(
                (auction.mileage_km or 0) - 20000,
                (auction.mileage_km or 0) + 20000,
            ),
        )
        .order_by(Auction.auction_date.desc())
        .limit(10)
        .all()
    )

    listing = auction.listing
    photos = listing.photo_file_ids if listing else []
    telegram_message_id = listing.telegram_message_id if listing else None

    phase = derive_phase(db, auction.model_normalized, auction.year)

    return {
        "id": auction.id,
        "lot_number": auction.lot_number,
        "model": auction.model_normalized,
        "model_raw": auction.model_raw,
        "variant": auction.variant,
        "year": auction.year,
        "mileage_km": auction.mileage_km,
        "start_price_eur": auction.start_price_eur,
        "final_price_eur": auction.final_price_eur,
        "status": auction.status.value if auction.status else None,
        "auction_date": auction.auction_date.isoformat() if auction.auction_date else None,
        "match_confidence": auction.match_confidence,
        # Note d'état du véhicule (fiche OCR) — ex: "4.5", "5", "R", None
        "condition_score": auction.condition_score,
        "phase": phase,
        "photos": photos or [],
        "telegram_message_id": telegram_message_id,
        "similar": [
            {
                "id": s.id,
                "lot_number": s.lot_number,
                "year": s.year,
                "mileage_km": s.mileage_km,
                "final_price_eur": s.final_price_eur,
                "status": s.status.value if s.status else None,
                "auction_date": s.auction_date.isoformat() if s.auction_date else None,
            }
            for s in similar
        ],
    }
