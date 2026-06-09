import statistics
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from models import Auction, AuctionStatus
from datetime import date
from typing import Optional


def build_filters(
    db: Session,
    model: Optional[str],
    mileage_min: Optional[int],
    mileage_max: Optional[int],
    status: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    confidence: Optional[str] = None,
    variant: Optional[str] = None,
):
    filters = []
    if model:
        filters.append(Auction.model_normalized.ilike(f"%{model}%"))
    if variant:
        filters.append(Auction.variant == variant)
    if mileage_min is not None:
        filters.append(Auction.mileage_km >= mileage_min)
    if mileage_max is not None:
        filters.append(Auction.mileage_km <= mileage_max)
    if status and status != "all":
        try:
            filters.append(Auction.status == AuctionStatus(status))
        except ValueError:
            pass
    if date_from:
        filters.append(Auction.auction_date >= date_from)
    if date_to:
        filters.append(Auction.auction_date <= date_to)
    if year_min is not None:
        filters.append(Auction.year >= year_min)
    if year_max is not None:
        filters.append(Auction.year <= year_max)
    if confidence == "high":
        filters.append(Auction.match_confidence == "high")
    elif confidence == "review":
        filters.append(Auction.match_confidence == "review")
    return filters


def compute_stats(
    db: Session,
    model: Optional[str] = None,
    mileage_min: Optional[int] = None,
    mileage_max: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    confidence: Optional[str] = None,
    variant: Optional[str] = None,
) -> dict:
    filters = build_filters(db, model, mileage_min, mileage_max, status, date_from, date_to, year_min, year_max, confidence, variant)

    query = db.query(Auction)
    if filters:
        query = query.filter(and_(*filters))

    auctions = query.all()

    if not auctions:
        return {
            "count": 0,
            "avg_price": None,
            "median_price": None,
            "min_price": None,
            "max_price": None,
            "sold_rate": None,
            "price_by_mileage": [],
            "price_over_time": [],
        }

    prices = [a.final_price_eur for a in auctions if a.final_price_eur is not None]
    sold = [a for a in auctions if a.status == AuctionStatus.sold]
    sold_rate = len(sold) / len(auctions) * 100 if auctions else 0

    price_by_mileage = [
        {"mileage": a.mileage_km, "price": a.final_price_eur or a.start_price_eur, "model": a.model_normalized, "lot": a.lot_number, "status": a.status.value, "id": a.id}
        for a in auctions
        if a.mileage_km is not None and (a.final_price_eur or a.start_price_eur)
    ]

    time_map: dict[str, list[int]] = {}
    for a in sold:
        if a.auction_date and a.final_price_eur:
            key = a.auction_date.strftime("%Y-%m")
            time_map.setdefault(key, []).append(a.final_price_eur)

    price_over_time = sorted(
        [{"date": k, "avg_price": int(sum(v) / len(v)), "count": len(v)} for k, v in time_map.items()],
        key=lambda x: x["date"],
    )

    return {
        "count": len(auctions),
        "avg_price": int(sum(prices) / len(prices)) if prices else None,
        "median_price": int(statistics.median(prices)) if prices else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "sold_rate": round(sold_rate, 1),
        "price_by_mileage": price_by_mileage,
        "price_over_time": price_over_time,
    }
