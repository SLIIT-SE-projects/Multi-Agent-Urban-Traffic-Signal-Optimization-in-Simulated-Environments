# GNN Service

FastAPI HTTP service wrapping the Recurrent HGAT MARL traffic signal
controller from `services/gnn_optimizer/`. Conforms to the standard model
contract in `contracts/openapi/model_service.yaml`.

This is the first model service split out of the monolithic Simulation
Manager (Phase 3 of the migration).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/info` | Model metadata |
| GET | `/health` | Liveness + readiness |
| POST | `/reset` | Initialize a new session, build the heterograph, load weights |
| POST | `/predict` | Compute actions for a snapshot (called every 15 steps) |
| POST | `/teardown` | Release the active session |

Full schemas in `contracts/schemas/`.

## Run locally

```bash
cd services/gnn_service
pip install -r requirements.txt
export MODEL_WEIGHTS_PATH=/path/to/repo/model_weights/final_marl_model_best.pth
export SCENARIOS_DIR=/path/to/repo/simulation_and_control_panel/scenarios
python main.py
```

The service listens on `:8002`.

## Run in Docker

The service runs as part of the root `docker-compose.yml`. The Manager
container reaches it via `http://gnn_service:8002` (compose network DNS).

```bash
docker compose up gnn_service
```

## How the Manager calls it

The Manager's `HttpModelRouter` (in `services/simulation_manager/routing/http_router.py`)
calls this service when:

```bash
MODEL_GNN_URL=http://gnn_service:8002 docker compose up
```

If `MODEL_GNN_URL` is not set, the Manager falls back to its in-process
GNN adapter (Phase 2 behavior).

## Inference details

The service preserves the exact pipeline from
`services/simulation_manager/optimizers/gnn_adapter.py`:

1. Build heterograph from `.net.xml` using `TrafficGraphBuilder`
2. Run **MC Dropout** with 20 samples for uncertainty quantification
3. Argmax over mean probabilities → binary switch action per intersection
4. Single deterministic forward pass to advance the GRU hidden state

## Per-session state

The model maintains GRU hidden state across `/predict` calls for the same
`session_id`. Calling `/reset` clears it. Single-tenant — only one active
session at a time. Multi-tenant support deferred to Phase 6+.

## Dependencies

- `torch`, `torch-geometric` — model + graph batching
- `sumolib` — `.net.xml` parsing (no TraCI / no SUMO binary required)
- `fastapi`, `uvicorn` — HTTP

The container does **not** need the SUMO C++ binary — it only needs to
parse `.net.xml` files, which `sumolib` does in pure Python.

## Migration status

| Phase | Status |
|---|---|
| 3 — GNN over HTTP | **Current** |
| 6 — Schema validation in /reset and /predict | Pending |
| 6 — Auth tokens for external calls | Pending |
| 7 — Reconstruct graph from network dict (drop net.xml shortcut) | Pending |
