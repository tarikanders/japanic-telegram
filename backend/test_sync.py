"""Run after telegram_login.py to verify sync works."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

async def main():
    from services.scraper import run_sync

    print("Testing Telegram sync (fetching last 20 messages)...")
    
    import os
    original_env = os.environ.copy()
    
    logs = []
    async def log_cb(msg):
        logs.append(msg)
        print(f"  {msg}")

    result = await run_sync(log_callback=log_cb)
    
    if "error" in result:
        print(f"\nERROR: {result['error']}")
        return False
    
    print(f"\nSync result: {result}")
    
    # Check what was imported
    from database import SessionLocal
    from models import Auction, Listing
    db = SessionLocal()
    auction_count = db.query(Auction).count()
    listing_count = db.query(Listing).count()
    db.close()
    
    print(f"\nDB state: {auction_count} auctions, {listing_count} listings")
    print("SUCCESS: Telegram sync working!")
    return True

if __name__ == "__main__":
    asyncio.run(main())
