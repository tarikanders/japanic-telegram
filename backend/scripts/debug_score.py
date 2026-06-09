"""Valide l'extraction score sur 3 fiches réelles avant le re-scrape complet."""
import asyncio, os, sys
from io import BytesIO
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from database import SessionLocal
from models import Listing
from services.lot_ocr import _extract_score_from_text

async def main():
    from google.cloud import vision as gv
    from telethon import TelegramClient

    db = SessionLocal()
    listings = db.query(Listing).filter(
        Listing.grouped_id.isnot(None),
    ).order_by(Listing.id).limit(3).all()
    db.close()

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    channel = os.getenv("TELEGRAM_CHANNEL")
    session_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "telegram_session")

    client = TelegramClient(session_file, int(api_id), api_hash)
    await client.connect()

    ok = 0
    for lst in listings:
        print(f"\n{'='*60}")
        print(f"Listing #{lst.id}  model={lst.model_raw}")
        try:
            msgs = []
            async for msg in client.iter_messages(channel, min_id=lst.telegram_message_id - 10,
                                                   max_id=lst.telegram_message_id + 10, reverse=True):
                if getattr(msg, "grouped_id", None) == lst.grouped_id:
                    msgs.append(msg)
            photo_msgs = sorted([m for m in msgs if m.media], key=lambda m: m.id)
            if not photo_msgs:
                print("  Pas de photo")
                continue
            buf = BytesIO()
            await photo_msgs[-1].download_media(file=buf)
            img = buf.getvalue()
            vision_client = gv.ImageAnnotatorClient()
            resp = vision_client.text_detection(gv.Image(content=img))
            ocr_text = resp.text_annotations[0].description if resp.text_annotations else ""

            score = _extract_score_from_text(ocr_text)
            print(f"  score extrait : {score!r}")

            # Fenêtre autour de 内装 pour debug
            idx = ocr_text.find("内装")
            if idx >= 0:
                window = repr(ocr_text[max(0, idx-40):idx+20])
                print(f"  contexte 内装 : {window}")
            else:
                print("  内装 absent — texte (200) :", repr(ocr_text[:200]))

            if score is not None:
                ok += 1
        except Exception as e:
            print(f"  Erreur: {e}")
        await asyncio.sleep(1)

    await client.disconnect()
    print(f"\n{'='*60}")
    print(f"Score extrait : {ok}/3")
    if ok >= 2:
        print("GO — lancer le re-scrape complet")
    else:
        print("NOK — revoir les patterns avant re-scrape")

asyncio.run(main())
