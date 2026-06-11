# JapanicTelegram — Japan Auction Intelligence

Scrape les lots d'enchères auto japonaises postés sur un canal Telegram → dashboard de recherche/filtre/visualisation des prix.

## Stack
- **Backend** : FastAPI (Python 3.11) + SQLAlchemy + SQLite. Scraping Telegram via **Telethon**.
- **Front** : React (JS, pas TS) + Vite. Build copié dans `backend/static/`.
- **lbc-service** : micro-service Node séparé (port 3001) qui interroge Leboncoin (`leboncoin-api-search`). Source = `server.ts` → build esbuild → `server.cjs`.
- **Deploy** : Docker multi-stage → Cloud Run (`japan-auction-app`), orchestré par **supervisord** (uvicorn + node). SQLite sur volume Cloud Storage monté à `/data`. Secrets via GCP Secret Manager.

## Commandes
```bash
# Backend
uvicorn main:app --app-dir backend --reload          # dev local
pytest backend                                       # tests (~165, doivent passer)

# Frontend
cd frontend && npm run dev        # vite
cd frontend && npm run build      # -> backend/static

# lbc-service
cd lbc-service && npm run build   # esbuild server.ts -> server.cjs
cd lbc-service && npm start       # node server.cjs
```
En prod, `supervisord.conf` lance : `uvicorn main:app --host 0.0.0.0 --port 8080` + `node /app/lbc-service/server.cjs` (LBC_PORT=3001).

## Architecture (`backend/`)
- `routers/` : admin, search, archive, auth, exchange, watchlist, telegram_setup.
- `services/` : pipeline de traitement —
  - `scraper.py` (Telethon) → `parser.py` → `normalizer.py` → `linker.py` (878 lignes, **matching Hungarian via scipy**) → `stats.py`.
  - `lot_ocr.py` : OCR du numéro de lot via **Google Cloud Vision**.
  - `phases.py` : orchestration des phases du pipeline.
- `models.py`, `database.py`, `init_db.py`, `sync.py` (sync Telegram).
- `scripts/` : migrations ad-hoc + outils d'audit (`audit_db.py`, `check_scores.py`, `variant_audit.py`...). Beaucoup de `migrate_*` déjà jouées → à archiver.
- `tests/` : test_linker, test_normalizer, test_parser, test_phases. Gros : `test_pipeline.py` (988 lignes).

## Pièges (vérifiés)
- ⚠️ **NE JAMAIS commit** : `.session`/`.session-journal` (sessions Telegram), `.env`, `*.db`. Tous gitignorés — garder ainsi.
- ⚠️ **13 backups DB (`*.backup_*`) = 446 MB sur disque** dans `backend/`, non trackés mais jamais purgés. Besoin d'une rotation (garder les 3 derniers).
- ⚠️ **`lbc-service/server.cjs` = artefact de build** régénéré par le Dockerfile depuis `server.ts` (jamais copié du repo dans l'image). Éditer `server.ts`, pas le `.cjs`. (`server.js`, vieil orphelin périmé, a été supprimé.)
- ⚠️ **Déploiement 100% Docker** (`cloudbuild.yaml` → `docker build .`). Rien ne contourne le Dockerfile.
- ⚠️ Dépendances optionnelles avec **fallback gracieux si absentes** : `scipy` (linker), `Pillow` + `google-cloud-vision` (OCR). Le code ne doit pas planter sans elles.
- 📌 **Tier 3 OCR bloqué** : Tesseract KO sous Windows, Cloud Vision ~$27 estimé. Spike `scripts/spike_ocr_lot.py` à lancer avant tout re-scrape massif.

## Conventions
- Sous-module git (`JapanicTelegram`). `git fetch --all` avant toute op git.
- Manipule auth Telegram + JWT + scraping → passer `/security-review` avant un push sensible.
