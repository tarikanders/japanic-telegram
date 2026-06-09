#!/usr/bin/env python3
"""
Lance le sync Telegram en standalone (sans serveur FastAPI).
Lit le .env a la racine du projet, charge les credentials, appelle run_sync().

Usage:
    cd backend && python scripts/run_sync.py
"""
import os
import sys
import asyncio

# Chemin vers backend/
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Chemin vers la racine du projet (un niveau au-dessus de backend/)
_ROOT = os.path.dirname(_BACKEND)

sys.path.insert(0, _BACKEND)

# Charger le .env depuis la racine
_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Le scraper cherche le fichier de session dans backend/ par defaut.
# On ne surcharge que si TELEGRAM_SESSION_FILE n'est pas deja defini.
session_file = os.environ.get("TELEGRAM_SESSION_FILE", os.path.join(_BACKEND, "telegram_session"))
if not os.path.isabs(session_file):
    session_file = os.path.join(_BACKEND, session_file)
os.environ["TELEGRAM_SESSION_FILE"] = session_file

print(f"Session file : {session_file}.session  exists={os.path.exists(session_file + '.session')}")
print(f"Channel      : {os.getenv('TELEGRAM_CHANNEL')}")
print(f"API ID       : {os.getenv('TELEGRAM_API_ID')}")
print()


async def _main():
    from services.scraper import run_sync

    total_printed = [0]

    async def log(msg: str):
        total_printed[0] += 1
        if total_printed[0] <= 200 or total_printed[0] % 500 == 0:
            print(f"  {msg}")
        elif total_printed[0] == 201:
            print("  ... (logs abregees, affichage tous les 500)")

    print("Demarrage du sync...")
    result = await run_sync(log_callback=log)
    print()
    print("Resultat :", result)


asyncio.run(_main())
