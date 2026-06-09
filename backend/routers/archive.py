from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database import get_db
from models import ArchivedVehicle

router = APIRouter(prefix="/api/archive", tags=["archive"])


class ArchiveCreate(BaseModel):
    model_name: str
    generation_code: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    phases: Optional[List] = []
    variants: Optional[List] = []
    lbc_price_eur: Optional[int] = None
    bid_price_yen: Optional[int] = None
    bid_price_eur: Optional[int] = None
    auction_model_key: Optional[str] = None
    notes: Optional[str] = None
    archive_status: Optional[str] = "reference"


class ArchivePatch(BaseModel):
    notes: Optional[str] = None
    archive_status: Optional[str] = None


@router.get("")
def list_archive(db: Session = Depends(get_db)):
    entries = db.query(ArchivedVehicle).order_by(ArchivedVehicle.archived_at.desc()).all()
    return [_serialize(e) for e in entries]


@router.post("", status_code=201)
def add_to_archive(body: ArchiveCreate, db: Session = Depends(get_db)):
    entry = ArchivedVehicle(**body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _serialize(entry)


@router.patch("/{entry_id}")
def update_archive_entry(entry_id: int, body: ArchivePatch, db: Session = Depends(get_db)):
    entry = db.query(ArchivedVehicle).filter(ArchivedVehicle.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    if body.notes is not None:
        entry.notes = body.notes
    if body.archive_status is not None:
        entry.archive_status = body.archive_status
    db.commit()
    db.refresh(entry)
    return _serialize(entry)


@router.delete("/{entry_id}", status_code=204)
def delete_archive_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(ArchivedVehicle).filter(ArchivedVehicle.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()


def _serialize(e: ArchivedVehicle) -> dict:
    return {
        "id": e.id,
        "model_name": e.model_name,
        "generation_code": e.generation_code,
        "year_start": e.year_start,
        "year_end": e.year_end,
        "phases": e.phases or [],
        "variants": e.variants or [],
        "lbc_price_eur": e.lbc_price_eur,
        "bid_price_yen": e.bid_price_yen,
        "bid_price_eur": e.bid_price_eur,
        "auction_model_key": e.auction_model_key,
        "notes": e.notes,
        "archive_status": e.archive_status,
        "archived_at": e.archived_at.isoformat() if e.archived_at else None,
    }
