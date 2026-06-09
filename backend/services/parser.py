import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import date


@dataclass
class ParsedListing:
    year: Optional[int]
    model_raw: str
    mileage_km: Optional[int]
    start_price_eur: Optional[int]


@dataclass
class ParsedAuctionResult:
    lot_number: str
    model_raw: str
    price_eur: Optional[int]
    status: str              # sold / not_sold / canceled
    line_index: Optional[int] = field(default=None)  # ordinal dans le message résultat


# En-tête de message résultat : "Today's results (06/04)" ou "Todays results (6/4)"
RESULTS_HEADER_PATTERN = re.compile(
    r"today'?s\s+results\s*\((\d{1,2})/(\d{1,2})\)",
    re.IGNORECASE,
)

LISTING_PATTERN = re.compile(
    r"(\d{4})\s+model\s+(.+?)\.\s*(\d+(?:\.\d+)?)k?\s*km\.(?:\s*start\s+price\s+(\d+)€?)?",
    re.IGNORECASE,
)

RESULT_SOLD_PATTERN = re.compile(
    r"^(\w+),\s*(.+?)\s+(\d+)€\s+sold\s*$",
    re.IGNORECASE,
)

RESULT_NOT_SOLD_PATTERN = re.compile(
    r"^(\w+),\s*(.+?)(?:\s+(\d+)€)?\s+not\s+sold\s*$",
    re.IGNORECASE,
)

RESULT_CANCELED_PATTERN = re.compile(
    r"^(\w+),\s*(.+?)\s+canceled\s+by\s+seller\s*$",
    re.IGNORECASE,
)


def parse_listing(text: str) -> Optional[ParsedListing]:
    m = LISTING_PATTERN.search(text)
    if not m:
        return None
    year = int(m.group(1))
    model_raw = m.group(2).strip()
    mileage_str = m.group(3).replace(",", ".")
    mileage_km = int(float(mileage_str) * 1000) if "k" not in m.group(0).lower() else int(float(mileage_str) * 1000)
    # handle "65k km" → 65000 and "65 km" → 65
    raw_mileage_part = re.search(r"([\d.]+)(k?)\s*km", m.group(0), re.IGNORECASE)
    if raw_mileage_part:
        val = float(raw_mileage_part.group(1).replace(",", "."))
        is_k = raw_mileage_part.group(2).lower() == "k"
        mileage_km = int(val * 1000) if is_k else int(val)
    start_price = int(m.group(4)) if m.group(4) else None
    return ParsedListing(year=year, model_raw=model_raw, mileage_km=mileage_km, start_price_eur=start_price)


def parse_auction_result_line(line: str) -> Optional[ParsedAuctionResult]:
    line = line.strip()
    m = RESULT_SOLD_PATTERN.match(line)
    if m:
        return ParsedAuctionResult(
            lot_number=m.group(1),
            model_raw=m.group(2).strip(),
            price_eur=int(m.group(3)),
            status="sold",
        )
    m = RESULT_NOT_SOLD_PATTERN.match(line)
    if m:
        return ParsedAuctionResult(
            lot_number=m.group(1),
            model_raw=m.group(2).strip(),
            price_eur=int(m.group(3)) if m.group(3) else None,
            status="not_sold",
        )
    m = RESULT_CANCELED_PATTERN.match(line)
    if m:
        return ParsedAuctionResult(
            lot_number=m.group(1),
            model_raw=m.group(2).strip(),
            price_eur=None,
            status="canceled",
        )
    return None


def parse_results_header_date(text: str, fallback_year: int) -> Optional[date]:
    """
    Extrait la date du message résultat depuis l'en-tête "Today's results (MM/DD)".
    L'année est inférée à partir de fallback_year (timestamp du message) avec une
    garde pour les résultats postés en début janvier qui référencent décembre.

    Retourne None si aucun en-tête trouvé.
    """
    m = RESULTS_HEADER_PATTERN.search(text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = fallback_year
    # Garde bascule d'année : en-tête décembre reçu en janvier → année précédente
    if month == 12 and fallback_year and date.today().month == 1:
        year = fallback_year - 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_results_message(text: str) -> list[ParsedAuctionResult]:
    """Parse toutes les lignes de résultats d'un message.
    Renseigne line_index = position parmi les lignes résultat parsées (0-based).
    """
    results = []
    for line in text.splitlines():
        r = parse_auction_result_line(line)
        if r:
            r.line_index = len(results)
            results.append(r)
    return results
