# syntax=docker/dockerfile:1.6
# ─────────────────────────────────────────────────────────────────────────
# GNN Service — FastAPI HTTP wrapper around services/gnn_optimizer.
#
# Mirrors the host repo layout at /workspace/ so the service can import
# from /workspace/services/gnn_optimizer/src at runtime (mounted volume).
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace/services/gnn_service

# Build tooling for native wheels (torch, torch-geometric, numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /workspace/services/gnn_service/requirements.txt
RUN pip install --default-timeout=1000 --retries 10 --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /workspace/services/gnn_service/requirements.txt

COPY . /workspace/services/gnn_service

ENV HOST=0.0.0.0 \
    PORT=8002 \
    MODEL_WEIGHTS_PATH=/workspace/model_weights/final_marl_model_best.pth \
    SCENARIOS_DIR=/workspace/simulation_and_control_panel/scenarios \
    MAX_INFERENCE_MS=2000 \
    DECISION_INTERVAL_STEPS=15 \
    MC_DROPOUT_SAMPLES=20

EXPOSE 8002

CMD ["python", "main.py"]
