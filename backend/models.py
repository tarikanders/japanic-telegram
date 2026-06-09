import enum
from sqlalchemy import Column, Integer, String, Float, Date, BigInteger, Enum, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class AuctionStatus(str, enum.Enum):
    sold = "sold"
    not_sold = "not_sold"
    canceled = "canceled"


class Auction(Base):
    __tablename__ = "auctions"

    id = Column(Integer, primary_key=True, index=True)
    lot_number = Column(String, index=True)
    model_raw = Column(Text)
    model_normalized = Column(String, index=True)
    year = Column(Integer)
    mileage_km = Column(Integer, index=True)
    start_price_eur = Column(Integer)
    final_price_eur = Column(Integer, nullable=True)
    status = Column(Enum(AuctionStatus), index=True)
    auction_date = Column(Date, index=True)
    telegram_message_id = Column(BigInteger, nullable=True)  # NOT unique: multiple auctions per result message
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Fiabilité du matching annonce↔résultat ---
    # "high"   : un listing se détache nettement (candidat unique ou écart de score net)
    #            → year/km/start_price copiés et dignes de confiance.
    # "review" : plusieurs listings également plausibles (modèle générique, fenêtre dense)
    #            → year/km laissés NULL ; matched_listing_id = meilleure DEVINETTE à vérifier.
    # NULL     : aucun listing compatible trouvé (rien à vérifier).
    match_confidence = Column(String, index=True, nullable=True)
    matched_listing_id = Column(Integer, nullable=True)  # traçabilité : d'où viennent year/km

    # --- Signaux Tier 2 (capturés lors du re-scrape enrichi) ---
    raw_text = Column(Text, nullable=True)               # texte brut du message Telegram
    result_line_index = Column(Integer, nullable=True)   # ordinal du lot dans son message résultat
    grouped_id = Column(BigInteger, nullable=True)       # Telegram album grouped_id

    # --- Tier 3 — dénormalisé depuis le Listing relié (même logique que year/mileage_km) ---
    # condition_score : note d'état copiée depuis listing.condition_score lors du match "high".
    # Ex : "4.5", "5", "R", "RA". NULL si le listing n'avait pas de note ou pas de match high.
    condition_score = Column(String, nullable=True)
    # variant : finition du véhicule extraite du model_raw (ex : "GTS", "GT4", "Turbo S", "S").
    # NULL si la finition n'est pas détectable ou déjà encodée dans model_normalized.
    variant = Column(String, nullable=True)

    listing = relationship("Listing", back_populates="auction", uselist=False)


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    model_raw = Column(Text)
    model_normalized = Column(String, index=True)   # normalisé via normalizer.py
    year = Column(Integer)
    mileage_km = Column(Integer)
    start_price_eur = Column(Integer)
    photo_file_ids = Column(JSON, default=list)
    posted_date = Column(Date)
    linked_auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=True)
    telegram_message_id = Column(BigInteger, unique=True, nullable=True)

    # --- Signaux Tier 2 ---
    raw_text = Column(Text, nullable=True)
    grouped_id = Column(BigInteger, nullable=True)

    # --- Tier 3 : pont déterministe par numéro de lot (OCR fiche-rapport) ---
    # lot_number       : n° de lot lu par OCR sur la photo de la fiche-rapport.
    # lot_ocr_confidence : 'ocr_high' (lot net/unique), 'ocr_low' (ambigu), 'none'.
    # report_photo_index : index (0-based) de la photo-fiche dans l'album Telegram.
    # condition_score  : note d'état du véhicule lue sur la fiche (ex : "4.5", "5", "R", "RA").
    # variant          : finition extraite du model_raw (ex : "GTS", "GT4", "Turbo S").
    lot_number = Column(String, index=True, nullable=True)
    lot_ocr_confidence = Column(String, nullable=True)
    report_photo_index = Column(Integer, nullable=True)
    condition_score = Column(String, nullable=True)
    variant = Column(String, nullable=True)

    auction = relationship("Auction", back_populates="listing")


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    id = Column(Integer, primary_key=True)
    last_message_id = Column(BigInteger, default=0)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    records_synced = Column(Integer, default=0)
    status = Column(String, default="idle")
    error_message = Column(Text, nullable=True)


class ArchivedVehicle(Base):
    __tablename__ = "archive"

    id = Column(Integer, primary_key=True)
    model_name = Column(String, nullable=False)
    generation_code = Column(String, nullable=True)
    year_start = Column(Integer, nullable=True)
    year_end = Column(Integer, nullable=True)
    phases = Column(JSON, default=list)
    variants = Column(JSON, default=list)
    lbc_price_eur = Column(Integer, nullable=True)
    bid_price_yen = Column(Integer, nullable=True)
    bid_price_eur = Column(Integer, nullable=True)
    auction_model_key = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    archive_status = Column(String, default="reference")  # bought | passed | reference
    archived_at = Column(DateTime(timezone=True), server_default=func.now())


class WatchlistEntry(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True)
    model_name = Column(String, nullable=False)
    generation_code = Column(String, nullable=True)
    year_start = Column(Integer, nullable=True)
    year_end = Column(Integer, nullable=True)
    phases = Column(JSON, default=list)    # [{phase, year_from, year_to, note?}]
    variants = Column(JSON, default=list)  # [{name, hp, note?}]
    lbc_price_eur = Column(Integer, nullable=True)
    lbc_price_note = Column(String, nullable=True)
    bid_min = Column(Integer, nullable=True)
    bid_max = Column(Integer, nullable=True)
    bid_unit = Column(String, default="yen")
    lbc_query = Column(String, nullable=True)
    lbc_filters = Column(JSON, nullable=True)
    auction_model_key = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
