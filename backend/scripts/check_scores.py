import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))
from database import SessionLocal
from models import Listing

db = SessionLocal()
rows = db.query(Listing).order_by(Listing.id).limit(15).all()
print(f"{'#':>6}  {'lot':>8}  {'conf':>10}  {'score':>6}  modele")
print("-" * 70)
for r in rows:
    lot = r.lot_number or "-"
    conf = r.lot_ocr_confidence or "-"
    score = r.condition_score or "-"
    model = (r.model_raw or "")[:35]
    print(f"#{r.id:5d}  {lot:>8}  {conf:>10}  {score:>6}  {model}")
total = db.query(Listing).count()
with_score = db.query(Listing).filter(Listing.condition_score.isnot(None)).count()
with_lot = db.query(Listing).filter(Listing.lot_number.isnot(None)).count()
print(f"\nTotal listings : {total}")
print(f"Avec lot OCR   : {with_lot} ({with_lot*100//max(1,total)}%)")
print(f"Avec score     : {with_score} ({with_score*100//max(1,total)}%)")
db.close()
