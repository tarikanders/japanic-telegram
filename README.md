# Japan Auction Intelligence

Track Japanese car auction prices from a Telegram channel. Search by model, filter by mileage, visualize price trends.

## Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite (upgradable to PostgreSQL)
- **Frontend**: React (Vite) + Recharts
- **Scraper**: Telethon (incremental Telegram sync)
- **Deployment**: Single Docker container on Google Cloud Run

---

## Local Development

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your Telegram credentials
```

### 2. Backend

```bash
cd backend
pip install -r ../requirements.txt
python init_db.py          # Create DB tables
uvicorn main:app --reload  # http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### 4. Initial Telegram sync (manual)

```bash
cd backend
python -c "import asyncio; from services.scraper import run_sync; asyncio.run(run_sync())"
```

> The first run will prompt you to enter your Telegram phone number and OTP code.
> After that, a session file is saved and no login is needed again.

---

## Docker (local test)

```bash
docker build -t japan-auction .
docker run -p 8080:8080 --env-file .env japan-auction
```

---

## Google Cloud Run Deployment

### Prerequisites

- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed

### Step 1 — Enable APIs

```bash
gcloud services enable run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

### Step 2 — Create Artifact Registry repo

```bash
gcloud artifacts repositories create japan-auction \
  --repository-format=docker \
  --location=europe-west1 \
  --description="Japan Auction app images"
```

### Step 3 — Store secrets in Secret Manager

```bash
echo -n "YOUR_API_ID" | gcloud secrets create telegram-api-id --data-file=-
echo -n "YOUR_API_HASH" | gcloud secrets create telegram-api-hash --data-file=-
echo -n "your_admin_password" | gcloud secrets create admin-password --data-file=-
openssl rand -hex 32 | gcloud secrets create secret-key --data-file=-
```

### Step 4 — Build and deploy

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=europe-west1

# Build image
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/japan-auction/japan-auction-app:latest .
docker push $REGION-docker.pkg.dev/$PROJECT_ID/japan-auction/japan-auction-app:latest

# Deploy to Cloud Run
gcloud run deploy japan-auction-app \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/japan-auction/japan-auction-app:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5 \
  --set-secrets="TELEGRAM_API_ID=telegram-api-id:latest,TELEGRAM_API_HASH=telegram-api-hash:latest,ADMIN_PASSWORD=admin-password:latest,SECRET_KEY=secret-key:latest" \
  --set-env-vars="TELEGRAM_CHANNEL=@your_channel_name"
```

### Step 5 — Initialize the database (first deploy only)

```bash
SERVICE_URL=$(gcloud run services describe japan-auction-app --region=$REGION --format='value(status.url)')
echo "App live at: $SERVICE_URL"
```

Then trigger an initial sync via `/admin` in the browser (login with your ADMIN_PASSWORD).

### Step 6 — Scheduled sync (every 6h)

```bash
gcloud scheduler jobs create http japan-auction-sync \
  --location=$REGION \
  --schedule="0 */6 * * *" \
  --uri="$SERVICE_URL/api/admin/sync" \
  --http-method=POST \
  --headers="Authorization=Bearer $(curl -s -X POST $SERVICE_URL/api/auth/login -H 'Content-Type: application/json' -d '{\"password\":\"YOUR_ADMIN_PASSWORD\"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"access_token\"])')"
```

---

## Telegram API Credentials

1. Go to https://my.telegram.org
2. Login with your phone number
3. Click **API development tools**
4. Create a new app (any name/platform)
5. Copy **api_id** and **api_hash**

---

## Upgrade to PostgreSQL (Cloud SQL)

1. Create a Cloud SQL PostgreSQL instance
2. Update `DATABASE_URL`:
   ```
   postgresql://user:password@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
   ```
3. Add Cloud SQL connection to Cloud Run:
   ```bash
   gcloud run services update japan-auction-app \
     --add-cloudsql-instances=PROJECT:REGION:INSTANCE
   ```
4. Run `python init_db.py` once to create tables and indexes.

---

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # DB session management
│   ├── init_db.py           # Table creation script
│   ├── routers/
│   │   ├── search.py        # /api/models, /api/search, /api/stats, /api/lot
│   │   ├── admin.py         # /api/admin/status, /api/admin/sync, WS logs
│   │   └── auth.py          # /api/auth/login
│   └── services/
│       ├── scraper.py       # Telethon incremental sync
│       ├── parser.py        # Telegram message parsing (Type1 + Type2)
│       ├── normalizer.py    # Model name normalization via rapidfuzz
│       └── stats.py         # Price analytics (avg, median, scatter, trend)
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Search.jsx   # Main search page
│       │   ├── LotDetail.jsx # Lot detail + similar sales
│       │   └── Admin.jsx    # Admin panel + sync logs
│       └── components/
│           ├── SearchBar.jsx    # Autocomplete search
│           ├── StatsCards.jsx   # Avg/Median/Min-Max/Rate/Count
│           ├── Charts.jsx       # Scatter + Line charts
│           └── ResultsTable.jsx # Paginated results table
├── Dockerfile               # Multi-stage build (Node → Python)
├── cloudbuild.yaml          # GCP CI/CD pipeline
└── requirements.txt
```
