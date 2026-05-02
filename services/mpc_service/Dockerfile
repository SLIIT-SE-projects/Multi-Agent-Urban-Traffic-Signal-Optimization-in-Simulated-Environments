# syntax=docker/dockerfile:1.6
# ─────────────────────────────────────────────────────────────────────────
# MPC Service — FastAPI HTTP wrapper around services/mpc_traffic_control.
#
# Mirrors the host repo layout at /workspace/ so the service can import
# from /workspace/services/mpc_traffic_control/src at runtime (mounted volume).
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace/services/mpc_service

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /workspace/services/mpc_service/requirements.txt
RUN pip install -r /workspace/services/mpc_service/requirements.txt

COPY . /workspace/services/mpc_service

ENV HOST=0.0.0.0 \
    PORT=8003 \
    WEIGHTS_DIR=/workspace/services/mpc_traffic_control/data \
    SCENARIOS_DIR=/workspace/simulation_and_control_panel/scenarios \
    MAX_INFERENCE_MS=2000 \
    DECISION_INTERVAL_STEPS=15

EXPOSE 8003

CMD ["python", "main.py"]
