# syntax=docker/dockerfile:1.6
# ─────────────────────────────────────────────────────────────────────────
# Dashboard API Gateway — FastAPI service (port 8000).
#
# Owns:
#   - Browser-facing REST + WebSocket gateway (Traffic Dashboard, Sim UI)
#   - Model registry (Phase 6+)
#   - Telemetry relay from Redis pub/sub to UI
#
# IMPORTANT: build context must be the repository root (not this folder)
# so the Dockerfile can COPY both services/dashboard_api and the shared
# services/config.py.
#   docker compose build dashboard_api
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace

WORKDIR /workspace/services/dashboard_api

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY services/dashboard_api/requirements.txt /workspace/services/dashboard_api/requirements.txt
RUN pip install -r /workspace/services/dashboard_api/requirements.txt

# The dashboard_api imports `from services.config import Config` so the
# parent directory must also be available on the path. PYTHONPATH=/workspace
# (set above) plus copying both files makes that work.
COPY services/dashboard_api /workspace/services/dashboard_api
COPY services/config.py /workspace/services/config.py

ENV HOST=0.0.0.0 \
    PORT=8000 \
    REDIS_HOST=redis \
    REDIS_PORT=6379 \
    DASHBOARD_CORS_ORIGIN=http://localhost:5173

EXPOSE 8000

CMD ["uvicorn", "services.dashboard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
