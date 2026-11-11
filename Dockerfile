# EvenSteven: one container that builds the React app and serves it from the FastAPI backend.

# 1. build the frontend into frontend/dist
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. the API, serving the built frontend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/evensteven.db
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN mkdir -p /data && useradd --create-home appuser && chown -R appuser /data /app
USER appuser
# Render (and most hosts) pass the port in $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8090} --proxy-headers --forwarded-allow-ips='*'"]
