"""
Dérivation de la phase génération d'une voiture depuis les données curées (WatchlistEntry).

La phase (ex : "Phase 2 — 997.2 (2008-2012)") est calculée à la demande à partir de :
  - WatchlistEntry.auction_model_key  (clé de liaison, ex : "911", "Cayenne")
  - WatchlistEntry.phases             (JSON : [{phase, year_from, year_to, note?}])
  - WatchlistEntry.generation_code    (ex : "997", "958")

N'ajoute AUCUNE colonne DB : zéro migration requise.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def derive_phase(db: "Session", model_normalized: Optional[str], year: Optional[int]) -> Optional[dict]:
    """
    Retourne un dict décrivant la phase du véhicule, ou None.

    Exemple de retour :
        {
            "phase": 2,
            "year_from": 2008,
            "year_to": 2012,
            "generation_code": "997",
            "note": "S 385ch"   # optionnel
        }

    Retourne None si :
      - model_normalized ou year sont None,
      - aucune entrée WatchlistEntry ne correspond,
      - l'année est hors des bandes connues.
    """
    if not model_normalized or not year:
        return None

    from models import WatchlistEntry  # import local pour éviter les cycles

    # Chercher l'entrée watchlist dont auction_model_key est contenu dans model_normalized
    all_entries = (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.auction_model_key.isnot(None))
        .all()
    )

    matched_entry = None
    for entry in all_entries:
        key = (entry.auction_model_key or "").strip().lower()
        if key and key in model_normalized.lower():
            matched_entry = entry
            break

    if not matched_entry:
        return None

    phases = matched_entry.phases or []
    if not phases:
        return None

    for band in phases:
        y_from = band.get("year_from")
        y_to = band.get("year_to")
        if y_from is not None and y_to is not None and y_from <= year <= y_to:
            result: dict = {
                "phase": band.get("phase"),
                "year_from": y_from,
                "year_to": y_to,
                "generation_code": matched_entry.generation_code,
            }
            note = band.get("note")
            if note:
                result["note"] = note
            return result

    return None
