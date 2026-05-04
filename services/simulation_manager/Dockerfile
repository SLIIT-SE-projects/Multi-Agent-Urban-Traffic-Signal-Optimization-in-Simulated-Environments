# syntax=docker/dockerfile:1.6
# ─────────────────────────────────────────────────────────────────────────
# Simulation Manager — owns SUMO/TraCI loop and arbitration.
#
# In SUMO_MODE=remote (default for Docker), this image does NOT contain
# the SUMO C++ binary; it only needs the Python `traci` and `sumolib`
# packages. SUMO runs on the host (sumo-gui native window).
#
# In SUMO_MODE=local, this image expects sumo to be available on PATH and
# $SUMO_HOME to be set. Local mode is rare in Docker — mainly for
# non-Docker dev where the same code runs without a container.
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# We mirror the host repo layout inside the container so the existing
# relative paths in optimizers/gnn_adapter.py, mpc_adapter.py, and
# evps_adapter.py keep resolving correctly:
#   /workspace/                                  ← repo root mirror
#   /workspace/services/simulation_manager/      ← WORKDIR (this image)
#   /workspace/services/gnn_optimizer/           ← mounted at runtime
#   /workspace/services/mpc_traffic_control/     ← mounted at runtime
#   /workspace/services/emergency_vehicle_preemption/ ← mounted at runtime
#   /workspace/model_weights/                    ← mounted at runtime
#   /workspace/data/                             ← mounted at runtime
#   /workspace/simulation_and_control_panel/scenarios/ ← mounted at runtime
WORKDIR /workspace/services/simulation_manager

# Build tooling for native wheels (numpy, torch, etc.). Removed after install.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /workspace/services/simulation_manager/requirements.txt
RUN pip install --default-timeout=1000 --retries 10 --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /workspace/services/simulation_manager/requirements.txt

COPY . /workspace/services/simulation_manager

# Defaults assume Docker / remote SUMO. Override via docker-compose env or .env.
ENV SUMO_MODE=remote \
    SUMO_HOST=host.docker.internal \
    SUMO_PORT=8813 \
    USE_GUI=0 \
    HOST=0.0.0.0 \
    PORT=5000 \
    PROJECT_ROOT=/workspace \
    SCENARIOS_DIR=/workspace/simulation_and_control_panel/scenarios

EXPOSE 5000

CMD ["python", "app.py"]
