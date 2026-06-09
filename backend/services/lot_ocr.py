"""
lot_ocr.py — Module OCR pour extraire le numéro de lot depuis les images de fiches-rapport.

Interface principale :
  extract_lot_from_image(image_bytes) -> (lot: Optional[str], confidence: str)
  pick_report_photo(album_images)     -> Optional[bytes]

Moteur configurable via env OCR_ENGINE=tesseract|vision.
Imports gardés (try/except) : OCR est une amélioration optionnelle, pas une dépendance dure.
Si les libs manquent → confidence='none', le linker retombe sur le fuzzy.
"""
import os
import re
from io import BytesIO
from typing import Optional

# ── Imports optionnels ───────────────────────────────────────────────────────
_HAS_TESSERACT = False
_HAS_VISION = False
_HAS_PIL = False

try:
    from PIL import Image, ImageFilter
    _HAS_PIL = True
except ImportError:
    pass

try:
    import pytesseract
    _HAS_TESSERACT = True and _HAS_PIL
except ImportError:
    pass

try:
    from google.cloud import vision as _gv
    _HAS_VISION = True
except ImportError:
    pass

# ── Constantes ───────────────────────────────────────────────────────────────
# Sur la fiche-rapport japonaise, le numéro de lot apparaît TOUJOURS juste avant
# le libellé "初度登録年月" (premier enregistrement) — c'est le signal positionnel fiable.
# Spike validé sur 20 albums réels : pattern anchor → ~90% vs ~55% pour le range seul.
# Tolère un préfixe lettre collé (ex: "k73093" → "73093") : artefact Vision OCR.
# 4–6 chiffres couvre tous les coins de vente (4-digit: 5112, 8038 ; 5-digit: 27xxx–88xxx ; 6-digit: 170255).
LOT_ANCHOR_PATTERN = re.compile(r"[a-zA-Z]?(\d{4,6})\s*初度登録年月")

# Repli si le template de fiche est différent (coins alternatifs sans l'ancre).
# Range 50000-99999 pour éviter les cylindrées (3000, 5500) et codes chassis (463272).
LOT_FALLBACK_PATTERN = re.compile(r"(?<!\d)[a-zA-Z]?([5-9]\d{4})(?!\d)")

# Note d'état du véhicule. Spike réel : label souvent absent ou mal lu (評価 sans 点, 評値点).
# Le score apparaît TOUJOURS avant 内装 dans le flux OCR — c'est l'ancre fiable.
# Valeurs : 1–6 (ex: 4, 4.5), 45 (OCR a oublié le point → 4.5), S/R/RA/XX.

# La fiche-rapport (avec le n° de lot) est TOUJOURS la dernière photo de l'album.
# Confirmé sur les vrais messages Telegram du canal.
# Surcharger via env LOT_REPORT_PHOTO_INDEX si jamais ça change.
_DEFAULT_REPORT_INDEX: int = -1  # dernière photo


def _get_engine() -> str:
    return os.getenv("OCR_ENGINE", "auto").lower()


def _get_report_index() -> Optional[int]:
    val = os.getenv("LOT_REPORT_PHOTO_INDEX", "")
    try:
        return int(val)
    except (ValueError, TypeError):
        return _DEFAULT_REPORT_INDEX


# ── Prétraitement PIL ────────────────────────────────────────────────────────

def _preprocess(img_bytes: bytes) -> "Image.Image":
    """
    Grayscale + upscale si trop petit + sharpen.
    Améliore Tesseract sur les fiches scannées basse résolution.
    """
    from PIL import Image, ImageFilter
    img = Image.open(BytesIO(img_bytes)).convert("L")
    if img.width < 800:
        scale = 800 / img.width
        img = img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.LANCZOS,
        )
    img = img.filter(ImageFilter.SHARPEN)
    return img


# ── Moteurs OCR ──────────────────────────────────────────────────────────────

def _run_tesseract(img_bytes: bytes) -> str:
    """OCR Tesseract — texte brut extrait de l'image."""
    img = _preprocess(img_bytes)
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(img, config=config)


def _run_vision(img_bytes: bytes) -> str:
    """OCR Google Cloud Vision — texte brut."""
    client = _gv.ImageAnnotatorClient()
    image = _gv.Image(content=img_bytes)
    response = client.text_detection(image=image)
    if response.text_annotations:
        return response.text_annotations[0].description
    return ""


def _run_ocr(img_bytes: bytes, engine: Optional[str] = None) -> str:
    """
    Lance l'OCR avec cascade automatique :
      OCR_ENGINE=auto (défaut) → Tesseract d'abord (gratuit), Cloud Vision en repli
      OCR_ENGINE=tesseract     → Tesseract seulement
      OCR_ENGINE=vision        → Cloud Vision directement
    Retourne "" si aucun moteur disponible ou si tous échouent.
    """
    eng = engine or _get_engine()

    if eng == "vision":
        if _HAS_VISION:
            try:
                return _run_vision(img_bytes)
            except Exception:
                pass
        return ""

    if eng == "tesseract":
        if _HAS_TESSERACT:
            try:
                return _run_tesseract(img_bytes)
            except Exception:
                pass
        return ""

    # Mode "auto" : Tesseract → Vision
    if _HAS_TESSERACT:
        try:
            result = _run_tesseract(img_bytes)
            if result.strip():
                return result
        except Exception:
            pass

    if _HAS_VISION:
        try:
            return _run_vision(img_bytes)
        except Exception:
            pass

    return ""


# ── Extraction du lot ────────────────────────────────────────────────────────

def _select_lot(candidates: list[str]) -> tuple[Optional[str], str]:
    """
    Choisit le meilleur candidat parmi les occurrences de 4–6 chiffres.
    - Un seul candidat → ocr_high.
    - Plusieurs mais un dominant (≥ 2× plus fréquent) → ocr_high avec le dominant.
    - Plusieurs équivalents → ocr_low (ambigu).
    - Aucun → none.
    """
    if not candidates:
        return None, "none"

    from collections import Counter
    freq = Counter(candidates)
    most_common, count = freq.most_common(1)[0]

    if len(freq) == 1:
        return most_common, "ocr_high"

    # Plusieurs : le dominant est net (> 50% des occurrences ET seul au top) ?
    total = sum(freq.values())
    if count / total > 0.5 and freq.most_common(2)[0][1] > freq.most_common(2)[1][1]:
        return most_common, "ocr_high"

    # Ambigu
    return most_common, "ocr_low"


def extract_lot_from_image(
    image_bytes: bytes,
    engine: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """
    Extrait le numéro de lot depuis une image de fiche-rapport.

    Retourne (lot, confidence) où confidence ∈ {'ocr_high', 'ocr_low', 'none'}.
    Dégrade gracieusement vers ('none', 'none') si OCR indisponible ou erreur.
    """
    if not image_bytes:
        return None, "none"

    eng = engine or _get_engine()
    if eng == "vision" and not _HAS_VISION:
        return None, "none"
    if eng == "tesseract" and not _HAS_TESSERACT:
        return None, "none"
    if eng == "auto" and not _HAS_TESSERACT and not _HAS_VISION:
        return None, "none"

    try:
        text = _run_ocr(image_bytes, eng)
        if not text:
            return None, "none"
        # Try anchor first: lot is always the number right before 初度登録年月 on fiche template
        m = LOT_ANCHOR_PATTERN.search(text)
        if m:
            return m.group(1), "ocr_high"
        # Fallback: range-based (50000-99999) for non-standard corners
        candidates = LOT_FALLBACK_PATTERN.findall(text)
        return _select_lot(candidates)
    except Exception:
        return None, "none"


# ── Sélection de la photo-fiche dans l'album ─────────────────────────────────

def pick_report_photo(album_images: list[bytes]) -> Optional[bytes]:
    """
    Sélectionne la photo de la fiche-rapport dans un album de photos.

    Stratégie (par ordre de priorité) :
    1. Si LOT_REPORT_PHOTO_INDEX est défini dans l'env → index fixe (validé par spike).
    2. Sinon → tester chaque photo : retourner celle qui produit le plus de texte OCR structuré
       (heuristique : les fiches ont beaucoup de texte dense ; les photos véhicule peu).
       ⚠ Plus lent (OCR sur toutes les photos). Activer l'index fixe dès que le spike valide.
    3. Si aucune → None (OCR manquant ou album vide).
    """
    if not album_images:
        return None

    # Index fixe : dernière photo par défaut (confirmé sur les vrais messages du canal).
    # Surcharger via LOT_REPORT_PHOTO_INDEX si le canal change de format.
    report_idx = _get_report_index()
    if report_idx is not None:
        try:
            return album_images[report_idx]  # supporte les index négatifs Python (-1 = dernier)
        except IndexError:
            return None

    return album_images[-1]


# ── Extraction de la note d'état ─────────────────────────────────────────────

def _extract_score_from_text(text: str) -> Optional[str]:
    """
    Extrait la note d'état du texte OCR de la fiche.

    Cascade basée sur les patterns réels observés (spike 20 albums + debug 5 fiches) :
    1. Score décimal (4.5, 3.5…) juste avant 内装 — ancre la plus fiable
    2. Label 評価(点) suivi du score (même mal orthographié par OCR)
    3. "45" / "35" / "55" isolé sur une ligne — OCR a supprimé le point décimal
    Retourne None si ambigu plutôt qu'un faux positif.
    """
    # 1. Score décimal avant 内装 : "4.5\n内装", "4.5\n+\n内装", "3,5\n内装"
    m = re.search(r"(?:^|\n)([1-5][.,]\d)\s*\n(?:[+\-]?\s*\n)?内装", text)
    if m:
        return m.group(1).replace(",", ".")

    # 2. Label 評価(点) — OCR lit parfois 評価 sans 点, ou 評値点 (mauvais kanji)
    #    Suivi du score (décimal ou entier), puis 内装
    m = re.search(r"評[価値]点?\s*\n?\s*([1-5][.,]\d)\s*\n?\s*(?:[+\-]\s*\n?)?内装", text)
    if m:
        return m.group(1).replace(",", ".")

    # 3. Label 評価(点) suivi d'un score entier clair (ex: "評価\n5\n内装")
    m = re.search(r"評[価値]点?\s*\n\s*([1-5])\s*\n?\s*(?:[+\-]\s*\n?)?内装", text)
    if m:
        return m.group(1)

    # 4. "45" / "35" / "55" etc. entre newlines (OCR a sauté le point)
    #    Seulement si 内装 est présent dans le texte (sinon trop ambigu)
    if "内装" in text:
        m = re.search(r"(?:^|\n)([1-5][05])(?:\n)", text)
        if m:
            val = m.group(1)
            return f"{val[0]}.{val[1]}"

    # 5. Codes lettre (S = neuf, R = restauré, XX = non évalué)
    #    Seulement si 評価 ou 内装 est présent (contexte fiche confirmé)
    if "内装" in text or "評価" in text:
        m = re.search(r"\b(S|R[AR]?|XX?)\b", text)
        if m:
            return m.group(1)

    return None


def extract_fiche_data(
    image_bytes: bytes,
    engine: Optional[str] = None,
) -> tuple[Optional[str], str, Optional[str]]:
    """
    Extrait le numéro de lot ET la note d'état en un seul appel OCR.

    Retourne (lot, lot_confidence, condition_score) où :
      - lot_confidence ∈ {'ocr_high', 'ocr_low', 'none'}
      - condition_score : "4.5", "5", "R", ... ou None si absent
    """
    if not image_bytes:
        return None, "none", None

    eng = engine or _get_engine()
    if eng == "vision" and not _HAS_VISION:
        return None, "none", None
    if eng == "tesseract" and not _HAS_TESSERACT:
        return None, "none", None
    if eng == "auto" and not _HAS_TESSERACT and not _HAS_VISION:
        return None, "none", None

    try:
        text = _run_ocr(image_bytes, eng)
        if not text:
            return None, "none", None

        # Lot : ancre positionnelle d'abord
        m = LOT_ANCHOR_PATTERN.search(text)
        if m:
            lot, confidence = m.group(1), "ocr_high"
        else:
            candidates = LOT_FALLBACK_PATTERN.findall(text)
            lot, confidence = _select_lot(candidates)

        score = _extract_score_from_text(text)
        return lot, confidence, score

    except Exception:
        return None, "none", None


# ── Utilitaire diagnostique ──────────────────────────────────────────────────

def availability() -> dict:
    """Retourne l'état de disponibilité des dépendances OCR."""
    return {
        "pillow": _HAS_PIL,
        "tesseract": _HAS_TESSERACT,
        "vision": _HAS_VISION,
        "active_engine": _get_engine(),
        "report_photo_index": _get_report_index(),
    }
