import os
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import WatchlistEntry, Auction, AuctionStatus
from routers.auth import verify_token

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

LBC_SERVICE_URL = os.getenv("LBC_SERVICE_URL", "http://localhost:3001")

SEED_DATA = [
    {
        "model_name": "Porsche Cayenne",
        "generation_code": "958",
        "year_start": 2010, "year_end": 2017,
        "phases": [
            {"phase": 1, "year_from": 2010, "year_to": 2014},
            {"phase": 2, "year_from": 2014, "year_to": 2017},
        ],
        "variants": [{"name": "GTS", "hp": 420}, {"name": "Turbo", "hp": 500}],
        "lbc_price_eur": 25000, "lbc_price_note": "avg",
        "bid_min": 17000, "bid_max": 18000, "bid_unit": "yen",
        "lbc_query": "porsche cayenne 958",
        "lbc_filters": {"brand": "porsche", "model": "cayenne", "year_min": 2010, "year_max": 2017},
        "auction_model_key": "Cayenne", "sort_order": 1,
    },
    {
        "model_name": "BMW M3",
        "generation_code": "E92/E93",
        "year_start": 2007, "year_end": 2012,
        "phases": [],
        "variants": [{"name": "Coupé E92", "hp": 420}, {"name": "Cabriolet E93", "hp": 420}],
        "lbc_price_eur": 31000, "lbc_price_note": "min",
        "bid_min": None, "bid_max": 20000, "bid_unit": "yen",
        "lbc_query": "bmw m3 e92 e93",
        "lbc_filters": {"brand": "bmw", "model": "m3", "year_min": 2007, "year_max": 2013},
        "auction_model_key": "M3", "sort_order": 2,
    },
    {
        "model_name": "Mercedes CLS 350",
        "generation_code": "W218",
        "year_start": 2011, "year_end": 2018,
        "phases": [
            {"phase": 1, "year_from": 2011, "year_to": 2014},
            {"phase": 2, "year_from": 2014, "year_to": 2018},
        ],
        "variants": [{"name": "350 CDI / BlueTEC", "hp": 265}],
        "lbc_price_eur": 17500, "lbc_price_note": "avg",
        "bid_min": 800, "bid_max": 900, "bid_unit": "yen",
        "lbc_query": "mercedes cls 350 w218",
        "lbc_filters": {"brand": "mercedes_benz", "model": "cls", "year_min": 2011, "year_max": 2018},
        "auction_model_key": "CLS", "sort_order": 3,
    },
    {
        "model_name": "Porsche 911 Carrera",
        "generation_code": "997",
        "year_start": 2004, "year_end": 2012,
        "phases": [
            {"phase": 1, "year_from": 2004, "year_to": 2008, "note": "S 355ch — 42/43k€ coupé, 50k€ cab"},
            {"phase": 2, "year_from": 2008, "year_to": 2012, "note": "S 385ch"},
        ],
        "variants": [
            {"name": "S Coupé P1", "hp": 355},
            {"name": "S Cabriolet P1", "hp": 355},
            {"name": "S Coupé P2", "hp": 385},
        ],
        "lbc_price_eur": None, "lbc_price_note": "voir par phase",
        "bid_min": None, "bid_max": None, "bid_unit": "yen",
        "lbc_query": "porsche 911 997",
        "lbc_filters": {"brand": "porsche", "model": "911", "year_min": 2004, "year_max": 2012},
        "auction_model_key": "911", "sort_order": 4,
    },
    {
        "model_name": "Chevrolet Corvette",
        "generation_code": "C6",
        "year_start": 2005, "year_end": 2013,
        "phases": [
            {"phase": 1, "year_from": 2005, "year_to": 2007, "note": "6.0 LS2"},
            {"phase": 2, "year_from": 2008, "year_to": 2013, "note": "6.2 LS3"},
        ],
        "variants": [
            {"name": "LS2 6.0 (Phase 1)", "hp": 400},
            {"name": "LS3 6.2 (Phase 2)", "hp": 436},
        ],
        "lbc_price_eur": 35000, "lbc_price_note": "phase 2",
        "bid_min": None, "bid_max": 29000, "bid_unit": "yen",
        "lbc_query": "corvette c6",
        "lbc_filters": {"brand": "chevrolet", "model": "corvette", "year_min": 2005, "year_max": 2013},
        "auction_model_key": "Corvette", "sort_order": 5,
    },
    {
        "model_name": "BMW 530",
        "generation_code": "G30",
        "year_start": 2016, "year_end": 2023,
        "phases": [
            {"phase": 1, "year_from": 2016, "year_to": 2020},
            {"phase": 2, "year_from": 2020, "year_to": 2023},
        ],
        "variants": [{"name": "530i / 530d", "hp": 252}],
        "lbc_price_eur": 20000, "lbc_price_note": "530",
        "bid_min": None, "bid_max": 1600, "bid_unit": "yen",
        "lbc_query": "bmw 530 g30",
        "lbc_filters": {"brand": "bmw", "model": "serie_5", "year_min": 2016, "year_max": 2023},
        "auction_model_key": "530", "sort_order": 6,
    },
]


@router.get("")
def get_watchlist(db: Session = Depends(get_db)):
    entries = db.query(WatchlistEntry).order_by(WatchlistEntry.sort_order).all()
    result = []
    for e in entries:
        avg_price = (
            db.query(func.avg(Auction.final_price_eur))
            .filter(
                Auction.model_normalized.ilike(f"%{e.auction_model_key}%"),
                Auction.status == AuctionStatus.sold,
                Auction.final_price_eur.isnot(None),
            )
            .scalar()
        ) if e.auction_model_key else None

        count_sold = (
            db.query(func.count(Auction.id))
            .filter(
                Auction.model_normalized.ilike(f"%{e.auction_model_key}%"),
                Auction.status == AuctionStatus.sold,
            )
            .scalar()
        ) if e.auction_model_key else 0

        result.append({
            "id": e.id,
            "model_name": e.model_name,
            "generation_code": e.generation_code,
            "year_start": e.year_start,
            "year_end": e.year_end,
            "phases": e.phases or [],
            "variants": e.variants or [],
            "lbc_price_eur": e.lbc_price_eur,
            "lbc_price_note": e.lbc_price_note,
            "bid_min": e.bid_min,
            "bid_max": e.bid_max,
            "bid_unit": e.bid_unit,
            "lbc_query": e.lbc_query,
            "lbc_filters": e.lbc_filters or {},
            "auction_model_key": e.auction_model_key,
            "auction_avg_eur": round(avg_price) if avg_price else None,
            "auction_sold_count": count_sold or 0,
        })
    return result


@router.post("/seed")
def seed_watchlist(db: Session = Depends(get_db), _=Depends(verify_token)):
    existing = db.query(WatchlistEntry).count()
    if existing > 0:
        return {"message": f"Already seeded ({existing} entries)"}
    for item in SEED_DATA:
        db.add(WatchlistEntry(**item))
    db.commit()
    return {"message": f"Seeded {len(SEED_DATA)} entries"}


@router.get("/lbc-search")
async def lbc_search(
    query: str = Query(...),
    brand: str = None,
    model: str = None,
    year_min: int = None,
    year_max: int = None,
    km_max: int = None,
    price_min: int = None,
    price_max: int = None,
):
    params = {"query": query}
    if brand: params["brand"] = brand
    if model: params["model"] = model
    if year_min: params["year_min"] = year_min
    if year_max: params["year_max"] = year_max
    if km_max: params["km_max"] = km_max
    if price_min: params["price_min"] = price_min
    if price_max: params["price_max"] = price_max
    if not os.getenv("LBC_SERVICE_URL"):
        raise HTTPException(
            status_code=503,
            detail="LBC service not configured. Set LBC_SERVICE_URL in environment."
        )
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(f"{LBC_SERVICE_URL}/search", params=params)
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"LBC service unreachable at {LBC_SERVICE_URL}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
