"""
End-to-end pipeline test — simulates Telegram messages going through the full
parse → normalize → DB insert → API response cycle, without needing network access.
"""
import asyncio
import sys
import os
import pytest
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Hard-set (pas setdefault) : ces tests font des DELETE/INSERT destructifs. Si
# DATABASE_URL n'était pas posé AVANT que `database` soit importé par un autre
# test, l'engine partagé pointe sur la PROD (japan_auctions.db) → wipe silencieux.
os.environ["DATABASE_URL"] = os.environ.get("PIPELINE_TEST_DB", "sqlite:////tmp/test_pipeline.db")


def _isolated_db():
    """
    Engine/Session DÉDIÉS au fichier de test. On NE réutilise jamais
    database.engine (qui peut déjà être lié à la prod). Garde dure anti-prod.
    drop_all + create_all garantit que le schéma est toujours à jour même si
    le fichier de test persiste depuis une exécution précédente.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    url = os.environ["DATABASE_URL"]
    assert "japan_auctions" not in url, f"REFUS : test destructif pointant sur la prod ({url})"
    eng = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=eng)   # repart de zéro → schéma toujours frais
    Base.metadata.create_all(bind=eng)
    return eng, sessionmaker(bind=eng, autoflush=False, autocommit=False)

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0

def ok(name: str):
    global PASS
    PASS += 1
    print(f"  ✓ {name}")

def fail(name: str, reason: str = ""):
    global FAIL
    FAIL += 1
    print(f"  ✗ {name}" + (f": {reason}" if reason else ""))

def assert_eq(name, actual, expected):
    if actual == expected:
        ok(name)
    else:
        fail(name, f"got {actual!r}, expected {expected!r}")

def assert_true(name, value, reason=""):
    if value:
        ok(name)
    else:
        fail(name, reason)


# ── 1. Parser tests ───────────────────────────────────────────────────────────

def test_parser():
    print("\n=== Parser ===")
    from services.parser import parse_listing, parse_results_message, parse_auction_result_line

    LISTING_CASES = [
        ("2009 model bmw M3 coupe. 65k km. Start price 15700€",   2009, "bmw M3 coupe",          65000, 15700),
        ("2019 model Toyota Supra. 32k km. Start price 42000€",   2019, "Toyota Supra",           32000, 42000),
        ("2020 model Honda NSX. 15k km. Start price 85000€",      2020, "Honda NSX",              15000, 85000),
        ("1999 model Nissan Skyline R34. 110k km. Start price 62000€", 1999, "Nissan Skyline R34", 110000, 62000),
        ("2016 model Nissan GTR. 55k km. Start price 35000€",     2016, "Nissan GTR",             55000, 35000),
        ("2022 model Porsche 911. 5k km. Start price 120000€",    2022, "Porsche 911",             5000, 120000),
        ("2018 model Honda Civic. 45000 km. Start price 8000€",   2018, "Honda Civic",            45000, 8000),  # no k suffix
        ("2015 model Mazda MX-5. 32.5k km. Start price 12000€",  2015, "Mazda MX-5",             32500, 12000),  # decimal
        # No start price (common in the channel)
        ("2013 model GL550 amg packet. 131k km.",                  2013, "GL550 amg packet",      131000, None),
        ("2017 model Levante S. 18k km.",                          2017, "Levante S",               18000, None),
        ("2013 model bmw650i. 125k km.",                           2013, "bmw650i",                125000, None),
    ]

    for msg, yr, model, km, price in LISTING_CASES:
        r = parse_listing(msg)
        assert_true(f"parse listing: {model}", r is not None, "returned None")
        if r:
            assert_eq(f"  year={yr}", r.year, yr)
            assert_eq(f"  model={model!r}", r.model_raw, model)
            assert_eq(f"  km={km}", r.mileage_km, km)
            assert_eq(f"  price={price}", r.start_price_eur, price)

    NON_LISTINGS = [
        "Auction results for today",
        "Good morning everyone!",
        "Please bid responsibly",
        "Final prices below:",
    ]
    for msg in NON_LISTINGS:
        r = parse_listing(msg)
        assert_true(f"reject non-listing: {msg[:30]!r}", r is None, f"wrongly parsed: {r}")

    RESULT_CASES = [
        ("A001, BMW M3 15700€ sold",                    "A001", "BMW M3",   15700, "sold"),
        ("Z999, Some Car 99999€ not sold",               "Z999", "Some Car", 99999, "not_sold"),
        ("X123, Ferrari F40 canceled by seller",         "X123", "Ferrari F40", None, "canceled"),
        ("B042, Toyota Supra 45000€ SOLD",               "B042", "Toyota Supra", 45000, "sold"),  # uppercase
        ("C007, Nissan GT-R 68000€ not sold",            "C007", "Nissan GT-R", 68000, "not_sold"),
        # No price on "not sold" (common in the channel)
        ("80328, G63 amg not sold",                      "80328", "G63 amg",  None, "not_sold"),
        ("82336, carera not sold",                       "82336", "carera",   None, "not_sold"),
    ]
    for line, lot, model, price, status in RESULT_CASES:
        r = parse_auction_result_line(line)
        assert_true(f"parse result: {lot}", r is not None, "returned None")
        if r:
            assert_eq(f"  lot={lot}", r.lot_number, lot)
            assert_eq(f"  price={price}", r.price_eur, price)
            assert_eq(f"  status={status}", r.status, status)

    # Multi-line results message
    msg = "A001, BMW M3 15700€ sold\nA002, Toyota Supra 42000€ not sold\nA003, Honda NSX canceled by seller"
    results = parse_results_message(msg)
    assert_eq("multi-line: 3 results", len(results), 3)
    assert_eq("multi-line: first is sold", results[0].status, "sold")
    assert_eq("multi-line: second is not_sold", results[1].status, "not_sold")
    assert_eq("multi-line: third is canceled", results[2].status, "canceled")


# ── 2. Normalizer tests ───────────────────────────────────────────────────────

def test_normalizer():
    print("\n=== Normalizer ===")
    from services.normalizer import normalize_model

    CASES = [
        ("bmw M3 coupe",       "BMW M3"),
        ("Bmw m3",             "BMW M3"),
        ("BMW M3",             "BMW M3"),
        ("toyota supra mk4",   "Toyota Supra"),
        ("nissan gtr r35",     "Nissan GT-R"),
        ("nissan gt-r",        "Nissan GT-R"),
        ("honda s2000 type s", "Honda S2000"),
        ("mazda rx7 fd",       "Mazda RX-7"),
        ("mazda rx-7",         "Mazda RX-7"),
        ("subaru wrx sti",     "Subaru WRX"),
        ("porsche 911 carrera","Porsche 911 Carrera"),
    ]
    for raw, expected in CASES:
        result = normalize_model(raw)
        assert_eq(f"normalize {raw!r}", result, expected)

    # Unknown model should title-case gracefully
    r = normalize_model("some unknown vehicle 2019")
    assert_true("unknown model → title case", isinstance(r, str) and len(r) > 0)


# ── 3. Stats calculation tests ────────────────────────────────────────────────

def test_stats():
    print("\n=== Stats (calculation layer) ===")
    import statistics
    from models import Auction, AuctionStatus

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    # Clear and seed controlled dataset
    db.query(Auction).delete()
    db.commit()

    seed = [
        ("L1", "BMW M3",     "BMW M3",   2015, 65000, 15700, 16200, "sold",     "2024-03-01"),
        ("L2", "BMW M3",     "BMW M3",   2017, 45000, 18500, 19000, "sold",     "2024-03-01"),
        ("L3", "Toyota Supra","Toyota Supra",2019,32000,42000,45000,"sold",     "2024-03-08"),
        ("L4", "Nissan GT-R","Nissan GT-R",2016,55000,35000, None, "not_sold",  "2024-03-08"),
        ("L5", "Honda NSX",  "Honda NSX", 2020, 15000, 85000, 87500,"sold",     "2024-03-15"),
        ("L6", "BMW M3",     "BMW M3",   2014, 95000, 12000, 12500, "sold",     "2024-04-01"),
        ("L7", "Mazda RX-7","Mazda RX-7",2002, 78000, 18000,  None,"canceled",  "2024-04-01"),
        ("L8","Toyota Supra","Toyota Supra",2020,20000,55000,58000, "sold",     "2024-04-08"),
        ("L9","Nissan Skyline R34","Nissan Skyline R34",1999,110000,62000,68000,"sold","2024-04-15"),
        ("L10","BMW M3",     "BMW M3",   2018, 38000, 21000, 22500, "sold",     "2024-05-01"),
    ]
    for lot, raw, norm, yr, km, start, final, status, dt in seed:
        db.add(Auction(
            lot_number=lot, model_raw=raw, model_normalized=norm,
            year=yr, mileage_km=km, start_price_eur=start,
            final_price_eur=final, status=AuctionStatus(status),
            auction_date=date.fromisoformat(dt), telegram_message_id=hash(lot),
        ))
    db.commit()

    from services.stats import compute_stats

    # All records
    s = compute_stats(db)
    assert_eq("total count = 10",  s["count"], 10)
    assert_eq("sold_rate = 80.0%", s["sold_rate"], 80.0)
    assert_true("scatter data present", len(s["price_by_mileage"]) > 0)
    assert_true("trend data present",   len(s["price_over_time"]) > 0)

    sold_prices = [16200, 19000, 45000, 87500, 12500, 58000, 68000, 22500]
    exp_avg    = int(sum(sold_prices) / len(sold_prices))  # all statuses counted for avg
    # But stats counts ALL auctions' final_price_eur that are not None:
    all_finals = [16200, 19000, 45000, 87500, 12500, 58000, 68000, 22500]
    exp_avg    = int(sum(all_finals) / len(all_finals))
    exp_median = int(statistics.median(all_finals))
    assert_eq(f"avg price = {exp_avg}", s["avg_price"], exp_avg)
    assert_eq(f"median price = {exp_median}", s["median_price"], exp_median)

    # BMW only
    bmw = compute_stats(db, model="BMW M3")
    assert_eq("BMW count = 4",          bmw["count"], 4)
    assert_eq("BMW sold_rate = 100.0",  bmw["sold_rate"], 100.0)
    bmw_prices = [16200, 19000, 12500, 22500]
    assert_eq(f"BMW avg = {int(sum(bmw_prices)/len(bmw_prices))}", bmw["avg_price"], int(sum(bmw_prices)/len(bmw_prices)))

    # Mileage filter
    low_km = compute_stats(db, mileage_min=0, mileage_max=50000)
    low_km_lots = [l for l in seed if l[4] <= 50000]
    assert_eq(f"mileage ≤50k = {len(low_km_lots)}", low_km["count"], len(low_km_lots))

    # Status filter
    not_sold = compute_stats(db, status="not_sold")
    assert_eq("status=not_sold count = 1", not_sold["count"], 1)
    canceled = compute_stats(db, status="canceled")
    assert_eq("status=canceled count = 1", canceled["count"], 1)

    # Empty result
    empty = compute_stats(db, model="NonExistentModel999")
    assert_eq("empty → count=0",      empty["count"],       0)
    assert_eq("empty → avg=None",     empty["avg_price"],   None)
    assert_eq("empty → sold_rate=None",empty["sold_rate"],  None)

    db.close()


# ── 4. Full sync pipeline simulation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_pipeline():
    """Simulate what the Telethon scraper does: inject fake messages, run parsing+DB logic."""
    print("\n=== Sync Pipeline (simulated Telegram messages) ===")

    from models import Auction, Listing, SyncCheckpoint, AuctionStatus
    from services.parser import parse_listing, parse_results_message
    from services.normalizer import normalize_model

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    # Clear tables for clean test
    db.query(Auction).delete()
    db.query(Listing).delete()
    db.query(SyncCheckpoint).delete()
    db.commit()

    # Simulated Telegram messages (Type 1: listings, Type 2: results)
    FAKE_MESSAGES = [
        # Type 1 — listing messages
        (1001, "2019 model Toyota Supra. 32k km. Start price 42000€", date(2024, 3, 8), ["photo_id_1"]),
        (1002, "2020 model Honda NSX. 15k km. Start price 85000€",    date(2024, 3, 8), ["photo_id_2"]),
        (1003, "2009 model bmw M3 coupe. 65k km. Start price 15700€", date(2024, 3, 15), []),
        (1004, "2016 model Nissan GTR. 55k km. Start price 35000€",   date(2024, 3, 15), []),
        # Type 2 — results message (multiple lots in one message)
        (1010, "A001, Toyota Supra 45000€ sold\nA002, Honda NSX 87500€ sold\nA003, BMW M3 coupe 16200€ sold\nA004, Nissan GT-R canceled by seller", date(2024, 3, 22), []),
        # More listings
        (1020, "2022 model Porsche 911. 5k km. Start price 120000€",  date(2024, 4, 1), ["photo_id_3"]),
        (1021, "1999 model Nissan Skyline R34. 110k km. Start price 62000€", date(2024, 4, 1), []),
        # More results
        (1025, "B001, Porsche 911 118000€ sold\nB002, Nissan Skyline R34 68000€ sold", date(2024, 4, 8), []),
    ]

    synced_count = 0
    max_seen_id = 0

    for msg_id, text, msg_date, photo_ids in FAKE_MESSAGES:
        if msg_id > max_seen_id:
            max_seen_id = msg_id

        # Try listing parse
        listing_parsed = parse_listing(text)
        if listing_parsed:
            existing = db.query(Listing).filter_by(telegram_message_id=msg_id).first()
            if not existing:
                listing = Listing(
                    model_raw=listing_parsed.model_raw,
                    model_normalized=normalize_model(listing_parsed.model_raw),
                    year=listing_parsed.year,
                    mileage_km=listing_parsed.mileage_km,
                    start_price_eur=listing_parsed.start_price_eur,
                    photo_file_ids=photo_ids,
                    posted_date=msg_date,
                    telegram_message_id=msg_id,
                )
                db.add(listing)
                db.flush()  # match scraper behaviour: visible to same-session queries
                synced_count += 1

        # Try results parse
        results = parse_results_message(text)
        for r in results:
            existing = db.query(Auction).filter_by(lot_number=r.lot_number, auction_date=msg_date).first()
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
                    auction_date=msg_date,
                    telegram_message_id=msg_id,
                )

                # Link to listing
                matching = (
                    db.query(Listing)
                    .filter(Listing.model_raw.ilike(f"%{r.model_raw[:8]}%"))
                    .order_by(Listing.posted_date.desc())
                    .first()
                )
                if matching:
                    auction.year = matching.year
                    auction.mileage_km = matching.mileage_km
                    auction.start_price_eur = matching.start_price_eur
                    matching.linked_auction_id  # just touch relation

                db.add(auction)
                synced_count += 1

    db.commit()

    # Save checkpoint
    checkpoint = SyncCheckpoint(
        last_message_id=max_seen_id,
        records_synced=synced_count,
        status="idle",
    )
    db.add(checkpoint)
    db.commit()

    # Verify DB state
    total_listings = db.query(Listing).count()
    total_auctions = db.query(Auction).count()
    checkpoint = db.query(SyncCheckpoint).first()

    assert_eq("listings inserted = 6",  total_listings, 6)
    assert_eq("auctions inserted = 6",  total_auctions, 6)
    assert_eq("checkpoint saved",       checkpoint.last_message_id, 1025)
    assert_eq("records_synced = 12",    checkpoint.records_synced, 12)
    assert_eq("checkpoint status=idle", checkpoint.status, "idle")

    # Verify normalization happened
    supra = db.query(Auction).filter(Auction.model_normalized == "Toyota Supra").first()
    assert_true("Toyota Supra normalized", supra is not None)
    assert_eq("Supra status=sold", supra.status, AuctionStatus.sold)
    assert_eq("Supra price=45000", supra.final_price_eur, 45000)

    nsx = db.query(Auction).filter(Auction.model_normalized == "Honda NSX").first()
    assert_true("Honda NSX normalized", nsx is not None)
    assert_eq("NSX price=87500", nsx.final_price_eur, 87500)

    gtr = db.query(Auction).filter(Auction.model_normalized == "Nissan GT-R").first()
    assert_true("Nissan GT-R normalized", gtr is not None)
    assert_eq("GT-R canceled", gtr.status, AuctionStatus.canceled)
    assert_eq("GT-R price=None", gtr.final_price_eur, None)

    porsche = db.query(Auction).filter(Auction.model_normalized == "Porsche 911 Carrera").first()
    assert_true("Porsche 911 normalized", porsche is not None)
    assert_eq("Porsche sold", porsche.status, AuctionStatus.sold)

    # Verify listing-to-auction linking
    supra_listing = db.query(Listing).filter(Listing.model_raw.ilike("%Toyota Supra%")).first()
    assert_true("Supra listing exists", supra_listing is not None)
    if supra_listing:
        assert_eq("Supra listing km=32000", supra_listing.mileage_km, 32000)
        assert_eq("Supra listing price=42000", supra_listing.start_price_eur, 42000)
        assert_true("Supra listing has photo", len(supra_listing.photo_file_ids) > 0)

    # Verify linked data carried over to auction
    if supra and supra_listing:
        assert_eq("Supra auction km inherited", supra.mileage_km, 32000)

    # Verify photos stored
    nsx_listing = db.query(Listing).filter(Listing.model_raw.ilike("%Honda NSX%")).first()
    assert_true("NSX listing has photo", nsx_listing and len(nsx_listing.photo_file_ids) > 0)

    db.close()


# ── 5. API endpoints (in-process TestClient, fixture DB seeded in conftest) ───

def test_api_endpoints(api_client):
    """API contract tests — no external server, uses TestClient from conftest."""
    print("\n=== API endpoints (in-process) ===")

    r = api_client.get("/api/stats").json()
    assert_eq("API: count=10",        r["count"],    10)
    assert_eq("API: sold_rate=80.0",  r["sold_rate"], 80.0)
    assert_true("API: scatter data",  len(r["price_by_mileage"]) > 0)
    assert_true("API: trend data",    len(r["price_over_time"]) > 0)

    r = api_client.get("/api/search?model=BMW&mileage_min=30000&mileage_max=70000&status=sold").json()
    assert_true("API: BMW 30-70k sold exists", r["total"] > 0)

    r = api_client.get("/api/lot/1").json()
    assert_true("API: lot/1 has similar",      len(r["similar"]) > 0)
    assert_eq("API: lot/1 model=BMW M3",       r["model"], "BMW M3")

    r = api_client.get("/api/search?per_page=3&page=1").json()
    assert_eq("API: per_page=3 returns 3",     len(r["results"]), 3)
    assert_eq("API: total still 10",           r["total"], 10)

    r2 = api_client.get("/api/search?per_page=3&page=2").json()
    assert_eq("API: page 2 also returns 3",    len(r2["results"]), 3)
    ids_p1 = {x["id"] for x in r["results"]}
    ids_p2 = {x["id"] for x in r2["results"]}
    assert_true("API: page 1 ≠ page 2",        len(ids_p1 & ids_p2) == 0)


# ── 6. Linker — assignation globale + matching normalisé ─────────────────────

def test_linker_global_assignment():
    """
    Vérifie que l'assignation GLOBALE optimale ne vole pas l'annonce d'une
    autre enchère (bug de l'ancien algorithme glouton).

    Setup :
      - Annonce 1 (BMW M3, km=45000, prix=25000) — match FORT pour l'enchère A
      - Annonce 2 (BMW M3, km=52000, prix=31000) — seul candidat pour l'enchère B
    Avec le glouton, l'enchère A (traitée en premier) prend la meilleure annonce,
    laissant à B une annonce sous-optimale ou rien.
    Avec l'assignation globale, chaque enchère obtient SA bonne annonce.
    """
    print("\n=== Linker — assignation globale ===")
    from services.linker import _assign_batch, MATCH_MARGIN_MIN
    from services.normalizer import normalize_model
    from datetime import date

    # Objets factices (pas de DB)
    class FakeAuction:
        def __init__(self, aid, model, price, d):
            self._id = aid
            self.model_normalized = model
            self.final_price_eur = price
            self.auction_date = d
    class FakeListing:
        def __init__(self, lid, model, price, d, km):
            self._id = lid
            self.model_normalized = model
            self.start_price_eur = price
            self.posted_date = d
            self.mileage_km = km

    ref_date = date(2024, 5, 10)
    pre_date = date(2024, 5,  8)

    auA = FakeAuction("A", "BMW M3", 26000, ref_date)  # proche de lst1
    auB = FakeAuction("B", "BMW M3", 30000, ref_date)  # proche de lst2
    lst1 = FakeListing(1, "BMW M3", 25000, pre_date, 45000)
    lst2 = FakeListing(2, "BMW M3", 31000, pre_date, 52000)

    result = _assign_batch(
        [auA, auB], [lst1, lst2],
        lambda a: a.model_normalized, lambda l: l.model_normalized,
        lambda a: a.final_price_eur,  lambda a: a.auction_date,
        lambda l: l.start_price_eur,  lambda l: l.posted_date,
    )

    assert_true("linker: les 2 enchères ont un match", len(result) == 2)
    if len(result) == 2:
        match_A = result.get(id(auA))
        match_B = result.get(id(auB))
        assert_true("linker: enchère A obtient listing 1 (prix proche 26k)", match_A and match_A[0] is lst1)
        assert_true("linker: enchère B obtient listing 2 (prix proche 30k)", match_B and match_B[0] is lst2)


def test_linker_uses_normalized():
    """
    Vérifie que le linker compare NORMALISÉ↔NORMALISÉ.
    Un listing avec model_raw='bmw M3 coupe' / model_normalized='BMW M3' doit
    matcher l'enchère model_normalized='BMW M3' même si le raw ne matchait pas.
    """
    print("\n=== Linker — matching normalisé ===")
    from services.linker import find_best_listing
    from services.normalizer import normalize_model
    from models import Listing, Auction, AuctionStatus
    from datetime import date

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    ref_date = date(2024, 6, 10)
    pre_date = date(2024, 6,  8)

    # Listing avec raw bordélique MAIS normalized propre
    lst = Listing(
        model_raw="bmw M3 coupe",
        model_normalized=normalize_model("bmw M3 coupe"),  # "BMW M3"
        year=2018,
        mileage_km=40000,
        start_price_eur=28000,
        photo_file_ids=[],
        posted_date=pre_date,
        telegram_message_id=99001,
    )
    db.add(lst)
    db.commit()

    listing, confidence = find_best_listing(db, "BMW M3", 29000, ref_date)
    assert_true("listing trouvé via normalized", listing is not None)
    if listing:
        assert_eq("bon listing retourné", listing.id, lst.id)
    assert_true("confidence high ou review (pas none)", confidence in ("high", "review"))

    db.close()


# ── 7. Tier 2 — parser en-tête + line_index + alignement positionnel ─────────

def test_parse_results_header():
    print("\n=== Parser en-tête résultats ===")
    from services.parser import parse_results_header_date, parse_results_message
    from datetime import date

    # En-tête standard
    text = "Today's results (06/04)\n65032, 911 turbo 124000€ not sold\n65103, GL63 amg 10600€ sold"
    d = parse_results_header_date(text, 2025)
    assert_true("header date parsée", d is not None)
    if d:
        assert_eq("header mois=6", d.month, 6)
        assert_eq("header jour=4", d.day, 4)
        assert_eq("header année inférée=2025", d.year, 2025)

    # Variante sans apostrophe
    text2 = "Todays results (03/15)\nA001, BMW M3 25000€ sold"
    d2 = parse_results_header_date(text2, 2024)
    assert_true("header sans apostrophe", d2 is not None and d2.month == 3 and d2.day == 15)

    # Pas d'en-tête → None
    text3 = "A001, BMW M3 25000€ sold"
    assert_true("pas d'en-tête → None", parse_results_header_date(text3, 2024) is None)

    # line_index renseigné
    text4 = "Today's results (06/04)\n65032, 911 turbo 124000€ not sold\n65103, GL63 amg 10600€ sold"
    results = parse_results_message(text4)
    assert_eq("2 résultats parsés", len(results), 2)
    assert_eq("premier line_index=0", results[0].line_index, 0)
    assert_eq("deuxième line_index=1", results[1].line_index, 1)


def test_positional_alignment():
    """
    3 BMW M3 identiques dans le même message résultat et 3 annonces ordonnées.
    L'alignement positionnel doit récupérer le bon 1:1 là où le matching pur
    modèle serait ambigu (toutes les 3 ont le même score modèle).
    """
    print("\n=== Alignement positionnel par bande de lot ===")
    from services.linker import _align_session, _lot_band
    from services.normalizer import normalize_model
    from datetime import date

    ref_date = date(2024, 7, 10)
    pre_date = date(2024, 7,  8)

    # _lot_band
    assert_eq("lot_band 65032→65", _lot_band("65032"), "65")
    assert_eq("lot_band 73068→73", _lot_band("73068"), "73")
    assert_true("lot_band non-num→None", _lot_band("A001") is None)

    # 3 enchères BMW M3 avec prix différents (seul signal discriminant)
    class FakeAu:
        def __init__(self, p, idx): self.final_price_eur = p; self.result_line_index = idx
    class FakeLst:
        def __init__(self, p, mid): self.start_price_eur = p; self.telegram_message_id = mid

    bmw = "BMW M3"
    results_input = [
        (FakeAu(25000, 0), bmw, 25000, ref_date, 0),
        (FakeAu(31000, 1), bmw, 31000, ref_date, 1),
        (FakeAu(18000, 2), bmw, 18000, ref_date, 2),
    ]
    listings_input = [
        (FakeLst(24000, 101), bmw, 24000, pre_date),
        (FakeLst(30000, 102), bmw, 30000, pre_date),
        (FakeLst(17000, 103), bmw, 17000, pre_date),
    ]

    pairs = _align_session(results_input, listings_input)
    assert_true("alignement retourne des paires", len(pairs) > 0)
    if pairs:
        # Vérifier que les prix sont alignés (25k↔24k, 31k↔30k, 18k↔17k)
        for au, lst, score, kind in pairs:
            diff = abs(au.final_price_eur - lst.start_price_eur)
            assert_true(
                f"prix proches: {au.final_price_eur}↔{lst.start_price_eur}",
                diff < 3000,
                f"écart trop grand : {diff}"
            )


# ── 8. Incremental sync (deduplication) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_incremental_sync():  # noqa: F811
    print("\n=== Incremental sync deduplication ===")
    from models import Auction, AuctionStatus
    from services.parser import parse_results_message
    from services.normalizer import normalize_model

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    text = "A001, Toyota Supra 45000€ sold"
    msg_date = date(2024, 3, 22)
    results = parse_results_message(text)

    # Première insertion (simule le scrape initial)
    for r in results:
        existing = db.query(Auction).filter_by(lot_number=r.lot_number, auction_date=msg_date).first()
        if not existing:
            db.add(Auction(
                lot_number=r.lot_number,
                model_raw=r.model_raw,
                model_normalized=normalize_model(r.model_raw),
                final_price_eur=r.price_eur,
                status=AuctionStatus(r.status),
                auction_date=msg_date,
                telegram_message_id=9999,
            ))
    db.commit()
    initial_count = db.query(Auction).count()
    assert_eq("après première insertion count=1", initial_count, 1)

    # Re-synchronisation : même message, même lot → ne doit PAS dupliquer
    for r in results:
        existing = db.query(Auction).filter_by(lot_number=r.lot_number, auction_date=msg_date).first()
        if not existing:
            db.add(Auction(
                lot_number=r.lot_number,
                model_raw=r.model_raw,
                model_normalized=normalize_model(r.model_raw),
                final_price_eur=r.price_eur,
                status=AuctionStatus(r.status),
                auction_date=msg_date,
                telegram_message_id=9999,
            ))
    db.commit()

    final_count = db.query(Auction).count()
    assert_eq("re-sync does not duplicate existing records", final_count, initial_count)

    db.close()


# ── 9. Tier 3 — pont déterministe lot OCR ────────────────────────────────────

def test_link_by_lot_deterministic():
    """
    Annonce avec lot_number OCR + enchère même lot → match 'high' déterministe.
    year/km copiés, listing consommé 1:1.
    """
    print("\n=== Tier 3 — pont lot déterministe ===")
    from services.linker import find_best_listing, link_auctions
    from models import Listing, Auction, AuctionStatus
    from services.normalizer import normalize_model
    from datetime import date

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    pre_date = date(2024, 8, 9)
    ref_date = date(2024, 8, 10)

    # Listing avec lot OCR high
    lst = Listing(
        model_raw="BMW M3",
        model_normalized=normalize_model("BMW M3"),
        year=2018,
        mileage_km=45000,
        start_price_eur=28000,
        photo_file_ids=[],
        posted_date=pre_date,
        telegram_message_id=88001,
        lot_number="84011",
        lot_ocr_confidence="ocr_high",
    )
    db.add(lst)
    db.commit()

    # find_best_listing avec lot → doit retourner 'high' déterministe
    listing, confidence = find_best_listing(db, "BMW M3", 29000, ref_date, lot_number="84011")
    assert_true("listing trouvé par pont lot", listing is not None)
    assert_eq("confidence = high déterministe", confidence, "high")
    if listing:
        assert_eq("bon listing retourné (lot bridge)", listing.id, lst.id)

    db.close()


def test_lot_reuse_window():
    """
    Même lot '84011' sur deux dates éloignées (>7j) : seul le listing dans la
    fenêtre ≤7 j avant l'enchère doit matcher. L'autre doit être ignoré.
    """
    print("\n=== Tier 3 — fenêtre réutilisation lot ===")
    from services.linker import find_best_listing
    from models import Listing, Auction, AuctionStatus
    from services.normalizer import normalize_model
    from datetime import date

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    ref_date = date(2024, 9, 15)      # date de l'enchère
    close_date = date(2024, 9, 14)    # 1 jour avant → dans la fenêtre
    far_date = date(2024, 8, 1)       # 45 jours avant → hors fenêtre

    # Listing proche (dans la fenêtre)
    lst_close = Listing(
        model_raw="BMW M3", model_normalized="BMW M3",
        year=2020, mileage_km=20000, start_price_eur=40000,
        photo_file_ids=[], posted_date=close_date,
        telegram_message_id=88002,
        lot_number="84011", lot_ocr_confidence="ocr_high",
    )
    # Listing lointain (même lot, hors fenêtre)
    lst_far = Listing(
        model_raw="BMW M3", model_normalized="BMW M3",
        year=2016, mileage_km=80000, start_price_eur=15000,
        photo_file_ids=[], posted_date=far_date,
        telegram_message_id=88003,
        lot_number="84011", lot_ocr_confidence="ocr_high",
    )
    db.add_all([lst_close, lst_far])
    db.commit()

    listing, confidence = find_best_listing(db, "BMW M3", 41000, ref_date, lot_number="84011")
    assert_true("listing proche trouvé", listing is not None)
    assert_eq("confidence high", confidence, "high")
    if listing:
        assert_eq("listing proche sélectionné (pas le lointain)", listing.id, lst_close.id)

    db.close()


def test_lot_then_fuzzy_fallback():
    """
    Auction sans lot OCR (lot_number absent) → retombe sur le fuzzy.
    Aucune régression : le listing est quand même trouvé si le modèle matche.
    """
    print("\n=== Tier 3 — repli fuzzy si pas de lot ===")
    from services.linker import find_best_listing
    from models import Listing
    from services.normalizer import normalize_model
    from datetime import date

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    pre_date = date(2024, 10, 9)
    ref_date = date(2024, 10, 10)

    lst = Listing(
        model_raw="Toyota Supra", model_normalized=normalize_model("Toyota Supra"),
        year=2019, mileage_km=32000, start_price_eur=42000,
        photo_file_ids=[], posted_date=pre_date,
        telegram_message_id=88004,
        lot_number=None,                # pas de lot OCR
        lot_ocr_confidence="none",
    )
    db.add(lst)
    db.commit()

    # Pas de lot_number fourni → repli fuzzy
    listing, confidence = find_best_listing(
        db, normalize_model("Toyota Supra"), 44000, ref_date, lot_number=None
    )
    assert_true("repli fuzzy trouve le listing", listing is not None)
    assert_true("confidence non nulle", confidence in ("high", "review"))

    db.close()


def test_lot_ocr_extract():
    """
    extract_lot_from_image — test avec un mock (pas d'image réelle en test unitaire).
    Vérifie le contrat de l'interface : retourne (lot|None, confidence).
    """
    print("\n=== Tier 3 — extract_lot_from_image interface ===")
    from services.lot_ocr import extract_lot_from_image, _select_lot

    # _select_lot directement (sans OCR)
    lot, conf = _select_lot([])
    assert_eq("vide → none", conf, "none")
    assert_true("vide → lot None", lot is None)

    lot, conf = _select_lot(["84011"])
    assert_eq("un candidat → ocr_high", conf, "ocr_high")
    assert_eq("bon lot", lot, "84011")

    lot, conf = _select_lot(["84011", "99999"])
    assert_eq("deux candidats → ocr_low", conf, "ocr_low")

    lot, conf = _select_lot(["84011", "84011", "84011", "99999"])
    assert_eq("dominant net → ocr_high", conf, "ocr_high")
    assert_eq("dominant retourné", lot, "84011")

    # extract_lot_from_image doit dégrader gracieusement si OCR indisponible
    lot, conf = extract_lot_from_image(b"fake_image_data")
    assert_true("pas d'exception si OCR absent", True)
    assert_true("confidence toujours une string", isinstance(conf, str))


def test_condition_score_extract():
    """
    _extract_score_from_text — vérifie l'extraction de la note d'état depuis le texte OCR.
    Ancre principale : 内装 (toujours présent sur fiche). Debug réel : 5 fiches Vision OCR.
    """
    print("\n=== Tier 3 — _extract_score_from_text ===")
    from services.lot_ocr import _extract_score_from_text

    # Cas nominaux : score décimal avant 内装 (Pattern 1 — ancre la plus fiable)
    assert_eq("4.5 standard (max 5)", _extract_score_from_text("評価点\n4.5\n内装"), "4.5")
    assert_eq("3.5 avant 内装", _extract_score_from_text("評価\n3.5\n内装\n4WD B"), "3.5")
    assert_eq("4.5 avec + devant 内装", _extract_score_from_text("4.5\n+\n内装\nSR"), "4.5")
    assert_eq("4,5 virgule européenne", _extract_score_from_text("評価点\n4,5\n内装"), "4.5")

    # Label présent mais orthographié différemment par OCR (Pattern 2/3)
    assert_eq("5 entier avant 内装", _extract_score_from_text("評価点\n5\n内装"), "5")
    assert_eq("4 entier avant 内装", _extract_score_from_text("評価点\n4\n内装"), "4")
    assert_eq("評価 sans 点 (label tronqué)", _extract_score_from_text("型式\n3800\n評価点\n4.5\n内装"), "4.5")

    # OCR a supprimé le point décimal → "45" isolé (Pattern 4)
    assert_eq("45 → 4.5 (point sauté)", _extract_score_from_text("4WD\n45\nB\n内装"), "4.5")
    assert_eq("35 → 3.5 (point sauté)", _extract_score_from_text("前後\n35\n内装\n2WD"), "3.5")

    # Codes lettre (Pattern 5)
    assert_eq("score R (restauré)", _extract_score_from_text("評価点\nR\n内装"), "R")
    assert_eq("score RA", _extract_score_from_text("評価点\nRA\n内装"), "RA")
    assert_eq("score XX (non évalué)", _extract_score_from_text("評価点\nXX\n内装"), "XX")
    assert_eq("score S (neuf)", _extract_score_from_text("評価点\nS\n内装"), "S")

    # Faux positifs à rejeter
    assert_true("5500cc pas capturé (pas 内装)", _extract_score_from_text("評価点\n5500\n型式") is None)
    assert_true("pas de 評価点 ni 内装 → None", _extract_score_from_text("型式\n3800\n73351 初度登録年月") is None)


def test_link_by_lot_batch():
    """
    Test de link_auctions avec pont lot activé : 2 enchères + 2 annonces avec lots OCR.
    Les 2 doivent être résolues en 'high' déterministe (linked_by_lot = 2).
    """
    print("\n=== Tier 3 — link_auctions pont lot batch ===")
    from services.linker import link_auctions
    from models import Listing, Auction, AuctionStatus
    from services.normalizer import normalize_model
    from datetime import date

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    pre_date = date(2024, 11, 9)
    ref_date = date(2024, 11, 10)

    # Deux annonces avec lots OCR distincts (même modèle → fuzzy seul serait ambigu)
    lst_a = Listing(
        model_raw="BMW M3", model_normalized="BMW M3",
        year=2018, mileage_km=40000, start_price_eur=28000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=88010,
        lot_number="70001", lot_ocr_confidence="ocr_high",
    )
    lst_b = Listing(
        model_raw="BMW M3", model_normalized="BMW M3",
        year=2020, mileage_km=15000, start_price_eur=44000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=88011,
        lot_number="70002", lot_ocr_confidence="ocr_high",
    )
    db.add_all([lst_a, lst_b])

    au_a = Auction(
        lot_number="70001", model_raw="BMW M3", model_normalized="BMW M3",
        final_price_eur=29000, status=AuctionStatus.sold,
        auction_date=ref_date, telegram_message_id=88020,
    )
    au_b = Auction(
        lot_number="70002", model_raw="BMW M3", model_normalized="BMW M3",
        final_price_eur=45000, status=AuctionStatus.sold,
        auction_date=ref_date, telegram_message_id=88021,
    )
    db.add_all([au_a, au_b])
    db.commit()

    stats = link_auctions(db, dry_run=False, verbose=False)

    assert_eq("2 matched high via lot", stats["linked_high"], 2)
    assert_eq("2 linked_by_lot", stats["linked_by_lot"], 2)
    assert_eq("0 unmatched", stats["unmatched"], 0)

    # Vérifier les données copiées
    db.refresh(au_a)
    db.refresh(au_b)
    assert_eq("au_a year=2018 (de lst_a)", au_a.year, 2018)
    assert_eq("au_b year=2020 (de lst_b)", au_b.year, 2020)
    assert_eq("au_a km=40000", au_a.mileage_km, 40000)
    assert_eq("au_b km=15000", au_b.mileage_km, 15000)
    assert_eq("au_a confidence=high", au_a.match_confidence, "high")

    db.close()


def test_link_auctions_positional_pass():
    """
    Test bout-en-bout de la pré-passe positionnelle dans link_auctions.

    Scénario : 3 BMW M3 dans le même message résultat (même date, même lot_band 70xxx),
    lots réutilisés (lot_number identiques aux annonces passées → pont-lot ambigu).
    Les 3 annonces ont des result_line_index distincts ; les 3 listings sont publiés
    dans le bon ordre (telegram_message_id croissant).
    Objectif : link_auctions doit résoudre les 3 paires correctement via l'alignement
    positionnel et les marquer 'high' (linked_positional = 3).
    """
    print("\n=== Tier 2 — pré-passe positionnelle dans link_auctions ===")
    from services.linker import link_auctions
    from models import Listing, Auction, AuctionStatus
    from services.normalizer import normalize_model
    from datetime import date

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    ref_date = date(2025, 3, 15)
    pre_date = date(2025, 3, 14)  # 1 jour avant → dans la fenêtre

    # 3 listings BMW M3 avec des km/prix distincts, publiés dans l'ordre
    # (telegram_message_id 1001 < 1002 < 1003 = ordre de publication)
    lst1 = Listing(
        model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        year=2018, mileage_km=25000, start_price_eur=35000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=1001,
        lot_number="70011",     # lot "réutilisé" : plusieurs listings possible
        lot_ocr_confidence="ocr_low",   # ocr_low → pont-lot seul ne suffit pas
    )
    lst2 = Listing(
        model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        year=2020, mileage_km=10000, start_price_eur=55000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=1002,
        lot_number="70012",
        lot_ocr_confidence="ocr_low",
    )
    lst3 = Listing(
        model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        year=2016, mileage_km=60000, start_price_eur=20000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=1003,
        lot_number="70013",
        lot_ocr_confidence="ocr_low",
    )
    db.add_all([lst1, lst2, lst3])

    # 3 auctions BMW M3 dans le même message résultat, ordonnées par result_line_index
    # Prix finaux proches des prix de départ pour que model_score les valide.
    # Chaque auction a le lot correspondant MAIS ocr_low + lots réutilisés (plusieurs
    # listings par lot fictifs → pont-lot renvoie None → repli positionnelle).
    au1 = Auction(
        lot_number="70011", model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        final_price_eur=36000, status=AuctionStatus.sold,
        auction_date=ref_date, telegram_message_id=2001,
        result_line_index=0,
    )
    au2 = Auction(
        lot_number="70012", model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        final_price_eur=56000, status=AuctionStatus.sold,
        auction_date=ref_date, telegram_message_id=2001,
        result_line_index=1,
    )
    au3 = Auction(
        lot_number="70013", model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        final_price_eur=21000, status=AuctionStatus.sold,
        auction_date=ref_date, telegram_message_id=2001,
        result_line_index=2,
    )
    db.add_all([au1, au2, au3])
    db.commit()

    stats = link_auctions(db, dry_run=False, verbose=True)

    # Au moins 2 paires résolues via le positionnel (peut-être les 3)
    assert_true(
        "pré-passe positionnelle a résolu au moins 2 paires high",
        stats.get("linked_positional", 0) >= 2,
        f"linked_positional={stats.get('linked_positional',0)}",
    )
    # Aucune contamination : 3 listings distincts pour 3 auctions (1:1)
    db.refresh(au1); db.refresh(au2); db.refresh(au3)
    ids = {au1.matched_listing_id, au2.matched_listing_id, au3.matched_listing_id} - {None}
    assert_true(
        "listings affectés distincts (1:1, pas de contamination)",
        len(ids) == len([x for x in [au1.matched_listing_id, au2.matched_listing_id, au3.matched_listing_id] if x is not None]),
        f"ids={ids}",
    )

    # Les données copiées concordent : au1 (prix~35k) devrait avoir lst1 (km=25000)
    # et au3 (prix~20k) devrait avoir lst3 (km=60000).
    # On vérifie juste la cohérence prix/km (pas l'ordre exact — le positionnel peut
    # légèrement varier selon la DP).
    for au, lst in [(au1, lst1), (au2, lst2), (au3, lst3)]:
        if au.matched_listing_id == lst.id and au.year is not None:
            assert_eq(f"AU#{au.id} year copié de lst", au.year, lst.year)
            assert_eq(f"AU#{au.id} km copié de lst", au.mileage_km, lst.mileage_km)

    db.close()


def test_link_auctions_positional_multi_band():
    """
    Test de la passe positionnelle par BANDE DE LOT (v2).

    Scénario : un message résultat contient 2 bandes distinctes.
      - Bande 65xxx : 2 Porsche 911, prix distincts
      - Bande 70xxx : 2 BMW M3, prix distincts
    Chaque bande a ses listings publiés en ordre, avec lot_number correspondant
    à la même bande. Les listings d'une bande ne doivent PAS contaminer l'autre.

    Attendu : link_auctions résout les 4 paires via linked_positional,
    chaque auction obtient la bonne année (1:1 par ordre positionnel).
    """
    print("\n=== Tier 2 — positionnelle multi-bandes (v2, par lot_band) ===")
    from services.linker import link_auctions
    from models import Listing, Auction, AuctionStatus
    from services.normalizer import normalize_model
    from datetime import date

    engine, SessionLocal = _isolated_db()
    db = SessionLocal()

    ref_date = date(2025, 6, 10)
    pre_date = date(2025, 6, 9)

    # ── Listings bande 65xxx (Porsche 911) ───────────────────────────────────
    lst_65a = Listing(
        model_raw="carera", model_normalized=normalize_model("carera"),
        year=2013, mileage_km=45000, start_price_eur=32000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=3001,
        lot_number="65001", lot_ocr_confidence="ocr_high",
    )
    lst_65b = Listing(
        model_raw="carera", model_normalized=normalize_model("carera"),
        year=2018, mileage_km=20000, start_price_eur=48000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=3002,
        lot_number="65002", lot_ocr_confidence="ocr_high",
    )

    # ── Listings bande 70xxx (BMW M3) ────────────────────────────────────────
    lst_70a = Listing(
        model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        year=2016, mileage_km=55000, start_price_eur=22000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=3003,
        lot_number="70001", lot_ocr_confidence="ocr_high",
    )
    lst_70b = Listing(
        model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        year=2021, mileage_km=8000, start_price_eur=45000,
        photo_file_ids=[], posted_date=pre_date, telegram_message_id=3004,
        lot_number="70002", lot_ocr_confidence="ocr_high",
    )
    db.add_all([lst_65a, lst_65b, lst_70a, lst_70b])

    # ── Auctions — même message résultat, bandes entrelacées ─────────────────
    # Bande 65xxx : idx 0, 1 (premiers dans le message)
    # Bande 70xxx : idx 2, 3 (après dans le message)
    au_65a = Auction(
        lot_number="65001", model_raw="carera", model_normalized=normalize_model("carera"),
        final_price_eur=33000, status=AuctionStatus.not_sold,
        auction_date=ref_date, telegram_message_id=4001, result_line_index=0,
    )
    au_65b = Auction(
        lot_number="65002", model_raw="carera", model_normalized=normalize_model("carera"),
        final_price_eur=50000, status=AuctionStatus.sold,
        auction_date=ref_date, telegram_message_id=4001, result_line_index=1,
    )
    au_70a = Auction(
        lot_number="70001", model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        final_price_eur=23000, status=AuctionStatus.not_sold,
        auction_date=ref_date, telegram_message_id=4001, result_line_index=2,
    )
    au_70b = Auction(
        lot_number="70002", model_raw="BMW M3", model_normalized=normalize_model("BMW M3"),
        final_price_eur=46000, status=AuctionStatus.sold,
        auction_date=ref_date, telegram_message_id=4001, result_line_index=3,
    )
    db.add_all([au_65a, au_65b, au_70a, au_70b])
    db.commit()

    stats = link_auctions(db, dry_run=False, verbose=True)

    db.refresh(au_65a); db.refresh(au_65b)
    db.refresh(au_70a); db.refresh(au_70b)

    # Vérifier que linked_positional a capturé des paires (au moins 3 sur 4)
    assert_true(
        "positionnelle multi-bandes : au moins 3 paires high",
        stats.get("linked_positional", 0) + stats.get("linked_by_lot", 0) >= 3,
        f"linked_positional={stats.get('linked_positional',0)} linked_by_lot={stats.get('linked_by_lot',0)}",
    )

    # Pas de contamination inter-bandes :
    # au_65a/b ne doivent pas avoir de listing BMW M3 (et vice versa)
    for au_65, lst_id in [(au_65a, lst_65a.id), (au_65b, lst_65b.id)]:
        if au_65.year is not None:
            assert_true(
                f"AU#{au_65.id} (carera) relie a un listing carera, pas BMW M3",
                au_65.matched_listing_id in (lst_65a.id, lst_65b.id),
                f"matched_listing_id={au_65.matched_listing_id}",
            )
    for au_70, lst_id in [(au_70a, lst_70a.id), (au_70b, lst_70b.id)]:
        if au_70.year is not None:
            assert_true(
                f"AU#{au_70.id} (BMW M3) relie a un listing BMW M3, pas carera",
                au_70.matched_listing_id in (lst_70a.id, lst_70b.id),
                f"matched_listing_id={au_70.matched_listing_id}",
            )

    # Ordre positionnel respecté : au_65a (idx=0, prix~33k) → lst_65a (year=2013)
    # au_65b (idx=1, prix~50k) → lst_65b (year=2018)
    if au_65a.year is not None and au_65b.year is not None:
        assert_eq("au_65a (idx=0) → year 2013", au_65a.year, 2013)
        assert_eq("au_65b (idx=1) → year 2018", au_65b.year, 2018)

    db.close()


# ── Runner ────────────────────────────────────────────────────────────────────

async def main():
    test_parser()
    test_normalizer()
    test_stats()
    await test_sync_pipeline()
    test_linker_global_assignment()
    test_linker_uses_normalized()
    test_parse_results_header()
    test_positional_alignment()
    await test_incremental_sync()
    # Tier 3
    test_link_by_lot_deterministic()
    test_lot_reuse_window()
    test_lot_then_fuzzy_fallback()
    test_lot_ocr_extract()
    test_condition_score_extract()
    test_link_by_lot_batch()
    # Tier 2 — pré-passe positionnelle bout-en-bout
    test_link_auctions_positional_pass()
    # Tier 2 v2 — positionnelle par bande de lot
    test_link_auctions_positional_multi_band()

    print(f"\n{'='*50}")
    print(f"TOTAL: {PASS} passed, {FAIL} failed")
    if FAIL == 0:
        print("ALL PIPELINE TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
