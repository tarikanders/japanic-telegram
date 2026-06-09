"""
Tests unitaires pour services/normalizer.py — focalisés sur extract_variant et la
correction 911 GTS.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.normalizer import normalize_model, extract_variant


# ── normalize_model — 911 GTS doit donner "Porsche 911 Gts" (titre) ─────────

def test_911_gts_normalized():
    result = normalize_model("911 GTS")
    assert result == "Porsche 911 Gts", f"got {result!r}"


def test_911_carera_gts_normalized():
    """'911 carera GTS' — correction d'orthographe + trim GTS."""
    result = normalize_model("911 carera GTS")
    assert "Gts" in result or "gts" in result.lower(), f"got {result!r}"


def test_911_targa4_normalized():
    """'Targa4' sans espace doit matcher le trim 'targa 4'."""
    result = normalize_model("911 Targa4")
    # Avec le fix \btarga 4\b dans le regex, on attend "Porsche 911 Targa 4"
    # (sinon "Carrera" si le regex ne match pas — le test valide le fix)
    assert "targa" in result.lower(), f"got {result!r}"


# ── extract_variant — Porsche Cayman ─────────────────────────────────────────

def test_cayman_gt4():
    assert extract_variant("cayman GT4", "Porsche Cayman") == "GT4"


def test_cayman_gt4_with_generation():
    assert extract_variant("cayman GT4 (F6)", "Porsche Cayman") == "GT4"


def test_cayman_gts():
    assert extract_variant("cayman GTS", "Porsche Cayman") == "GTS"


def test_cayman_s():
    assert extract_variant("cayman S", "Porsche Cayman") == "S"


def test_cayman_r():
    assert extract_variant("cayman R (F6)", "Porsche Cayman") == "R"


def test_cayman_718():
    assert extract_variant("718 cayman", "Porsche Cayman") == "718"


def test_cayman_base_no_variant():
    assert extract_variant("cayman", "Porsche Cayman") is None


# ── extract_variant — Porsche Boxster ────────────────────────────────────────

def test_boxster_gts():
    assert extract_variant("boxster GTS", "Porsche Boxster") == "GTS"


def test_boxster_spyder():
    assert extract_variant("boxster spyder (F6)", "Porsche Boxster") == "Spyder"


def test_boxster_s():
    assert extract_variant("boxster S (F6)", "Porsche Boxster") == "S"


# ── extract_variant — Porsche Panamera ───────────────────────────────────────

def test_panamera_gts():
    assert extract_variant("Panamera GTS", "Porsche Panamera") == "GTS"


def test_panamera_turbo():
    assert extract_variant("Panamera turbo", "Porsche Panamera") == "Turbo"


def test_panamera_turbo_s():
    assert extract_variant("Panamera turbo S", "Porsche Panamera") == "Turbo S"


def test_panamera_4s():
    assert extract_variant("Panamera 4S", "Porsche Panamera") == "4S"


# ── extract_variant — Porsche Cayenne ────────────────────────────────────────

def test_cayenne_turbo_s():
    assert extract_variant("cayenne turbo S", "Porsche Cayenne") == "Turbo S"


def test_cayenne_gts():
    assert extract_variant("cayenne GTS (3.6)", "Porsche Cayenne") == "GTS"


def test_cayenne_turbo():
    assert extract_variant("cayenne turbo", "Porsche Cayenne") == "Turbo"


# ── extract_variant — Maserati Ghibli ────────────────────────────────────────

def test_ghibli_s():
    assert extract_variant("ghibli S", "Maserati Ghibli") == "S"


def test_ghibli_s_q4():
    assert extract_variant("Maserati ghibli S Q4", "Maserati Ghibli") == "S Q4"


def test_ghibli_s_gransport():
    assert extract_variant("ghibli S gransports", "Maserati Ghibli") == "S GranSport"


def test_ghibli_granlusso():
    assert extract_variant("Maserati ghibli granlusso", "Maserati Ghibli") == "GranLusso"


def test_ghibli_base_no_variant():
    assert extract_variant("ghibli", "Maserati Ghibli") is None


# ── extract_variant — modèle sans table → None ───────────────────────────────

def test_bmw_m3_no_variant():
    """BMW M3 — trim déjà encodé dans le nom, pas de table variant."""
    assert extract_variant("bmw m3", "BMW M3") is None


def test_mercedes_no_variant():
    assert extract_variant("c63 amg", "Mercedes C63 AMG") is None


def test_unknown_model_no_variant():
    assert extract_variant("Toyota Supra", "Toyota Supra") is None
