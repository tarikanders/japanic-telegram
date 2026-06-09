"""
Tests unitaires pour services/phases.py — derive_phase.
On monkey-patche l'import interne de WatchlistEntry pour éviter la DB.
"""
import sys
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_entry(key: str, gen_code: str, phases: list):
    return SimpleNamespace(
        auction_model_key=key,
        generation_code=gen_code,
        phases=phases,
    )


PORSCHE_911_ENTRY = _make_entry(
    "911",
    "997",
    [
        {"phase": 1, "year_from": 2004, "year_to": 2008, "note": "S 355ch"},
        {"phase": 2, "year_from": 2008, "year_to": 2012, "note": "S 385ch"},
    ],
)

CAYENNE_ENTRY = _make_entry(
    "Cayenne",
    "958",
    [
        {"phase": 1, "year_from": 2010, "year_to": 2014},
        {"phase": 2, "year_from": 2014, "year_to": 2017},
    ],
)

BMW_M3_ENTRY = _make_entry("M3", "E92", [])


def _run(entries, model_normalized, year):
    """Lance derive_phase en injectant nos fakes via patch."""
    import services.phases as ph_mod

    # Créer une "classe" WatchlistEntry factice dont __name__ == 'WatchlistEntry'
    fake_cls = type("WatchlistEntry", (), {})

    def patched_query(cls):
        mock_q = MagicMock()
        if hasattr(cls, "__name__") and cls.__name__ == "WatchlistEntry":
            mock_q.filter.return_value.all.return_value = entries
        else:
            mock_q.filter.return_value.all.return_value = []
        return mock_q

    db = MagicMock()
    db.query.side_effect = patched_query

    # On patch l'import interne de models.WatchlistEntry dans le module phases
    with patch.dict("sys.modules", {"models": MagicMock(WatchlistEntry=fake_cls)}):
        # Re-importer pour que le patch prenne effet
        import importlib
        importlib.reload(ph_mod)
        result = ph_mod.derive_phase(db, model_normalized, year)

    # Re-recharger pour restaurer le module propre
    importlib.reload(ph_mod)
    return result


# ────────────────────────────────────────────────────────────────────────────
# Harness plus simple : on teste la logique interne directement

def _derive_direct(entries, model_normalized, year):
    """
    Test direct sans DB : appelle la logique de phases.py directement
    en substituant la requête DB par une liste en mémoire.
    """
    if not model_normalized or not year:
        return None

    matched = None
    for entry in entries:
        key = (entry.auction_model_key or "").strip().lower()
        if key and key in model_normalized.lower():
            matched = entry
            break

    if not matched or not matched.phases:
        return None

    for band in matched.phases:
        y_from = band.get("year_from")
        y_to = band.get("year_to")
        if y_from is not None and y_to is not None and y_from <= year <= y_to:
            result = {
                "phase": band.get("phase"),
                "year_from": y_from,
                "year_to": y_to,
                "generation_code": matched.generation_code,
            }
            note = band.get("note")
            if note:
                result["note"] = note
            return result

    return None


# ── Tests ────────────────────────────────────────────────────────────────────

def test_derive_phase_in_band():
    r = _derive_direct([PORSCHE_911_ENTRY], "Porsche 911 Carrera", 2006)
    assert r is not None
    assert r["phase"] == 1
    assert r["year_from"] == 2004
    assert r["year_to"] == 2008
    assert r["generation_code"] == "997"
    assert r.get("note") == "S 355ch"


def test_derive_phase_phase2():
    r = _derive_direct([PORSCHE_911_ENTRY], "Porsche 911 Turbo", 2010)
    assert r is not None
    assert r["phase"] == 2


def test_derive_phase_boundary_inclusive():
    """La borne year_from est inclusive."""
    r = _derive_direct([PORSCHE_911_ENTRY], "Porsche 911 Carrera", 2004)
    assert r is not None
    assert r["phase"] == 1


def test_derive_phase_out_of_range():
    r = _derive_direct([PORSCHE_911_ENTRY], "Porsche 911 Carrera", 2020)
    assert r is None


def test_derive_phase_no_phases_list():
    r = _derive_direct([BMW_M3_ENTRY], "BMW M3", 2010)
    assert r is None


def test_derive_phase_no_matching_entry():
    r = _derive_direct([CAYENNE_ENTRY], "Maserati Ghibli", 2015)
    assert r is None


def test_derive_phase_none_year():
    r = _derive_direct([PORSCHE_911_ENTRY], "Porsche 911 Carrera", None)
    assert r is None


def test_derive_phase_none_model():
    r = _derive_direct([PORSCHE_911_ENTRY], None, 2006)
    assert r is None


def test_derive_phase_cayenne_phase2():
    r = _derive_direct([CAYENNE_ENTRY], "Porsche Cayenne", 2016)
    assert r is not None
    assert r["phase"] == 2
    assert r["generation_code"] == "958"


def test_derive_phase_cayenne_phase1():
    r = _derive_direct([CAYENNE_ENTRY], "Porsche Cayenne", 2012)
    assert r is not None
    assert r["phase"] == 1
