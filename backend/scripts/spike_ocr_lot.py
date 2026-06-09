#!/usr/bin/env python3
"""
Phase 0 — Spike de validation : OCR du numéro de lot sur les fiches Telegram.

OBJECTIF : prouver (ou infirmer) que l'OCR lit le lot sur les fiches-rapport
avant de coder tout le pipeline. Script jetable — résultat attendu = Go/No-Go.

USAGE (depuis backend/) :
    python scripts/spike_ocr_lot.py --sample 30
    python scripts/spike_ocr_lot.py --sample 30 --engine vision   # si Tesseract insuffisant

PRÉ-REQUIS :
  - Session Telegram existante (exécuter `python telegram_login.py` d'abord)
  - pip install Pillow pytesseract   (+  binaire Tesseract : winget install UB-Mannheim.TesseractOCR)
  - Pour Vision : pip install google-cloud-vision  + GOOGLE_APPLICATION_CREDENTIALS=...

SORTIE :
  - Pour chaque album : index photo, texte OCR tronqué, candidats lot, statut
  - Tableau récap : taux de lecture, position fiche (constante ?), exemples d'erreurs
"""
import asyncio
import argparse
import os
import re
import sys
from io import BytesIO
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── OCR imports (optionnels) ─────────────────────────────────────────────────
_HAS_TESSERACT = False
_HAS_VISION = False
try:
    import pytesseract
    from PIL import Image
    _HAS_TESSERACT = True
except ImportError:
    pass

try:
    from google.cloud import vision as _gv
    _HAS_VISION = True
except ImportError:
    pass


# ── Config ───────────────────────────────────────────────────────────────────
# Anchor: lot is always right before 初度登録年月 on fiche (positional, not range-based).
LOT_ANCHOR_PATTERN = re.compile(r"[a-zA-Z]?(\d{4,6})\s*初度登録年月")
# Fallback for corners without the anchor label visible
LOT_FALLBACK_PATTERN = re.compile(r"(?<!\d)[a-zA-Z]?([5-9]\d{4})(?!\d)")


def _preprocess_pil(img_bytes: bytes):
    """Grayscale + léger upscale + binarisation (améliore Tesseract sur fiches denses)."""
    from PIL import Image, ImageEnhance, ImageFilter
    img = Image.open(BytesIO(img_bytes)).convert("L")
    # Upscale si trop petite (Tesseract aime 300 dpi)
    if img.width < 800:
        scale = 800 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def _ocr_tesseract(img_bytes: bytes) -> str:
    """OCR via Tesseract — retourne tout le texte extrait."""
    img = _preprocess_pil(img_bytes)
    # psm 6 = bloc de texte uniforme ; pas de whitelist pour voir tout le texte
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(img, config=config)


def _ocr_vision(img_bytes: bytes) -> str:
    """OCR via Google Cloud Vision."""
    client = _gv.ImageAnnotatorClient()
    image = _gv.Image(content=img_bytes)
    response = client.text_detection(image=image)
    if response.text_annotations:
        return response.text_annotations[0].description
    return ""


def ocr_image(img_bytes: bytes, engine: str) -> str:
    if engine == "vision" and _HAS_VISION:
        return _ocr_vision(img_bytes)
    if _HAS_TESSERACT:
        return _ocr_tesseract(img_bytes)
    return ""


def extract_lot_candidates(text: str) -> list[str]:
    """Extrait le(s) candidat(s) numéro de lot : anchor positionnel d'abord, repli range."""
    m = LOT_ANCHOR_PATTERN.search(text)
    if m:
        return [m.group(1)]
    return LOT_FALLBACK_PATTERN.findall(text)


# ── Main spike ───────────────────────────────────────────────────────────────

async def run_spike(sample_size: int = 30, engine: str = "tesseract"):
    # Vérifications pré-conditions
    if engine == "tesseract" and not _HAS_TESSERACT:
        print("✗ Tesseract/Pillow non installé. `pip install Pillow pytesseract` + binaire Tesseract.")
        print("  (winget install UB-Mannheim.TesseractOCR)")
        sys.exit(1)
    if engine == "vision" and not _HAS_VISION:
        print("✗ google-cloud-vision non installé. `pip install google-cloud-vision`")
        sys.exit(1)

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    channel = os.getenv("TELEGRAM_CHANNEL")
    if not all([api_id, api_hash, channel]):
        print("✗ Variables TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_CHANNEL manquantes.")
        sys.exit(1)

    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError
    except ImportError:
        print("✗ telethon non installé.")
        sys.exit(1)

    # Charger ~sample_size annonces récentes depuis la DB (lecture seule)
    from database import SessionLocal
    from models import Listing

    db = SessionLocal()
    # Prendre des listings ANCIENS (pas les tout récents dont les enchères ne sont pas encore en DB)
    # On skip les 50 plus récents et on prend dans les suivants.
    listings_sample = (
        db.query(Listing)
        .filter(Listing.grouped_id.isnot(None))
        .order_by(Listing.id.desc())
        .offset(50)
        .limit(sample_size)
        .all()
    )
    db.close()

    if not listings_sample:
        print("✗ Aucune annonce avec grouped_id trouvée en DB.")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"SPIKE OCR LOT — {len(listings_sample)} annonces échantillonnées, moteur={engine.upper()}")
    print(f"{'='*70}\n")

    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_name = os.getenv("TELEGRAM_SESSION_FILE", "telegram_session")
    session_file = session_name if os.path.isabs(session_name) else os.path.join(_backend_dir, session_name)

    if not os.path.exists(f"{session_file}.session"):
        print(f"✗ Fichier session introuvable : {session_file}.session")
        print("  Exécuter `python telegram_login.py` d'abord.")
        sys.exit(1)

    client = TelegramClient(session_file, int(api_id), api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("✗ Non autorisé. Exécuter `python telegram_login.py`.")
        await client.disconnect()
        sys.exit(1)

    print(f"✓ Connecté à Telegram\n")

    # Résultats spike
    results = []  # list of dicts

    for i, lst in enumerate(listings_sample):
        grouped_id = lst.grouped_id
        txt_msg_id = lst.telegram_message_id
        print(f"[{i+1:02d}/{len(listings_sample)}] Listing #{lst.id}  grouped_id={grouped_id}  txt_msg={txt_msg_id}")

        # Récupérer tous les messages de l'album : itère autour du message texte (window ±10)
        # ⚠ Telegram ne permet pas de filtrer par grouped_id directement via get_messages.
        # On itère une petite fenêtre autour du message texte et on filtre par grouped_id.
        album_messages = []
        try:
            min_id = max(1, txt_msg_id - 10)
            max_id = txt_msg_id + 10
            async for msg in client.iter_messages(channel, min_id=min_id, max_id=max_id, reverse=True):
                if getattr(msg, "grouped_id", None) == grouped_id:
                    album_messages.append(msg)
        except FloodWaitError as e:
            print(f"  ⏳ FloodWait {e.seconds}s — attente...")
            await asyncio.sleep(e.seconds)
            async for msg in client.iter_messages(channel, min_id=min_id, max_id=max_id, reverse=True):
                if getattr(msg, "grouped_id", None) == grouped_id:
                    album_messages.append(msg)
        except Exception as e:
            print(f"  ✗ Erreur récupération album: {e}")
            results.append({"listing_id": lst.id, "grouped_id": grouped_id, "error": str(e)})
            continue

        if not album_messages:
            print(f"  ⚠ Album vide (aucun message avec grouped_id={grouped_id} dans la fenêtre)")
            results.append({"listing_id": lst.id, "grouped_id": grouped_id,
                           "album_size": 0, "lot_found": False, "error": "album vide"})
            continue

        print(f"  Album: {len(album_messages)} messages")

        # Télécharger + OCR chaque photo de l'album
        photo_results = []
        for idx, msg in enumerate(album_messages):
            if not msg.media:
                photo_results.append({"idx": idx, "has_media": False, "text_ocr": "", "lot_candidates": []})
                continue
            try:
                buf = BytesIO()
                await msg.download_media(file=buf)
                img_bytes = buf.getvalue()
                if not img_bytes:
                    photo_results.append({"idx": idx, "has_media": True, "downloaded": False,
                                         "text_ocr": "", "lot_candidates": []})
                    continue

                ocr_text = ocr_image(img_bytes, engine)
                candidates = extract_lot_candidates(ocr_text)
                text_preview = ocr_text[:120].replace("\n", "↵")
                print(f"    [photo {idx}]  OCR↦ «{text_preview}»  → lots candidats: {candidates}")
                photo_results.append({
                    "idx": idx,
                    "has_media": True,
                    "downloaded": True,
                    "text_ocr": ocr_text[:300],
                    "lot_candidates": candidates,
                })
            except Exception as e:
                print(f"    [photo {idx}] ✗ Erreur: {e}")
                photo_results.append({"idx": idx, "has_media": True, "error": str(e),
                                     "text_ocr": "", "lot_candidates": []})

        # Croiser : existe-t-il une auction avec un lot parmi les candidats ?
        from database import SessionLocal as SL
        from models import Auction
        db2 = SL()
        matched_lots = []
        for pr in photo_results:
            for cand in pr.get("lot_candidates", []):
                # Fenêtre ±7j autour de la posted_date du listing
                if lst.posted_date:
                    from datetime import timedelta
                    d_min = lst.posted_date
                    d_max = lst.posted_date + timedelta(days=7)
                    hit = db2.query(Auction).filter(
                        Auction.lot_number == cand,
                        Auction.auction_date >= d_min,
                        Auction.auction_date <= d_max,
                    ).first()
                    if hit:
                        matched_lots.append({"lot": cand, "photo_idx": pr["idx"],
                                            "auction_id": hit.id, "auction_date": str(hit.auction_date)})
        db2.close()

        lot_found = len(matched_lots) > 0
        fiche_positions = [m["photo_idx"] for m in matched_lots]
        print(f"  → Lot(s) croisé(s) avec DB: {matched_lots if matched_lots else 'AUCUN'}")

        results.append({
            "listing_id": lst.id,
            "grouped_id": grouped_id,
            "album_size": len(album_messages),
            "photo_results": photo_results,
            "lot_found": lot_found,
            "matched_lots": matched_lots,
            "fiche_positions": fiche_positions,
        })

        # Anti-flood léger entre albums
        await asyncio.sleep(0.5)

    await client.disconnect()

    # ── Récap final ────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("RÉCAP SPIKE")
    print(f"{'='*70}")

    total = len(results)
    found = sum(1 for r in results if r.get("lot_found"))
    errors = sum(1 for r in results if r.get("error"))
    read_rate = found / max(1, total - errors) * 100

    print(f"  Albums traités       : {total}")
    print(f"  Erreurs / ignorés    : {errors}")
    print(f"  Lot croisé avec DB   : {found}")
    print(f"  Taux de lecture      : {read_rate:.1f}%")

    # Position de la fiche (constante ?)
    all_positions = [p for r in results for p in r.get("fiche_positions", [])]
    if all_positions:
        from collections import Counter
        pos_counts = Counter(all_positions)
        print(f"\n  Position de la fiche (index photo) : {dict(pos_counts)}")
        most_common_pos, most_common_n = pos_counts.most_common(1)[0]
        pct_const = most_common_n / len(all_positions) * 100
        print(f"  → Position dominante : photo[{most_common_pos}] ({pct_const:.0f}% des cas)")
    else:
        print("\n  ⚠ Aucune position de fiche détectée")

    print(f"\n{'='*70}")
    print("CRITÈRE GO/NO-GO")
    if read_rate >= 80:
        print(f"  ✅ GO — taux {read_rate:.1f}% ≥ 80%. Continuer avec le moteur {engine.upper()}.")
    elif read_rate >= 50:
        print(f"  ⚠ INCERTAIN — taux {read_rate:.1f}% (50-80%). Tester Cloud Vision avant de décider.")
        if engine == "tesseract":
            print("     Relancer avec --engine vision")
    else:
        print(f"  ❌ NO-GO Tesseract — taux {read_rate:.1f}% < 50%.")
        if engine == "tesseract":
            print("     Tenter Cloud Vision : python scripts/spike_ocr_lot.py --engine vision")
        else:
            print("     Cloud Vision aussi insuffisant → Tier 3 non viable. Rester Tier 1+2.")
    print(f"{'='*70}\n")

    return read_rate


def main():
    parser = argparse.ArgumentParser(description="Spike OCR lot Telegram")
    parser.add_argument("--sample", type=int, default=30, help="Nombre d'albums à tester (défaut: 30)")
    parser.add_argument("--engine", choices=["tesseract", "vision"], default="tesseract",
                        help="Moteur OCR (défaut: tesseract)")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(run_spike(sample_size=args.sample, engine=args.engine))


if __name__ == "__main__":
    main()
