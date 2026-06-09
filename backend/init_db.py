"""Run once to initialize database tables in production."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base
from models import Auction, Listing, SyncCheckpoint  # noqa: F401 — imports trigger table registration

Base.metadata.create_all(bind=engine)
print("Database tables created successfully.")

from sqlalchemy import text
with engine.connect() as conn:
    if "postgresql" in str(engine.url):
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_auctions_model ON auctions (model_normalized)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_auctions_mileage ON auctions (mileage_km)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_auctions_date ON auctions (auction_date)"))
        conn.commit()
        print("PostgreSQL indexes created.")
    else:
        print("SQLite: indexes handled by SQLAlchemy model definitions.")
