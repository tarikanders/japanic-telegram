# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent
COPY frontend/ .
RUN npm run build

# Stage 2: Build lbc-service bundle
FROM node:20-slim AS lbc-builder
WORKDIR /app/lbc
COPY lbc-service/package.json ./
RUN npm install --silent
COPY lbc-service/server.ts ./
RUN ./node_modules/.bin/esbuild server.ts --bundle --platform=node --outfile=server.cjs --format=cjs

# Stage 3: Final runtime image
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /app/backend/static ./backend/static
COPY --from=lbc-builder /app/lbc/server.cjs ./lbc-service/server.cjs
COPY supervisord.conf /etc/supervisor/conf.d/app.conf

ENV PYTHONPATH=/app/backend
ENV PORT=8080
ENV LBC_PORT=3001

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/app.conf"]
