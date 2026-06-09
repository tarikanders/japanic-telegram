"""
Tests unitaires pour services/linker.py — focalisés sur _pick_lot_candidate.

Utilise des objets factices (SimpleNamespace) : aucune DB requise.
Couvre les cas essentiels :
  - Lot unique + modèle confirme → sélectionné
  - Lot ré-utilisé, modèles différents → choisit celui dont le modèle matche
  - Lot ré-utilisé, même modèle, dates différentes → choisit le plus récent (plus proche avant l'enchère)
  - Lot ré-utilisé, même modèle, même date → ambigu → None
  - ocr_low + modèle confirme → accepté
  - ocr_low + modèle ne confirme pas → repli ocr_high strict (ou None si pas de high unique)
"""
import sys
import os
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.linker import _pick_lot_candidate


def _make_listing(
    model_norm: str,
    model_raw: str = "",
    posted_date: date = None,
    ocr_confidence: str = "ocr_high",
) -> SimpleNamespace:
    """Crée un listing factice avec les champs utilisés par _pick_lot_candidate."""
    return SimpleNamespace(
        model_normalized=model_norm,
        model_raw=model_raw or model_norm,
        posted_date=posted_date,
        lot_ocr_confidence=ocr_confidence,
        condition_score=None,
    )


# ── Cas 1 : lot unique, modèle confirme ──────────────────────────────────────

def test_single_candidate_model_matches():
    """Un seul candidat dont le modèle matche → retourné sans ambiguïté."""
    auction_model = "BMW M3"
    lst = _make_listing("BMW M3", posted_date=date(2025, 3, 10))
    result = _pick_lot_candidate(auction_model, [lst])
    assert result is lst


def test_single_candidate_model_mismatch_ocr_high():
    """Un seul candidat ocr_high dont le modèle NE matche PAS → repli strict → retourné (ocr_high unique)."""
    auction_model = "BMW M3"
    lst = _make_listing("Porsche 911", posted_date=date(2025, 3, 10), ocr_confidence="ocr_high")
    result = _pick_lot_candidate(auction_model, [lst])
    # Aucun modèle fort mais 1 ocr_high → retourné (ancienne règle de sécurité)
    assert result is lst


# ── Cas 2 : lot ré-utilisé, modèles différents ───────────────────────────────

def test_reused_lot_different_models_picks_matching():
    """Lot ré-utilisé : 2 candidats, modèles différents → prend celui dont le modèle matche."""
    auction_model = "BMW M3"
    lst_match = _make_listing("BMW M3", posted_date=date(2025, 3, 10))
    lst_other = _make_listing("Porsche 911", posted_date=date(2025, 3, 9))
    result = _pick_lot_candidate(auction_model, [lst_match, lst_other])
    assert result is lst_match


def test_reused_lot_different_models_no_match_returns_none():
    """Lot ré-utilisé : 2 candidats mais aucun modèle ne matche → None (sauf si unique ocr_high)."""
    auction_model = "BMW M3"
    lst_a = _make_listing("Porsche 911", posted_date=date(2025, 3, 10), ocr_confidence="ocr_low")
    lst_b = _make_listing("Audi RS6", posted_date=date(2025, 3, 9), ocr_confidence="ocr_low")
    result = _pick_lot_candidate(auction_model, [lst_a, lst_b])
    # Aucun modèle fort, 0 ocr_high → None
    assert result is None


# ── Cas 3 : lot ré-utilisé, même modèle, dates différentes ───────────────────

def test_reused_lot_same_model_different_dates_picks_most_recent():
    """Lot ré-utilisé, même modèle, dates différentes → choisit le plus proche (date max)."""
    auction_model = "BMW M3"
    lst_old = _make_listing("BMW M3", posted_date=date(2025, 1, 5))
    lst_new = _make_listing("BMW M3", posted_date=date(2025, 3, 10))
    result = _pick_lot_candidate(auction_model, [lst_old, lst_new])
    assert result is lst_new


# ── Cas 4 : lot ré-utilisé, même modèle, même date → ambigu ─────────────────

def test_reused_lot_same_model_same_date_returns_none():
    """Lot ré-utilisé, même modèle, même posted_date → ambigu → None."""
    auction_model = "BMW M3"
    lst_a = _make_listing("BMW M3", posted_date=date(2025, 3, 10))
    lst_b = _make_listing("BMW M3", posted_date=date(2025, 3, 10))
    result = _pick_lot_candidate(auction_model, [lst_a, lst_b])
    assert result is None


# ── Cas 5 : ocr_low accepté si modèle confirme ───────────────────────────────

def test_ocr_low_accepted_when_model_confirms():
    """ocr_low seul, modèle confirme → accepté (double signal lot+modèle)."""
    auction_model = "BMW M3"
    lst = _make_listing("BMW M3", posted_date=date(2025, 3, 10), ocr_confidence="ocr_low")
    result = _pick_lot_candidate(auction_model, [lst])
    assert result is lst


def test_ocr_low_rejected_when_model_does_not_confirm():
    """ocr_low, modèle ne matche pas, aucun ocr_high disponible → None."""
    auction_model = "BMW M3"
    lst = _make_listing("Porsche 911", posted_date=date(2025, 3, 10), ocr_confidence="ocr_low")
    result = _pick_lot_candidate(auction_model, [lst])
    assert result is None


def test_ocr_low_falls_back_to_single_ocr_high():
    """ocr_low sans modèle fort, mais 1 ocr_high disponible → repli strict → retourné."""
    auction_model = "BMW M3"
    lst_low = _make_listing("Porsche 911", posted_date=date(2025, 3, 10), ocr_confidence="ocr_low")
    lst_high = _make_listing("Ferrari", posted_date=date(2025, 3, 9), ocr_confidence="ocr_high")
    result = _pick_lot_candidate(auction_model, [lst_low, lst_high])
    # Aucun modèle fort → repli strict : 1 seul ocr_high → retourné
    assert result is lst_high


# ── Cas 6 : liste vide ────────────────────────────────────────────────────────

def test_empty_candidates_returns_none():
    result = _pick_lot_candidate("BMW M3", [])
    assert result is None


# ── Tests _align_session — min_coverage_ratio ─────────────────────────────────

from datetime import date as _date
from services.linker import _align_session, MODEL_MIN_SCORE


def _make_result(auction, model_norm, price, d, idx):
    """Tuple attendu par _align_session (côté résultats)."""
    return (auction, model_norm, price, d, idx)


def _make_lst_tuple(listing, model_norm, price, d):
    """Tuple attendu par _align_session (côté annonces)."""
    return (listing, model_norm, price, d)


def test_align_session_default_coverage_accepts_half():
    """
    Avec min_coverage_ratio=0.5 (défaut), 2/4 paires alignées → accepté.
    """
    from types import SimpleNamespace
    ref = _date(2025, 3, 15)
    pre = _date(2025, 3, 14)

    # 4 résultats BMW M3
    results = [
        _make_result(SimpleNamespace(id=i), "BMW M3", 30000 + i * 5000, ref, i)
        for i in range(4)
    ]
    # 4 listings BMW M3 — même modèle, publication ordonnée
    listings = [
        _make_lst_tuple(SimpleNamespace(id=10 + i), "BMW M3", 28000 + i * 5000, pre)
        for i in range(4)
    ]

    pairs = _align_session(results, listings)  # min_coverage_ratio=0.5 par défaut
    # 4 résultats, 4 listings, modèles identiques → DP aligne les 4
    assert len(pairs) >= 2, f"Attendu >=2 paires, obtenu {len(pairs)}"


def test_align_session_strict_coverage_rejects_partial():
    """
    Avec min_coverage_ratio=0.8, si seulement 2/5 paires (40%) passent le seuil
    de score modèle (les 3 autres n'ont aucun listing compatible), la session
    est rejetée ([] retourné).
    """
    from types import SimpleNamespace
    ref = _date(2025, 3, 15)
    pre = _date(2025, 3, 14)

    # 5 résultats : 2 BMW M3 + 3 Porsche 911
    results = [
        _make_result(SimpleNamespace(id=1), "BMW M3", 35000, ref, 0),
        _make_result(SimpleNamespace(id=2), "BMW M3", 40000, ref, 1),
        _make_result(SimpleNamespace(id=3), "Porsche 911", 60000, ref, 2),
        _make_result(SimpleNamespace(id=4), "Porsche 911", 65000, ref, 3),
        _make_result(SimpleNamespace(id=5), "Porsche 911", 70000, ref, 4),
    ]
    # Listings : 2 BMW M3 seulement — pas de Porsche 911 → 2/5 = 40% alignables
    listings = [
        _make_lst_tuple(SimpleNamespace(id=10), "BMW M3", 33000, pre),
        _make_lst_tuple(SimpleNamespace(id=11), "BMW M3", 38000, pre),
    ]

    pairs = _align_session(results, listings, min_coverage_ratio=0.8)
    # 2/5 < 80% → rejeté
    assert pairs == [], f"Attendu [] (coverage trop faible), obtenu {len(pairs)} paires"


def test_align_session_strict_coverage_accepts_full():
    """
    Avec min_coverage_ratio=0.8, si 5/5 paires s'alignent (100%), la session
    est acceptée.
    """
    from types import SimpleNamespace
    ref = _date(2025, 3, 15)
    pre = _date(2025, 3, 14)

    model = "BMW M3"
    results = [
        _make_result(SimpleNamespace(id=i), model, 30000 + i * 3000, ref, i)
        for i in range(5)
    ]
    listings = [
        _make_lst_tuple(SimpleNamespace(id=10 + i), model, 29000 + i * 3000, pre)
        for i in range(5)
    ]

    pairs = _align_session(results, listings, min_coverage_ratio=0.8)
    assert len(pairs) == 5, f"Attendu 5 paires, obtenu {len(pairs)}"


def test_align_session_boundary_exact_threshold():
    """
    Avec min_coverage_ratio=0.8, 4/5 paires (80%) → ceil(5*0.8)=4 → accepté.
    """
    from types import SimpleNamespace
    ref = _date(2025, 3, 15)
    pre = _date(2025, 3, 14)

    # 5 résultats : 4 BMW M3 + 1 Porsche 911 sans listing
    results = [
        _make_result(SimpleNamespace(id=1), "BMW M3", 30000, ref, 0),
        _make_result(SimpleNamespace(id=2), "BMW M3", 35000, ref, 1),
        _make_result(SimpleNamespace(id=3), "BMW M3", 40000, ref, 2),
        _make_result(SimpleNamespace(id=4), "BMW M3", 45000, ref, 3),
        _make_result(SimpleNamespace(id=5), "Porsche 911", 70000, ref, 4),
    ]
    listings = [
        _make_lst_tuple(SimpleNamespace(id=10), "BMW M3", 29000, pre),
        _make_lst_tuple(SimpleNamespace(id=11), "BMW M3", 34000, pre),
        _make_lst_tuple(SimpleNamespace(id=12), "BMW M3", 39000, pre),
        _make_lst_tuple(SimpleNamespace(id=13), "BMW M3", 44000, pre),
    ]

    pairs = _align_session(results, listings, min_coverage_ratio=0.8)
    # 4/5 = 80% = ceil(5*0.8)=4 → exactement au seuil → accepté
    assert len(pairs) == 4, f"Attendu 4 paires (seuil exact), obtenu {len(pairs)}"
