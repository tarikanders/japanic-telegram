#!/usr/bin/env python3
"""
Re-derive result_line_index depuis le raw_text stocke pour chaque auction.

Probleme : des doublons de result_line_index existent en DB quand deux messages
de resultats physiques distincts ont ete stockes sous le meme telegram_message_id.
Exemple constate : session 2025-01-16 (msg_id=90523), 6 index dupliques,
rendant l'entree de la DP monotone ambigue => passe positionnelle inutilisable.

Approche :
  1. Pour chaque groupe (telegram_message_id) d'auctions :
     a. Collecter TOUS les raw_text distincts du groupe (il peut y en avoir plusieurs
        si deux messages physiques ont le meme msg_id apres scraping).
     b. Re-parser chaque raw_text via parse_results_message.
     c. Appairier chaque ligne parsee a son auction par lot_number.
     d. Réécrire result_line_index avec un ordinal unique et strictement croissant
        GLOBAL au sein du groupe (lot_number → position dans la concaténation
        ordonnée de tous les raw_texts).
  2. Logguer les groupes où des doublons ont ete detectes avant correction.
  3. No-op si raw_text est NULL sur toutes les auctions du groupe.

Idempotent : re-executer produit le meme resultat.

Usage:
    cd backend && python scripts/reparse_line_index.py          # dry-run (rien ecrit)
    cd backend && python scripts/reparse_line_index.py --apply  # applique en DB
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Auction
from services.parser import parse_results_message


def _collect_lot_index_map(auctions_in_msg: list) -> dict[str, int]:
    """
    Construit lot_number -> new_line_index en re-parsant TOUS les raw_text
    du groupe (plusieurs messages physiques possibles sous un meme telegram_message_id).

    Strategie :
    - Rassembler les raw_texts distincts (deduplique).
    - Pour chaque raw_text, parser les lignes et noter les lots presents.
    - Affecter un index global croissant a chaque lot, dans l'ordre de premiere
      apparition : raw_text_0 lots d'abord (indices 0..N0-1), puis raw_text_1
      (indices N0..N0+N1-1), etc.
    - Si un lot apparait dans PLUSIEURS raw_texts, garder seulement la premiere
      occurrence (cas de duplication de scraping).

    Retourne {} si aucun raw_text disponible.
    """
    # Collecter les raw_text distincts (ordonnes par l'id Python de l'auction
    # qui les porte, pour un ordre stable et reproductible)
    seen_texts: set[str] = set()
    raw_texts_ordered: list[str] = []
    for au in sorted(auctions_in_msg, key=lambda a: a.id):
        if au.raw_text and au.raw_text not in seen_texts:
            seen_texts.add(au.raw_text)
            raw_texts_ordered.append(au.raw_text)

    if not raw_texts_ordered:
        return {}

    lot_to_idx: dict[str, int] = {}
    global_counter = 0

    for raw_text in raw_texts_ordered:
        parsed = parse_results_message(raw_text)
        for r in parsed:
            if r.lot_number not in lot_to_idx:
                lot_to_idx[r.lot_number] = global_counter
                global_counter += 1
            # Si deja vu dans un raw_text precedent : on ignore (duplication)

    return lot_to_idx


def reparse_group(auctions_in_msg: list, dry_run: bool) -> dict:
    """
    Re-derive result_line_index pour un groupe d'auctions partageant
    le meme telegram_message_id.

    Retourne un dict de stats pour les compteurs globaux.
    """
    stats = {"fixed": 0, "no_raw_text": 0, "lot_not_found": 0, "dup_before": 0}

    # Detecter les doublons AVANT correction
    idxs = [au.result_line_index for au in auctions_in_msg if au.result_line_index is not None]
    dup_count = len(idxs) - len(set(idxs))
    if dup_count > 0:
        stats["dup_before"] = dup_count

    lot_to_idx = _collect_lot_index_map(auctions_in_msg)

    if not lot_to_idx:
        stats["no_raw_text"] = len(auctions_in_msg)
        return stats

    for au in auctions_in_msg:
        if au.lot_number not in lot_to_idx:
            stats["lot_not_found"] += 1
            continue

        new_idx = lot_to_idx[au.lot_number]
        if au.result_line_index != new_idx:
            stats["fixed"] += 1
            if not dry_run:
                au.result_line_index = new_idx

    return stats


def main():
    apply = "--apply" in sys.argv
    dry_run = not apply

    print("=" * 64)
    print(f"REPARSE LINE INDEX - mode : {'DRY-RUN' if dry_run else 'APPLY'}")
    print("=" * 64)

    db = SessionLocal()

    # Charger TOUTES les auctions avec un telegram_message_id
    all_auctions = (
        db.query(Auction)
        .filter(Auction.telegram_message_id.isnot(None))
        .order_by(Auction.telegram_message_id, Auction.id)
        .all()
    )

    # Grouper par telegram_message_id
    groups: dict[int, list] = defaultdict(list)
    for au in all_auctions:
        groups[au.telegram_message_id].append(au)

    total_stats = {
        "groups": 0,
        "groups_with_dups": 0,
        "groups_with_multi_raw": 0,
        "fixed": 0,
        "no_raw_text": 0,
        "lot_not_found": 0,
        "total_dups_before": 0,
    }
    problem_examples: list[str] = []

    for msg_id, auctions in sorted(groups.items()):
        # Compter les raw_texts distincts
        raw_texts = {au.raw_text for au in auctions if au.raw_text}
        if len(raw_texts) > 1:
            total_stats["groups_with_multi_raw"] += 1

        # Doublons avant correction
        idxs = [au.result_line_index for au in auctions if au.result_line_index is not None]
        has_dups = len(idxs) != len(set(idxs))

        total_stats["groups"] += 1
        if has_dups:
            total_stats["groups_with_dups"] += 1

        s = reparse_group(auctions, dry_run)
        total_stats["fixed"] += s["fixed"]
        total_stats["no_raw_text"] += s["no_raw_text"]
        total_stats["lot_not_found"] += s["lot_not_found"]
        total_stats["total_dups_before"] += s["dup_before"]

        if (has_dups or len(raw_texts) > 1) and len(problem_examples) < 12:
            dup_idxs = sorted(set(x for x in idxs if idxs.count(x) > 1))
            problem_examples.append(
                f"  msg_id={msg_id}: {len(auctions)} auctions, "
                f"{len(raw_texts)} raw_texts, "
                f"idx_dupliques={dup_idxs[:6]} | "
                f"fixed={s['fixed']} lot_not_found={s['lot_not_found']}"
            )

    if not dry_run:
        db.commit()
        print("DB mise a jour.")

    print(f"\nResultats :")
    print(f"  Groupes traites              : {total_stats['groups']:,}")
    print(f"  Groupes avec index dupliques : {total_stats['groups_with_dups']:,}")
    print(f"  Groupes multi-raw_text       : {total_stats['groups_with_multi_raw']:,}")
    print(f"  Doublons totaux (avant)      : {total_stats['total_dups_before']:,}")
    print(f"  result_line_index fixes      : {total_stats['fixed']:,}")
    print(f"  Lots sans raw_text           : {total_stats['no_raw_text']:,}")
    print(f"  Lots absents du raw_text     : {total_stats['lot_not_found']:,}")

    if problem_examples:
        print(f"\nGroupes problematiques ({min(len(problem_examples), 12)}) :")
        for ex in problem_examples:
            print(ex)

    if dry_run:
        print(f"\n-> DRY-RUN. Rien ecrit.")
        print(f"   Lancer avec --apply pour appliquer.")
    else:
        print(f"\nControle : verifier l'absence de doublons :")
        print(f"  SELECT telegram_message_id, result_line_index, COUNT(*)")
        print(f"  FROM auctions GROUP BY 1,2 HAVING COUNT(*)>1")


if __name__ == "__main__":
    main()
