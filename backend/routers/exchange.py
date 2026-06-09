import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["exchange"])

_cache: dict = {"rate": None, "updated_at": None}
_TTL = timedelta(minutes=30)


async def get_eur_jpy() -> float:
    now = datetime.utcnow()
    if _cache["rate"] and _cache["updated_at"] and (now - _cache["updated_at"]) < _TTL:
        return _cache["rate"]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("https://api.frankfurter.app/latest?from=EUR&to=JPY")
            rate = r.json()["rates"]["JPY"]
            _cache["rate"] = rate
            _cache["updated_at"] = now
            return rate
    except Exception:
        return _cache["rate"] or 160.0


@router.get("/exchange-rate")
async def exchange_rate():
    rate = await get_eur_jpy()
    return {
        "EUR_JPY": rate,
        "updated_at": _cache["updated_at"].isoformat() if _cache["updated_at"] else None,
    }
