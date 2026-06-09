<div align="center">

# JapanicTelegram — Japan Auction Intelligence

**Track Japanese car auction prices scraped from Telegram. Search, filter, visualize.**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![GCP](https://img.shields.io/badge/GCP_Cloud_Run-4285F4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)

</div>

---

## What it does

JapanicTelegram scrapes Japanese car auction lots posted to a Telegram channel and exposes them through a searchable, filterable dashboard. The goal: get real market price data for JDM cars without manually scrolling through thousands of Telegram messages.

- Search any model (`86`, `Silvia`, `Supra`...) and instantly see historical auction prices
- Filter by mileage range to compare like-for-like
- Visualize price trends over time with scatter plots and line charts
- Analytics: avg, median, min/max, daily rate, total count
- Admin panel to trigger manual syncs and watch live scraper logs

## Features

| Feature | Details |
|---------|---------|
| Incremental scrape | Telethon syncs only new messages since last run |
| Fuzzy model matching | `rapidfuzz` normalizes model names (`"Civic Type-R"` → `"Civic Type R"`) |
| Dual message parser | Handles Telegram auction format Type1 and Type2 |
| Price analytics | avg, median, min/max, scatter, trend line |
| Auth-protected admin | JWT login, sync trigger, real-time WebSocket logs |
| GCP scheduled sync | Cloud Scheduler fires every 6h automatically |

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + SQLAlchemy + SQLite (upgradeable to PostgreSQL) |
| Frontend | React (Vite) + Recharts |
| Scraper | Telethon (Telegram MTProto) |
| Deployment | Single Docker container on Google Cloud Run |
| Secrets | GCP Secret Manager |
| CI/CD | Cloud Build (`cloudbuild.yaml`) |

## Local development

```bash
cp .env.example .env
# Fill in TELEGRAM_API_ID, TELEGRAM_API_HASH, ADMIN_PASSWORD, SECRET_KEY

# Backend
cd backend
pip install -r ../requirements.txt
python init_db.py
uvicorn main:app --reload       # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev                     # http://localhost:5173

# Initial Telegram sync (prompts for phone + OTP once, then saves session)
cd backend
python -c "import asyncio; from services.scraper import run_sync; asyncio.run(run_sync())"
```

## Docker

```bash
docker build -t japan-auction .
docker run -p 8080:8080 --env-file .env japan-auction
```

## GCP Cloud Run deployment

```bash
# 1. Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com

# 2. Store secrets
echo -n "YOUR_API_ID"   | gcloud secrets create telegram-api-id  --data-file=-
echo -n "YOUR_API_HASH" | gcloud secrets create telegram-api-hash --data-file=-
echo -n "admin_pass"    | gcloud secrets create admin-password    --data-file=-
openssl rand -hex 32    | gcloud secrets create secret-key        --data-file=-

# 3. Build & deploy
PROJECT_ID=$(gcloud config get-value project)
REGION=europe-west1
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/japan-auction/app:latest .
docker push $REGION-docker.pkg.dev/$PROJECT_ID/japan-auction/app:latest
gcloud run deploy japan-auction-app \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/japan-auction/app:latest \
  --region=$REGION --platform=managed --allow-unauthenticated \
  --memory=512Mi --cpu=1 --min-instances=0 --max-instances=5 \
  --set-secrets="TELEGRAM_API_ID=telegram-api-id:latest,TELEGRAM_API_HASH=telegram-api-hash:latest,ADMIN_PASSWORD=admin-password:latest,SECRET_KEY=secret-key:latest" \
  --set-env-vars="TELEGRAM_CHANNEL=@your_channel_name"

# 4. Scheduled sync every 6h
SERVICE_URL=$(gcloud run services describe japan-auction-app --region=$REGION --format='value(status.url)')
gcloud scheduler jobs create http japan-auction-sync \
  --location=$REGION --schedule="0 */6 * * *" \
  --uri="$SERVICE_URL/api/admin/sync" --http-method=POST
```

## Project structure

```
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # SQLAlchemy models
│   ├── routers/
│   │   ├── search.py        # /api/models, /api/search, /api/stats, /api/lot
│   │   ├── admin.py         # /api/admin/status, /api/admin/sync, WS logs
│   │   └── auth.py          # /api/auth/login
│   └── services/
│       ├── scraper.py       # Telethon incremental sync
│       ├── parser.py        # Message parsing (Type1 + Type2)
│       ├── normalizer.py    # Model name normalization via rapidfuzz
│       └── stats.py         # Price analytics
├── frontend/
│   └── src/
│       ├── pages/           # Search, LotDetail, Admin
│       └── components/      # SearchBar, StatsCards, Charts, ResultsTable
├── Dockerfile
├── cloudbuild.yaml
└── requirements.txt
```

## Telegram API credentials

1. Go to [my.telegram.org](https://my.telegram.org)
2. Login → API development tools → Create app
3. Copy `api_id` and `api_hash` into `.env`
