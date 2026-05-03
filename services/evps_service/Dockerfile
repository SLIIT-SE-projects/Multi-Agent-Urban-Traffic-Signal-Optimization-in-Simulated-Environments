# syntax=docker/dockerfile:1.6
# ─────────────────────────────────────────────────────────────────────────
# EVPS Service — FastAPI wrapper around the EV preemption pipeline.
#
# Mirrors the host repo layout at /workspace/. Mounts the model files
# from /workspace/services/emergency_vehicle_preemption/.
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace/services/evps_service

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /workspace/services/evps_service/requirements.txt
RUN pip install -r /workspace/services/evps_service/requirements.txt

COPY . /workspace/services/evps_service

ENV HOST=0.0.0.0 \
    PORT=8004 \
    EVPS_MODELS_DIR=/workspace/services/emergency_vehicle_preemption \
    SEQUENCE_LENGTH=10 \
    ETA_SMOOTHING_ALPHA=0.3 \
    MAX_INFERENCE_MS=500

EXPOSE 8004

CMD ["python", "main.py"]
