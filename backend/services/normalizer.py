import re
from typing import Optional
from rapidfuzz import process, fuzz

# Alias exacts (surtout JDM / cas particuliers non couverts par les règles).
MODEL_ALIASES: dict[str, str] = {
    "bmw m3": "BMW M3",
    "bmw m5": "BMW M5",
    "bmw m4": "BMW M4",
    "bmw x5": "BMW X5",
    "bmw x3": "BMW X3",
    "bmw 3 series": "BMW 3 Series",
    "bmw 5 series": "BMW 5 Series",
    "toyota supra": "Toyota Supra",
    "toyota gt86": "Toyota GT86",
    "toyota ae86": "Toyota AE86",
    "nissan skyline": "Nissan Skyline",
    "nissan gtr": "Nissan GT-R",
    "nissan gt-r": "Nissan GT-R",
    "nissan r34": "Nissan Skyline R34",
    "nissan r33": "Nissan Skyline R33",
    "nissan r32": "Nissan Skyline R32",
    "honda nsx": "Honda NSX",
    "honda civic type r": "Honda Civic Type R",
    "honda s2000": "Honda S2000",
    "mazda rx7": "Mazda RX-7",
    "mazda rx-7": "Mazda RX-7",
    "mazda mx5": "Mazda MX-5",
    "mazda mx-5": "Mazda MX-5",
    "subaru impreza": "Subaru Impreza",
    "subaru wrx": "Subaru WRX",
    "mitsubishi lancer": "Mitsubishi Lancer",
    "mitsubishi evo": "Mitsubishi Lancer Evolution",
    "porsche cayman": "Porsche Cayman",
    "lexus is": "Lexus IS",
    "lexus gs": "Lexus GS",
}

# Corrections d'orthographe fréquentes dans le canal (avant toute règle).
_SPELLING = {
    "carera": "carrera",
    "carrera": "carrera",   # idempotent
    "carerra": "carrera",
    "grantourismo": "granturismo",
    "grandturismo": "granturismo",
    "grancabrio": "grancabrio",
    "grandcabrio": "grancabrio",
    "quatroporte": "quattroporte",
    "quattraporte": "quattroporte",
    "martini": "martin",   # "Aston martini" → "Aston martin"
    "panamerica": "panamera",
}

_alias_keys = list(MODEL_ALIASES.keys())

# Codes-modèle Mercedes (classe + cylindrée), AMG ou non.
_MB_CLASSES = "cls|cla|clk|cl|gle|glk|gla|gls|gle|gl|slk|slc|sls|sl|amg gt|c|e|s|g|a|b|m"
_RE_MB_AMG = re.compile(rf"\b({_MB_CLASSES})\s?(\d{{2,3}})\s*(s)?\s*amg\b", re.I)
_RE_MB_PLAIN = re.compile(rf"\b({_MB_CLASSES})\s?(\d{{3}})\b", re.I)

# BMW : M3/M4/M5, X/Z series, 3-chiffres + i optionnel.
_RE_BMW = re.compile(r"\bbmw\s*([mxz]?\d{1,3}[a-z]{0,2})\b", re.I)
_RE_BMW_M = re.compile(r"\b([mxz]\d)\b", re.I)

# Porsche
_RE_PORSCHE_911 = re.compile(r"\b(carrera|911)\b.*?\b(turbo|gt3 rs|gt3|gt2|targa|s|4s)\b", re.I)


def _clean(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\-]", "", s)
    return s


def _apply_spelling(s: str) -> str:
    return " ".join(_SPELLING.get(tok, tok) for tok in s.split())


def _rule_based(cleaned: str):
    """Normalisation déterministe par marque/code. Retourne None si aucune règle."""
    # --- Mercedes AMG (prioritaire : '63 amg' etc.) ---
    m = _RE_MB_AMG.search(cleaned)
    if m:
        cls = m.group(1).upper().replace(" ", "")
        num = m.group(2)
        s_variant = " S" if m.group(3) else ""
        return f"Mercedes {cls}{num}{s_variant} AMG"

    # --- Maserati ---
    if "granturismo" in cleaned:
        return "Maserati GranTurismo"
    if "grancabrio" in cleaned:
        return "Maserati GranCabrio"
    if "quattroporte" in cleaned:
        return "Maserati Quattroporte"
    if "ghibli" in cleaned:
        return "Maserati Ghibli"
    if "levante" in cleaned:
        return "Maserati Levante"

    # --- Porsche ---
    if "cayenne" in cleaned:
        return "Porsche Cayenne"
    if "cayman" in cleaned:
        return "Porsche Cayman"
    if "boxster" in cleaned:
        return "Porsche Boxster"
    if "panamera" in cleaned:
        return "Porsche Panamera"
    if "macan" in cleaned:
        return "Porsche Macan"
    if "carrera" in cleaned or re.search(r"\b911\b", cleaned):
        # targa\s*4 couvre "Targa 4" et "Targa4" (collé) sans espace dans le canal
        mt = re.search(r"\b(turbo s|turbo|gt3 rs|gt3|gt2 rs|gt2|gts|targa 4s|targa\s?4|targa|4s|4)\b", cleaned)
        trim = mt.group(1).title() if mt else "Carrera"
        return f"Porsche 911 {trim}"

    # --- BMW M/X/Z + numériques ---
    m = _RE_BMW.search(cleaned)
    if m:
        code = m.group(1).upper()
        return f"BMW {code}"
    m = _RE_BMW_M.search(cleaned)
    if m and ("bmw" in cleaned or m.group(1).lower() in {"m3", "m4", "m5", "m6", "m2"}):
        return f"BMW {m.group(1).upper()}"

    # --- Audi sportives ---
    m = re.search(r"\baudi\s*(rs\d|s\d|r8|tt\s?rs|tts|tt)\b", cleaned)
    if m:
        code = m.group(1).upper().replace(" ", "")
        return f"Audi {code}"

    # --- Mercedes non-AMG (E350, GLK350, SL550...) ---
    m = _RE_MB_PLAIN.search(cleaned)
    if m and "amg" not in cleaned:
        cls = m.group(1).upper().replace(" ", "")
        return f"Mercedes {cls}{m.group(2)}"

    return None


def normalize_model(raw: str, threshold: int = 75) -> str:
    cleaned = _apply_spelling(_clean(raw))

    # 1) règles déterministes (couvrent le gros du volume Mercedes/BMW/Porsche/Maserati)
    ruled = _rule_based(cleaned)
    if ruled:
        return ruled

    # 2) alias exacts
    if cleaned in MODEL_ALIASES:
        return MODEL_ALIASES[cleaned]

    # 3) fuzzy contre les alias (JDM surtout) — seuil relevé pour éviter Z3→M3
    match = process.extractOne(cleaned, _alias_keys, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= max(threshold, 85):
        return MODEL_ALIASES[match[0]]
    match2 = process.extractOne(cleaned, _alias_keys, scorer=fuzz.partial_ratio)
    if match2 and match2[1] >= 92:
        return MODEL_ALIASES[match2[0]]

    # 4) fallback : title-case
    return " ".join(w.capitalize() for w in cleaned.split())


# ──────────────────────────────────────────────────────────────────────────────
# Extraction de la finition (variant)
# ──────────────────────────────────────────────────────────────────────────────
# Table de règles par modèle normalisé.
# Chaque entrée : (regex_pattern, canonical_label) — ordre décroissant de précision.
# Règles pilotées par la distribution réelle des model_raw 2025+ (audit A0).
_VARIANT_TABLE: dict[str, list[tuple[str, str]]] = {
    # Porsche Cayman (458 auctions, 328 listings 2025+ ; GT4/GTS/S/R dans les listings)
    "Porsche Cayman": [
        (r"\bgt4\s*rs\b",       "GT4 RS"),
        (r"\bgt4\b",            "GT4"),
        (r"\bgts\s*4\.0\b",     "GTS 4.0"),
        (r"\bgts\b",            "GTS"),
        (r"\bblack\s*edition\b","Black Edition"),
        (r"\bspyder\b",         "Spyder"),
        (r"\b718\b",            "718"),
        (r"\br\b",              "R"),
        (r"\bs\b",              "S"),
    ],
    # Porsche Boxster (397 auctions, 299 listings ; GTS/S/Spyder)
    "Porsche Boxster": [
        (r"\brs60\s*spyder\b",  "RS60 Spyder"),
        (r"\bgts\b",            "GTS"),
        (r"\bspyder\b",         "Spyder"),
        (r"\b718\b",            "718"),
        (r"\bs\b",              "S"),
    ],
    # Porsche Panamera (304 auctions, 168 listings ; GTS 83!, Turbo 33, 4S 29, S 14)
    "Porsche Panamera": [
        (r"\bturbo\s*s\b",      "Turbo S"),
        (r"\bturbo\b",          "Turbo"),
        (r"\bgts\b",            "GTS"),
        (r"\b4s\b",             "4S"),
        (r"\bs\s*e[-\s]hybrid\b","S E-Hybrid"),
        (r"\bs\b",              "S"),
    ],
    # Porsche Cayenne (298 auctions, 148 listings ; Turbo 54, GTS 63, Turbo S 20, S 8)
    "Porsche Cayenne": [
        (r"\bturbo\s*s\b",      "Turbo S"),
        (r"\bturbo\b",          "Turbo"),
        (r"\bgts\b",            "GTS"),
        (r"\bs\s*e[-\s]hybrid\b","S E-Hybrid"),
        (r"\bs\b",              "S"),
    ],
    # Maserati Ghibli (157 auctions, 90 listings ; S 47, S Q4 3, GranSport 5, GranLusso 2)
    "Maserati Ghibli": [
        (r"\bs\s*gransport",   "S GranSport"),  # "gransports" (s final) toléré
        (r"\bs\s*q4\b",         "S Q4"),
        (r"\bgranlusso\b",      "GranLusso"),
        (r"\bs\b",              "S"),
    ],
    # Maserati GranTurismo (268 auctions — listings n'ont pas de variant dans le raw ; règles
    # préventives pour les rares cas où la finition apparaît)
    "Maserati GranTurismo": [
        (r"\bmc\s*stradale\b",  "MC Stradale"),
        (r"\bmc\b",             "MC"),
        (r"\bsport\b",          "Sport"),
        (r"\bs\b",              "S"),
    ],
    # Maserati GranCabrio (79 auctions)
    "Maserati GranCabrio": [
        (r"\bmc\b",             "MC"),
        (r"\bsport\b",          "Sport"),
        (r"\bs\b",              "S"),
    ],
    # Maserati Quattroporte (137 auctions)
    "Maserati Quattroporte": [
        (r"\bgts\b",            "GTS"),
        (r"\bs\s*q4\b",         "S Q4"),
        (r"\bs\b",              "S"),
    ],
}


def extract_variant(raw: str, base_normalized: str) -> Optional[str]:
    """
    Extrait la finition (variant) du model_raw brut étant donné le modèle normalisé.

    Retourne un label canonique (ex : "GTS", "GT4", "Turbo S", "S") ou None.
    Ne retourne rien si :
      - le modèle de base n'a pas de table de règles,
      - aucune règle ne matche dans le raw,
      - le trim est déjà encodé dans base_normalized (évite la redondance
        pour les modèles comme 911 Turbo, BMW M3, Mercedes C63 AMG…).

    Note : les variants des modèles BMW M / Audi RS / Mercedes AMG / Porsche 911 sont déjà
    intégrés dans model_normalized via _rule_based() → pas de table pour eux.
    """
    rules = _VARIANT_TABLE.get(base_normalized)
    if not rules:
        return None
    cleaned = _clean(_apply_spelling(raw))
    for pattern, canonical in rules:
        if re.search(pattern, cleaned, re.I):
            return canonical
    return None
