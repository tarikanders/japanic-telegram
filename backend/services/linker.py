"""
Linker : associe un résultat d'enchère (Auction) à son annonce (Listing).

Contexte réel (vérifié sur les vrais messages Telegram) :
  - L'annonce (listing) ne contient JAMAIS de numéro de lot.
      ex: "2014 model G63 amg. 29k km. Start price 32000€"
  - Le résultat (auction) contient le lot, modèle en casse variable, prix.
      ex: "86004, G63 amg 37000€ not sold"

Clé de matching = similarité de MODÈLE NORMALISÉ + proximité temporelle + prix.
Le lot ne sert qu'à dédupliquer les résultats entre eux.

Règle d'or : un listing décrit UN véhicule physique → il ne peut alimenter
QU'UNE seule auction (1:1 strict). L'assignation est GLOBALE et OPTIMALE
(Hungarian / linear_sum_assignment) par bucket de modèle, pas gloutonne.
Un match "high" = le linker peut faire confiance → year/km écrits.
"""
import math
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from rapidfuzz import fuzz
from services.normalizer import normalize_model


def _data_min_date() -> Optional[date]:
    """
    Floor de date configurable via env DATA_MIN_DATE (défaut 2025-01-01).
    Le linker ne matche que les auctions/listings postérieurs à cette date
    pour réduire les collisions cross-années et se concentrer sur 2025-2026.
    Mettre DATA_MIN_DATE="" ou DATA_MIN_DATE=1970-01-01 pour désactiver le filtre.
    """
    raw = os.getenv("DATA_MIN_DATE", "2025-01-01").strip().lower()
    if not raw or raw in ("none", "all", "0", "off"):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date(2025, 1, 1)


DATA_MIN_DATE: Optional[date] = _data_min_date()

# ── Import optionnel scipy ────────────────────────────────────────────────────
try:
    from scipy.optimize import linear_sum_assignment as _lsa
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

# --- paramètres de matching (ajustables) ---
MODEL_MIN_SCORE = 86        # score fuzzy minimal modèle (0-100) pour accepter
CORE_MIN_RATIO = 86         # similarité minimale du CODE-MODÈLE (S4, M5, G63...)
# Fenêtre temporelle (jours). Le listing doit précéder le résultat.
# Médiane réelle ≈ 1j, p75 ≈ 7j, puis saut bimodal. 7j = un cycle hebdomadaire.
MAX_DAYS_BEFORE = 7
PRICE_TOLERANCE = 0.6       # |final - start| / start toléré avant pénalité

# Marge minimale top1/top2 pour écrire year/km (confiance "high").
MATCH_MARGIN_MIN = 6.0
YEAR_MIN, YEAR_MAX = 1980, 2026

# Mots qui n'identifient PAS le modèle : marques + finitions/carrosseries.
_BRANDS = {
    "bmw", "audi", "mercedes", "mercedes-benz", "benz", "porsche", "nissan",
    "toyota", "honda", "mazda", "subaru", "mitsubishi", "lexus", "aston",
    "martin", "martini", "ferrari", "lamborghini", "maserati", "jaguar",
    "land", "rover", "volkswagen", "vw", "mini",
}
_FILLERS = {
    "amg", "coupe", "coupé", "cabrio", "cabriolet", "sedan", "wagon", "touring",
    "manuel", "manual", "auto", "packet", "package", "pack", "performance",
    "sport", "sports", "hybrid", "hv", "hb", "edition", "line", "model",
    "4matic", "quattro", "xdrive", "s-line", "sline", "le", "v8", "v6", "v12",
}

_SENTINEL = 1e6  # coût interdit dans la matrice d'assignation


def _clean_model(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\-]", "", s)
    return s


def _core_tokens(s: str) -> list[str]:
    toks = [t for t in _clean_model(s).split() if t and t not in _BRANDS and t not in _FILLERS]
    return toks


def _core_match(a: str, b: str) -> Optional[float]:
    ca, cb = _core_tokens(a), _core_tokens(b)
    if ca and cb:
        best = max(fuzz.ratio(x, y) for x in ca for y in cb)
        return best if best >= CORE_MIN_RATIO else None
    full = fuzz.token_sort_ratio(_clean_model(a), _clean_model(b))
    return full if full >= MODEL_MIN_SCORE else None


def model_score(auction_model: str, listing_model: str) -> float:
    """Score 0-100, avec garde anti-cross-matching sur les codes-modèle."""
    a = _clean_model(auction_model)
    b = _clean_model(listing_model)
    if not a or not b:
        return 0.0
    core = _core_match(auction_model, listing_model)
    if core is None:
        return 0.0
    overall = max(fuzz.token_set_ratio(a, b), fuzz.partial_ratio(a, b))
    return min(core, overall)


@dataclass
class LinkCandidate:
    listing_id: int
    score: float
    model_score: float
    days_gap: int


def score_listing(
    auction_model: str,
    auction_final_price: Optional[int],
    auction_date: Optional[date],
    listing_model: str,
    listing_start_price: Optional[int],
    listing_posted_date: Optional[date],
) -> Optional[float]:
    """
    Score global d'un couple (auction, listing). Retourne None si rejeté.
    Les modèles passés ici doivent déjà être NORMALISÉS (normalisé↔normalisé).
    """
    ms = model_score(auction_model, listing_model)
    if ms < MODEL_MIN_SCORE:
        return None

    days_gap = None
    if auction_date and listing_posted_date:
        days_gap = (auction_date - listing_posted_date).days
        if days_gap < 0 or days_gap > MAX_DAYS_BEFORE:
            return None

    score = ms

    if days_gap is not None:
        score += 10.0 * (1.0 - days_gap / MAX_DAYS_BEFORE)

    if auction_final_price and listing_start_price and listing_start_price > 0:
        rel = abs(auction_final_price - listing_start_price) / listing_start_price
        if rel <= PRICE_TOLERANCE:
            score += 5.0 * (1.0 - rel / PRICE_TOLERANCE)

    return score


def _valid_year(y) -> bool:
    return y is not None and YEAR_MIN <= y <= YEAR_MAX


# ── Assignation optimale par batch ────────────────────────────────────────────

def _assign_batch_scipy(
    auctions: list, listings: list,
    au_model_fn, lst_model_fn,
    au_price_fn, au_date_fn,
    lst_price_fn, lst_date_fn,
) -> dict:
    """
    Assignation GLOBALE optimale via Hungarian (scipy.linear_sum_assignment).
    Retourne {auction_id: (listing, score, margin)} pour les paires retenues.
    """
    import numpy as np
    n, m = len(auctions), len(listings)
    C = np.full((n, m), _SENTINEL)

    for i, au in enumerate(auctions):
        for j, lst in enumerate(listings):
            sc = score_listing(
                au_model_fn(au), au_price_fn(au), au_date_fn(au),
                lst_model_fn(lst), lst_price_fn(lst), lst_date_fn(lst),
            )
            if sc is not None:
                C[i, j] = -sc  # minimiser coût = maximiser score

    row_ind, col_ind = _lsa(C)
    result = {}
    for i, j in zip(row_ind, col_ind):
        if C[i, j] >= _SENTINEL * 0.9:  # paire sentinelle → pas de match réel
            continue
        best_score = -C[i, j]
        # marge = score du 2e meilleur FAISABLE pour cet auction
        row = C[i]
        feasible_others = sorted([-v for v in row if v < _SENTINEL * 0.9])
        second_best = feasible_others[1] if len(feasible_others) > 1 else 0.0
        margin = best_score - second_best
        result[id(auctions[i])] = (listings[j], best_score, margin)

    return result


def _assign_batch_greedy(
    auctions: list, listings: list,
    au_model_fn, lst_model_fn,
    au_price_fn, au_date_fn,
    lst_price_fn, lst_date_fn,
) -> dict:
    """
    Fallback sans scipy : tri global de tous les triplets faisables, puis
    assignation gloutonne avec consommation mutuelle — quasi-optimal, O(n*m*log).
    """
    triples = []
    for au in auctions:
        for lst in listings:
            sc = score_listing(
                au_model_fn(au), au_price_fn(au), au_date_fn(au),
                lst_model_fn(lst), lst_price_fn(lst), lst_date_fn(lst),
            )
            if sc is not None:
                triples.append((sc, au, lst))
    triples.sort(key=lambda t: t[0], reverse=True)

    used_au, used_lst = set(), set()
    # pré-calcul second_best par auction
    best_per_au: dict = {}
    for sc, au, lst in triples:
        aid = id(au)
        if aid not in best_per_au:
            best_per_au[aid] = sc
    second_per_au: dict = {}
    for sc, au, lst in triples:
        aid = id(au)
        if aid in second_per_au:
            continue
        if aid in best_per_au and sc < best_per_au[aid]:
            second_per_au[aid] = sc

    result = {}
    for sc, au, lst in triples:
        aid, lid = id(au), id(lst)
        if aid in used_au or lid in used_lst:
            continue
        margin = best_per_au.get(aid, sc) - second_per_au.get(aid, 0.0)
        result[aid] = (lst, sc, margin)
        used_au.add(aid)
        used_lst.add(lid)

    return result


def _assign_batch(
    auctions, listings,
    au_model_fn, lst_model_fn,
    au_price_fn, au_date_fn,
    lst_price_fn, lst_date_fn,
) -> dict:
    """Délègue à scipy si disponible, sinon glouton global."""
    if not auctions or not listings:
        return {}
    if _HAS_SCIPY:
        return _assign_batch_scipy(
            auctions, listings,
            au_model_fn, lst_model_fn,
            au_price_fn, au_date_fn,
            lst_price_fn, lst_date_fn,
        )
    return _assign_batch_greedy(
        auctions, listings,
        au_model_fn, lst_model_fn,
        au_price_fn, au_date_fn,
        lst_price_fn, lst_date_fn,
    )


def classify_ranked(ranked: list) -> tuple[Optional[object], str]:
    """
    Décide la fiabilité depuis une liste triée (listing, score).
    Conservé pour compatibilité avec find_best_listing (sync incrémental).
    """
    if not ranked:
        return None, "none"
    best_l, best_s = ranked[0]
    if len(ranked) == 1:
        return best_l, "high"
    second_s = ranked[1][1]
    if best_s - second_s >= MATCH_MARGIN_MIN:
        return best_l, "high"
    return best_l, "review"


def rank_free_listings(db, auction_model, auction_final_price, auction_date,
                       exclude_ids: Optional[set] = None) -> list:
    """
    Classe les listings LIBRES compatibles par score décroissant.
    Utilise model_normalized↔model_normalized pour les deux côtés.
    """
    from models import Listing

    # Normaliser le modèle auction pour comparer normalisé↔normalisé
    auction_model_norm = normalize_model(auction_model) if auction_model else ""
    key_toks = _clean_model(auction_model_norm).split()
    if not key_toks:
        return []
    key = key_toks[0]

    q = db.query(Listing).filter(Listing.linked_auction_id.is_(None))
    if auction_date is not None:
        q = q.filter(Listing.posted_date <= auction_date)
    # Préfiltrer sur model_normalized (si disponible) sinon model_raw
    q = q.filter(
        Listing.model_normalized.ilike(f"%{key}%")
        | Listing.model_raw.ilike(f"%{key}%")
    )

    exclude_ids = exclude_ids or set()
    scored = []
    for lst in q.all():
        if lst.id in exclude_ids:
            continue
        lst_model = lst.model_normalized or normalize_model(lst.model_raw or "")
        sc = score_listing(
            auction_model_norm, auction_final_price, auction_date,
            lst_model, lst.start_price_eur, lst.posted_date,
        )
        if sc is not None:
            scored.append((lst, sc))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


# ── Alignement positionnel par bande de lot (Tier 2) ─────────────────────────

def _lot_band(lot_number) -> Optional[str]:
    """
    Bande de lot = session/maison d'enchère. Les numéros de lot se regroupent
    en tranches (65xxx / 70xxx / 73xxx…) correspondant à des salles/sessions.
    Retourne le préfixe millier (str) ou None si non numérique.
    """
    try:
        return str(int(lot_number) // 1000)
    except (TypeError, ValueError):
        return None


def _align_session(
    results: list,
    listings: list,
    min_coverage_ratio: float = 0.5,
) -> list[tuple]:
    """
    Alignement MONOTONE entre résultats d'une bande de lot et les annonces
    correspondantes. Basé sur une DP type plus longue sous-séquence commune
    pondérée par le score modèle.

    results  : liste de (auction, model_norm, final_price, auction_date,
                         result_line_index) — triés par result_line_index.
    listings : liste de (listing, model_norm, start_price, posted_date)
               — triés par (posted_date, telegram_message_id).

    min_coverage_ratio : fraction minimale des résultats qui doivent être
               alignés pour que la session soit retournée (défaut 0.5,
               utiliser 0.8 pour un alignement "prudent" par bande).

    Retourne une liste de (auction, listing, score, "positional") pour
    les paires où l'alignement est à la fois fort-modèle ET cohérent avec
    l'ordre → candidats pour une confiance "high" via signal positionnel.

    Dégrade proprement vers une liste vide si le signal est faible ou si
    les données Tier 2 (result_line_index) sont absentes.
    """
    if not results or not listings:
        return []

    # Vérifier que les données Tier 2 sont disponibles
    if any(r[4] is None for r in results):
        return []  # pas de line_index → pas d'alignement positionnel

    n, m = len(results), len(listings)

    # Matrice de score modèle : sc[i][j] = score(result i, listing j) ou 0
    sc_matrix = [[0.0] * m for _ in range(n)]
    for i, (au, au_mod, au_price, au_date, _) in enumerate(results):
        for j, (lst, lst_mod, lst_price, lst_date) in enumerate(listings):
            sc = score_listing(au_mod, au_price, au_date, lst_mod, lst_price, lst_date)
            if sc is not None:
                sc_matrix[i][j] = sc

    # DP monotone : dp[i][j] = meilleur score cumulatif en assignant result[i] → listing[j]
    # avec la contrainte de monotonie (les assignations ne se croisent pas)
    # dp[i][j] = max(dp[i-1][j-1], dp[i-1][j']) pour j' < j, + sc[i][j]
    # On ne garde qu'une assignation si sc[i][j] >= MODEL_MIN_SCORE
    INF = -1e9
    dp = [[INF] * m for _ in range(n)]
    parent = [[(-1, -1)] * m for _ in range(n)]  # pour backtracking

    for i in range(n):
        for j in range(m):
            if sc_matrix[i][j] < MODEL_MIN_SCORE:
                continue
            if i == 0:
                best_prev = 0.0
                dp[i][j] = sc_matrix[i][j]
                parent[i][j] = (-1, -1)
            else:
                # meilleur dp[i-1][j'] pour j' < j (contrainte monotonie)
                best_prev, best_jp = INF, -1
                for jp in range(j):
                    if dp[i-1][jp] > best_prev:
                        best_prev = dp[i-1][jp]
                        best_jp = jp
                # aussi possibilité de "sauter" le listing j-1 (i-1 non assigné avant j)
                if best_prev > INF:
                    dp[i][j] = best_prev + sc_matrix[i][j]
                    parent[i][j] = (i - 1, best_jp)
                else:
                    # premier assignable sans prédécesseur
                    dp[i][j] = sc_matrix[i][j]
                    parent[i][j] = (-1, -1)

    # Trouver la cellule finale maximale
    best_score, best_i, best_j = INF, -1, -1
    for i in range(n):
        for j in range(m):
            if dp[i][j] > best_score:
                best_score = dp[i][j]
                best_i, best_j = i, j

    if best_i == -1 or best_score < MODEL_MIN_SCORE:
        return []

    # Backtrack pour récupérer les paires
    pairs = []
    ci, cj = best_i, best_j
    while ci >= 0 and cj >= 0:
        if sc_matrix[ci][cj] >= MODEL_MIN_SCORE:
            au, _, au_price, au_date, _ = results[ci]
            lst, _, lst_price, lst_date = listings[cj]
            pairs.append((au, lst, sc_matrix[ci][cj], "positional"))
        pi, pj = parent[ci][cj]
        ci, cj = pi, pj

    pairs.reverse()

    # Filtrer : ne garder que les paires avec un score suffisant
    # et vérifier que l'alignement est plausible (>= min_coverage_ratio des résultats matchés).
    # Avec min_coverage_ratio=0.5 : comportement historique (n // 2).
    # Avec min_coverage_ratio=0.8 : mode prudent par bande (défaut pour l'appel par bande).
    min_pairs = max(1, math.ceil(n * min_coverage_ratio))
    if len(pairs) < min_pairs:
        return []  # alignement trop partiel → signal faible, dégrader

    return pairs


def _pick_lot_candidate(
    auction_model_norm: str,
    candidates: list,
) -> Optional[object]:
    """
    Choisit le meilleur listing parmi les candidats partageant le même lot_number
    dans la fenêtre temporelle.

    Stratégie (double signal lot + modèle) :
    1. Scorifier chaque candidat par model_score(auction_model_norm, listing_model).
    2. Candidats "forts" = ceux dont le score ≥ MODEL_MIN_SCORE.
       - Si exactement 1 fort → sûr, retourner (lot + modèle concorde).
       - Si plusieurs forts (lot ré-utilisé) → trier par posted_date décroissante
         (la plus proche AVANT l'enchère). Si le meilleur est unique par date → retourner.
         Sinon → ambigu, laisser au fuzzy.
    3. Aucun fort → repli sur l'ancienne règle stricte : ocr_high unique seulement.
       (Les lots ocr_low sans confirmation modèle ne sont PAS acceptés en repli strict.)

    ⚠ Les lots ocr_low sont acceptés uniquement via la branche "forts" (lot + modèle
    concordent). Ceci évite les faux positifs sur des lots mal lus quand le modèle
    ne confirme pas.
    """
    if not candidates:
        return None

    scored = [
        (lst, model_score(
            auction_model_norm,
            lst.model_normalized or normalize_model(lst.model_raw or ""),
        ))
        for lst in candidates
    ]
    strong = [(lst, ms) for lst, ms in scored if ms >= MODEL_MIN_SCORE]

    if len(strong) == 1:
        return strong[0][0]  # lot + modèle → déterministe

    if len(strong) > 1:
        # Lot ré-utilisé : choisir la date posted la plus proche avant l'enchère.
        strong.sort(key=lambda x: (x[0].posted_date or date.min), reverse=True)
        top_date = strong[0][0].posted_date
        second_date = strong[1][0].posted_date
        if top_date != second_date:
            return strong[0][0]  # date discrimine → sûr
        return None  # égalité de date → ambigu, laisser au fuzzy

    # Aucun modèle confirmé → repli strict : ocr_high unique seulement
    high = [lst for lst, _ in scored if lst.lot_ocr_confidence == "ocr_high"]
    return high[0] if len(high) == 1 else None


def _find_lot_listing(
    db,
    lot_number: str,
    auction_model: str,
    auction_date,
    exclude_ids: Optional[set] = None,
):
    """
    Cherche un listing libre dont lot_number correspond au lot de l'enchère,
    dans la fenêtre [auction_date - MAX_DAYS_BEFORE, auction_date].

    Utilise _pick_lot_candidate pour désambiguïser en croisant lot + modèle :
    - Lot unique + modèle confirme → high déterministe.
    - Lot ré-utilisé → départage par modèle puis par date posted la plus proche.
    - ocr_low accepté si le modèle confirme (double signal).
    Retourne None si ambigu (on laisse au fuzzy pour éviter les faux high silencieux).
    """
    from models import Listing
    from datetime import timedelta

    if not lot_number:
        return None

    exclude_ids = exclude_ids or set()

    # Charger TOUS les listings libres portant ce lot (toutes confidences OCR)
    q = (
        db.query(Listing)
        .filter(
            Listing.lot_number == lot_number,
            Listing.linked_auction_id.is_(None),
        )
    )
    if auction_date is not None:
        d_min = auction_date - timedelta(days=MAX_DAYS_BEFORE)
        q = q.filter(
            Listing.posted_date >= d_min,
            Listing.posted_date <= auction_date,
        )

    candidates = [lst for lst in q.all() if lst.id not in exclude_ids]
    if not candidates:
        return None

    auction_model_norm = normalize_model(auction_model) if auction_model else ""
    return _pick_lot_candidate(auction_model_norm, candidates)


def find_best_listing(
    db,
    auction_model,
    auction_final_price,
    auction_date,
    lot_number: Optional[str] = None,
    exclude_ids: Optional[set] = None,
):
    """
    Pour le sync incrémental. Retourne (listing | None, confidence).

    Pré-passe déterministe : si lot_number est fourni, utilise _pick_lot_candidate
    (croisement lot + modèle) → 'high' déterministe.
    Sinon → fuzzy via rank_free_listings (Tier 1+2).
    """
    exclude_ids = exclude_ids or set()

    # Tier 3 : pont lot déterministe (lot + modèle)
    if lot_number:
        lst = _find_lot_listing(db, lot_number, auction_model, auction_date, exclude_ids)
        if lst:
            return lst, "high"

    ranked = rank_free_listings(
        db, auction_model, auction_final_price, auction_date, exclude_ids=exclude_ids
    )
    return classify_ranked(ranked)


def _link_by_lot(
    db,
    auctions: list,
    listings_index: dict,  # {lot_number: [listing, ...]} — pré-indexé
    auction_date,
    used_listing_ids: set,
    dry_run: bool,
    stats: dict,
    verbose: bool,
) -> set:
    """
    Pré-passe déterministe Tier 3 : associe les enchères à leur annonce via le n° de lot OCR.

    Utilise _pick_lot_candidate (croisement lot + modèle + désambiguïsation par date) :
    - Lot unique + modèle confirme (≥ MODEL_MIN_SCORE) → match déterministe 'high'.
    - Lot ré-utilisé → département par modèle puis date posted la plus proche.
    - ocr_low accepté si modèle confirme (double signal).
    Retourne l'ensemble des id(auction) traités par cette passe.
    """
    from datetime import timedelta
    handled = set()

    for au in auctions:
        lot = au.lot_number
        if not lot or lot not in listings_index:
            continue

        # Candidats libres (toutes confidences OCR — le helper filtrera)
        candidates = [
            lst for lst in listings_index[lot]
            if lst.id not in used_listing_ids
            and lst.linked_auction_id is None
        ]

        # Filtrer par fenêtre temporelle
        if auction_date is not None:
            d_min = auction_date - timedelta(days=MAX_DAYS_BEFORE)
            candidates = [
                lst for lst in candidates
                if lst.posted_date is not None
                and d_min <= lst.posted_date <= auction_date
            ]

        if not candidates:
            continue

        au_model_norm = au.model_normalized or normalize_model(au.model_raw or "")
        best = _pick_lot_candidate(au_model_norm, candidates)
        if best is None:
            continue  # ambigu → laisser au fuzzy

        old_year = au.year
        new_year = best.year if _valid_year(best.year) else None

        used_listing_ids.add(best.id)
        handled.add(id(au))
        stats["linked_high"] += 1
        stats["linked_by_lot"] += 1
        if au.year != new_year:
            stats["year_changed"] += 1
        if old_year is not None and new_year is None:
            stats["year_cleared"] += 1

        if not dry_run:
            au.year = new_year
            au.mileage_km = best.mileage_km
            au.start_price_eur = best.start_price_eur
            au.match_confidence = "high"
            au.matched_listing_id = best.id
            au.condition_score = best.condition_score
            if best.variant:
                au.variant = best.variant
            best.linked_auction_id = au.id

        if verbose and len(stats["examples"]) < 20:
            stats["examples"].append(
                f"[LOT  ] AU#{au.id} '{au.model_raw}' lot={lot} <-"
                f"LST#{best.id} '{best.model_raw}' "
                f"[déterministe conf={best.lot_ocr_confidence}] year {old_year}→{new_year}"
            )

    return handled


def link_auctions(db, dry_run: bool = True, verbose: bool = False) -> dict:
    """
    Ré-associe TOUTES les auctions à leur meilleur listing libre (1:1).

    Algorithme GLOBAL par fenêtre temporelle (vs greedy) :
      1. Regroupe par (bucket_modèle, auction_date).
      2. Pour chaque groupe, ne considère que les listings postés dans les
         MAX_DAYS_BEFORE jours précédents → matrices petites (≈10-40 éléments).
      3. Résout l'assignation optimale par sous-batch (Hungarian si scipy,
         sinon glouton-global trié).
      4. Confiance "high" ssi score réel ET marge >= MATCH_MARGIN_MIN.

    Complexité : O(D * B * n_d * m_d) où D = jours distincts, B = buckets,
    n_d/m_d = enchères/annonces par (bucket, date) → typiquement 1-20 chacun.

    dry_run=True : ne commit rien.
    """
    from models import Auction, Listing
    from datetime import timedelta

    # ── Chargement — scopé 2025+ (DATA_MIN_DATE) ──────────────────────────────
    # Les données antérieures restent en DB mais ne participent pas au re-link :
    # fenêtre plus courte → moins de collisions cross-années.
    # Désactiver via DATA_MIN_DATE="" dans .env pour un re-link global.
    floor = DATA_MIN_DATE
    _lst_q = db.query(Listing).filter(Listing.linked_auction_id.is_(None))
    if floor:
        _lst_q = _lst_q.filter(Listing.posted_date >= floor)
    listings = _lst_q.all()

    _au_q = db.query(Auction).order_by(Auction.auction_date.asc().nullslast(), Auction.id.asc())
    if floor:
        _au_q = _au_q.filter(Auction.auction_date >= floor)
    auctions = _au_q.all()

    def _bucket(model_str: str) -> str:
        toks = _clean_model(normalize_model(model_str or "")).split()
        return toks[0] if toks else ""

    def au_model(au):   return normalize_model(au.model_normalized or au.model_raw or "")
    def lst_model(lst): return lst.model_normalized or normalize_model(lst.model_raw or "")
    def au_price(au):   return au.final_price_eur
    def lst_price(lst): return lst.start_price_eur
    def au_date(au):    return au.auction_date
    def lst_date(lst):  return lst.posted_date

    # Index listings par (bucket, posted_date) — utilisé par la bipartite
    lst_by_bucket_date: dict[tuple, list] = {}
    # Index listings par posted_date seul — utilisé par la passe positionnelle
    # (session multi-modèles : on veut TOUS les listings du jour, pas juste un bucket)
    lst_by_date: dict = {}
    for lst in listings:
        bk = _bucket(lst.model_raw)
        if lst.posted_date:
            lst_by_bucket_date.setdefault((bk, lst.posted_date), []).append(lst)
            lst_by_date.setdefault(lst.posted_date, []).append(lst)
        else:
            lst_by_bucket_date.setdefault((bk, None), []).append(lst)

    # Index auctions par (bucket, auction_date)
    au_by_bucket_date: dict[tuple, list] = {}
    for au in auctions:
        bk = _bucket(au.model_raw)
        au_by_bucket_date.setdefault((bk, au.auction_date), []).append(au)

    stats = {
        "auctions_total": len(auctions),
        "linked_high": 0,
        "linked_by_lot": 0,        # sous-compteur Tier 3 pont-lot (inclus dans linked_high)
        "linked_positional": 0,    # sous-compteur Tier 2 alignement positionnel (inclus dans linked_high)
        "needs_review": 0,
        "unmatched": 0,
        "year_changed": 0,
        "year_cleared": 0,
        "examples": [],
    }

    # ── Pré-passe Tier 3 : pont déterministe par numéro de lot ───────────────────
    # Indexer TOUS les listings portant un lot_number (toutes confidences OCR).
    # Le helper _pick_lot_candidate gère la discrimination ocr_high / ocr_low
    # via le croisement avec le modèle — ne pas pré-filtrer ici.
    lot_listings_index: dict[str, list] = {}
    for lst in listings:
        if lst.lot_number:
            lot_listings_index.setdefault(lst.lot_number, []).append(lst)

    used_listing_ids: set[int] = set()
    already_handled: set = set()  # id(auction) traitées par le pont lot

    if lot_listings_index:
        # Regrouper les auctions par auction_date pour la pré-passe
        from itertools import groupby
        auctions_by_date = {}
        for au in auctions:
            auctions_by_date.setdefault(au.auction_date, []).append(au)

        for auction_date_key, aus_on_date in auctions_by_date.items():
            handled = _link_by_lot(
                db,
                aus_on_date,
                lot_listings_index,
                auction_date_key,
                used_listing_ids,
                dry_run,
                stats,
                verbose,
            )
            already_handled.update(handled)

    # ── Pré-passe Tier 2 : alignement positionnel PAR BANDE DE LOT ──────────────
    # Signal : l'ordre des résultats dans le message (result_line_index) correspond
    # à l'ordre de publication des annonces (telegram_message_id / posted_date).
    #
    # Ancien comportement (v1) : une seule DP sur la session complète
    # (ex : 75 résultats × 191 annonces). Problèmes :
    #   - Doublons de result_line_index quand deux messages physiques partagent
    #     un telegram_message_id → DP reçoit un ordre ambigu.
    #   - La garde n//2 jette TOUTES les paires si la session est partiellement
    #     alignable (< 50 % des modèles matchent).
    #
    # Nouvelle approche (v2) : DP séparée PAR BANDE DE LOT (65xxx, 70xxx, …).
    #   - Chaque bande correspond à une salle/session d'enchère distincte.
    #   - Matrices plus petites (6-36 résultats × ~30-80 annonces) → moins de bruit.
    #   - Politique PRUDENTE : exiger >= 80 % de couverture par bande
    #     (une bande peu alignable est abandonnée → pas d'années fausses).
    #   - Annonces filtrées : celles sans lot_number (bande inconnue) +
    #     celles dont le lot_number appartient à la même bande.
    #     Les annonces d'une autre bande connue sont EXCLUES pour éviter
    #     les cross-contaminations entre salles.
    #   - Bandes traitées dans l'ordre croissant du premier result_line_index
    #     (bande arrivant en tête du message = annonces consommées en premier).

    # Regrouper auctions libres par (auction_date, telegram_message_id, lot_band).
    _pos_groups_by_band: dict[tuple, list] = {}
    for au in auctions:
        if id(au) in already_handled:
            continue
        if getattr(au, "result_line_index", None) is None:
            continue
        band = _lot_band(au.lot_number)
        if band is None:
            continue  # lot non-numérique → pas de bande définie
        key = (au.auction_date, au.telegram_message_id, band)
        _pos_groups_by_band.setdefault(key, []).append(au)

    # Trier les bandes par position d'apparition dans le message
    # (bandes arrivant tôt dans result_line_index = consommées en premier
    # → leurs annonces correspondantes ont été publiées plus tôt).
    _band_keys_sorted = sorted(
        _pos_groups_by_band.keys(),
        key=lambda k: min(au.result_line_index for au in _pos_groups_by_band[k]),
    )

    for (pos_date, _pos_msg_id, band) in _band_keys_sorted:
        pos_aus = _pos_groups_by_band[(pos_date, _pos_msg_id, band)]
        if not pos_aus:
            continue

        # Trier les résultats par result_line_index (ordre dans le message)
        pos_aus_sorted = sorted(pos_aus, key=lambda a: a.result_line_index)

        # Listings candidats :
        #   - include si lot_number est None (bande inconnue → peut appartenir ici)
        #   - include si lot_number donne la même bande
        #   - EXCLURE si lot_number donne une autre bande (salle différente)
        pos_lsts_raw: list = []
        if pos_date:
            for d_off in range(MAX_DAYS_BEFORE + 1):
                d = pos_date - timedelta(days=d_off)
                for l in lst_by_date.get(d, []):
                    if l.id in used_listing_ids:
                        continue
                    lst_band = _lot_band(l.lot_number)
                    if l.lot_number is not None and lst_band != band:
                        continue  # lot appartient à une autre salle → exclure
                    pos_lsts_raw.append(l)

        if not pos_lsts_raw:
            continue

        # Trier listings par ordre de publication (même logique que v1)
        pos_lsts_sorted = sorted(
            pos_lsts_raw,
            key=lambda l: (l.posted_date or date.min, l.telegram_message_id or 0),
        )

        _results_input = [
            (
                au,
                au_model(au),
                au.final_price_eur,
                au.auction_date,
                au.result_line_index,
            )
            for au in pos_aus_sorted
        ]
        _listings_input = [
            (
                lst,
                lst_model(lst),
                lst.start_price_eur,
                lst.posted_date,
            )
            for lst in pos_lsts_sorted
        ]

        # Politique prudente : 80 % de couverture minimale sur la bande
        pairs = _align_session(_results_input, _listings_input, min_coverage_ratio=0.8)

        for au, best, score, _kind in pairs:
            if id(au) in already_handled:
                continue  # pont-lot a pris la main entre temps
            if best.id in used_listing_ids:
                continue  # listing déjà consommé par une bande précédente

            old_year = au.year
            new_year = best.year if _valid_year(best.year) else None

            used_listing_ids.add(best.id)
            already_handled.add(id(au))
            stats["linked_high"] += 1
            stats["linked_positional"] += 1
            if au.year != new_year:
                stats["year_changed"] += 1
            if old_year is not None and new_year is None:
                stats["year_cleared"] += 1

            if not dry_run:
                au.year = new_year
                au.mileage_km = best.mileage_km
                au.start_price_eur = best.start_price_eur
                au.match_confidence = "high"
                au.matched_listing_id = best.id
                au.condition_score = best.condition_score
                if best.variant:
                    au.variant = best.variant
                best.linked_auction_id = au.id

            if verbose and len(stats["examples"]) < 20:
                stats["examples"].append(
                    f"[POS  ] AU#{au.id} '{au.model_raw}' lot={au.lot_number} band={band} <-"
                    f"LST#{best.id} '{best.model_raw}' "
                    f"[positionnel score={score:.0f}] year {old_year}→{new_year}"
                )

    # Résultat global : mapping id(auction) → (listing, score, margin)
    assignments: dict = {}

    # Pour chaque (bucket, auction_date), trouver les listings candidats
    # dans la fenêtre [auction_date - MAX_DAYS_BEFORE, auction_date]
    distinct_keys = set((bk, ad) for (bk, ad) in au_by_bucket_date)
    used_listing_ids_pre: set[int] = used_listing_ids.copy()  # respecter les lots déjà consommés

    for (bk, auction_date) in distinct_keys:
        aus = au_by_bucket_date.get((bk, auction_date), [])
        if not aus:
            continue

        # Collecter les listings dans la fenêtre temporelle
        lsts: list = []
        if auction_date:
            for d_off in range(MAX_DAYS_BEFORE + 1):
                d = auction_date - timedelta(days=d_off)
                lsts.extend(
                    l for l in lst_by_bucket_date.get((bk, d), [])
                    if l.id not in used_listing_ids_pre
                )
        else:
            lsts = [l for l in lst_by_bucket_date.get((bk, None), [])
                    if l.id not in used_listing_ids_pre]

        if not lsts:
            continue

        batch = _assign_batch(
            aus, lsts,
            au_model, lst_model,
            au_price, au_date,
            lst_price, lst_date,
        )
        for aid_key, (lst, sc, margin) in batch.items():
            if lst.id not in used_listing_ids_pre:
                assignments[aid_key] = (lst, sc, margin)

    # ── Application des résultats fuzzy/positionnel ───────────────────────────
    # (les auctions traitées par le pont lot sont exclues via already_handled)

    for au in auctions:
        if id(au) in already_handled:
            continue  # déjà traité par la pré-passe lot déterministe

        old_year = au.year
        match = assignments.get(id(au))

        if match is not None:
            best, best_score, margin = match
            if best.id in used_listing_ids:
                # Collision (deux buckets ont assigné le même listing) → ignorer
                match = None

        if match is not None:
            best, best_score, margin = match
            confidence = "high" if margin >= MATCH_MARGIN_MIN else "review"

            if confidence == "high":
                used_listing_ids.add(best.id)
                stats["linked_high"] += 1
                new_year = best.year if _valid_year(best.year) else None
                if au.year != new_year:
                    stats["year_changed"] += 1
                if old_year is not None and new_year is None:
                    stats["year_cleared"] += 1
                if not dry_run:
                    au.year = new_year
                    au.mileage_km = best.mileage_km
                    au.start_price_eur = best.start_price_eur
                    au.match_confidence = "high"
                    au.matched_listing_id = best.id
                    au.condition_score = best.condition_score
                    if best.variant:
                        au.variant = best.variant
                    best.linked_auction_id = au.id
                if verbose and len(stats["examples"]) < 20:
                    stats["examples"].append(
                        f"[HIGH ] AU#{au.id} '{au.model_raw}' ({au.lot_number}) <-"
                        f"LST#{best.id} '{best.model_raw}' "
                        f"[score={best_score:.0f} marge={margin:.0f}] year {old_year}→{new_year}"
                    )
            else:
                stats["needs_review"] += 1
                if old_year is not None:
                    stats["year_cleared"] += 1
                if not dry_run:
                    au.year = None
                    au.mileage_km = None
                    au.start_price_eur = None
                    au.condition_score = None
                    au.match_confidence = "review"
                    au.matched_listing_id = best.id
                if verbose and sum(1 for e in stats["examples"] if "REVIEW" in e) < 6:
                    stats["examples"].append(
                        f"[REVIEW] AU#{au.id} '{au.model_raw}' ({au.lot_number}) : "
                        f"marge={margin:.1f} < {MATCH_MARGIN_MIN} → à vérifier"
                    )
        else:
            stats["unmatched"] += 1
            if old_year is not None:
                stats["year_cleared"] += 1
            if not dry_run:
                au.year = None
                au.mileage_km = None
                au.start_price_eur = None
                au.condition_score = None
                au.match_confidence = None
                au.matched_listing_id = None

    if not dry_run:
        db.commit()

    return stats
