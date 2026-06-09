"""
Provides an in-process TestClient with a pre-seeded fixture DB for API tests.
No subprocess or external server needed.
"""
import os
import pytest
from datetime import date
from pathlib import Path

FIXTURE_DB_PATH = "/tmp/test_api_fixture.db"


def _seed_fixture_db(session_factory):
    from models import Auction, AuctionStatus

    records = [
        Auction(lot_number="10001", model_raw="BMW M3", model_normalized="BMW M3",
                year=2015, mileage_km=45000, final_price_eur=28000,
                status=AuctionStatus.sold, auction_date=date(2023, 1, 10)),
        Auction(lot_number="10002", model_raw="BMW M3", model_normalized="BMW M3",
                year=2016, mileage_km=52000, final_price_eur=31000,
                status=AuctionStatus.sold, auction_date=date(2023, 2, 15)),
        Auction(lot_number="10003", model_raw="BMW M3", model_normalized="BMW M3",
                year=2014, mileage_km=60000, final_price_eur=25000,
                status=AuctionStatus.sold, auction_date=date(2023, 3, 20)),
        Auction(lot_number="10004", model_raw="BMW M5", model_normalized="BMW M5",
                year=2013, mileage_km=35000, final_price_eur=22000,
                status=AuctionStatus.sold, auction_date=date(2023, 1, 25)),
        Auction(lot_number="10005", model_raw="BMW M5", model_normalized="BMW M5",
                year=2014, mileage_km=40000, final_price_eur=27000,
                status=AuctionStatus.sold, auction_date=date(2023, 4, 5)),
        Auction(lot_number="10006", model_raw="Porsche 911", model_normalized="Porsche 911 Carrera",
                year=2017, mileage_km=32000, final_price_eur=55000,
                status=AuctionStatus.sold, auction_date=date(2023, 2, 28)),
        Auction(lot_number="10007", model_raw="Porsche 911", model_normalized="Porsche 911 Carrera",
                year=2018, mileage_km=28000, final_price_eur=60000,
                status=AuctionStatus.not_sold, auction_date=date(2023, 5, 10)),
        Auction(lot_number="10008", model_raw="Mercedes C63 AMG", model_normalized="Mercedes C63 AMG",
                year=2016, mileage_km=50000, final_price_eur=35000,
                status=AuctionStatus.sold, auction_date=date(2023, 3, 15)),
        Auction(lot_number="10009", model_raw="Mercedes C63 AMG", model_normalized="Mercedes C63 AMG",
                year=2015, mileage_km=65000, final_price_eur=29000,
                status=AuctionStatus.sold, auction_date=date(2023, 6, 1)),
        Auction(lot_number="10010", model_raw="Audi RS6", model_normalized="Audi RS6",
                year=2017, mileage_km=55000, final_price_eur=45000,
                status=AuctionStatus.not_sold, auction_date=date(2023, 7, 10)),
    ]
    db = session_factory()
    try:
        db.add_all(records)
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def api_client():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient

    if Path(FIXTURE_DB_PATH).exists():
        Path(FIXTURE_DB_PATH).unlink()

    # Import order matters: database.py may already be bound to test_pipeline.db
    # (set by test_pipeline.py line 17). We bypass that via dependency_overrides.
    from database import Base, get_db
    import main as _main

    fixture_engine = create_engine(
        f"sqlite:///{FIXTURE_DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=fixture_engine)
    FixtureSession = sessionmaker(bind=fixture_engine, autoflush=False, autocommit=False)

    _seed_fixture_db(FixtureSession)

    def override_get_db():
        db = FixtureSession()
        try:
            yield db
        finally:
            db.close()

    _main.app.dependency_overrides[get_db] = override_get_db

    with TestClient(_main.app) as client:
        yield client

    _main.app.dependency_overrides.pop(get_db, None)

    if Path(FIXTURE_DB_PATH).exists():
        Path(FIXTURE_DB_PATH).unlink()
