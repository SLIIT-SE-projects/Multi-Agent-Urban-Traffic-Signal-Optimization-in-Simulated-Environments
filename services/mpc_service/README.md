# MPC Service

FastAPI HTTP service wrapping the Model Predictive Control traffic-signal
controller from `services/mpc_traffic_control/`. Conforms to the standard
model contract in `contracts/openapi/model_service.yaml` plus a
non-contract `/internals` endpoint for the dashboard's MPC Internals tab.

This is the second model service split out of the Simulation Manager
(Phase 4 of the migration). It mirrors the architecture of `gnn_service/`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/info` | Model metadata |
| GET | `/health` | Liveness + readiness |
| POST | `/reset` | Initialize a new session, build per-TLS controllers, load LSTM weights |
| POST | `/predict` | Compute actions for a snapshot (called every 15 steps) |
| POST | `/teardown` | Release the active session |
| GET | `/internals` | **Non-contract** — MPC-specific decisions for the dashboard MPC tab |

Schemas in `contracts/schemas/`.

## Action type

MPC emits `set_phase` actions. The `value` field is the **absolute SUMO
phase index** (already mapped from MPC's internal green-phase ranking).
The Manager applies it via the existing `_apply_actions` dispatcher in
`simulation_controller.py`.

## TraCI-free operation

Unlike the in-process adapter (`services/simulation_manager/optimizers/mpc_adapter.py`),
this service does **not** use TraCI. All static topology comes from
`sumolib` parsing the `.net.xml` file at `/reset` time:

| TraCI call (in adapter) | Replacement (in service) |
|---|---|
| `traci.trafficlight.getIDList()` | `net.getTrafficLights()` via sumolib |
| `traci.trafficlight.getAllProgramLogics()` | `tls.getPrograms()` via sumolib |
| `traci.trafficlight.getControlledLinks()` | `tls.getConnections()` via sumolib |
| `traci.trafficlight.getPhase()` | `snapshot.intersections[tls_id].phase_index` |
| `traci.lane.getLastStepHaltingNumber()` | `snapshot.lanes[lane_id].queue_length` |
| `traci.lane.getLength()` | cached at init from `lane.getLength()` via sumolib |
| `traci.simulation.getTime()` | `step` field in the /predict request |

The orchestration logic (recursive queue polling, plan state machine,
demand-LSTM update, per-TLS optimize) is preserved exactly.

## Run locally

```bash
cd services/mpc_service
pip install -r requirements.txt
export WEIGHTS_DIR=/path/to/repo/services/mpc_traffic_control/data
export SCENARIOS_DIR=/path/to/repo/simulation_and_control_panel/scenarios
python main.py
```

The service listens on `:8003`.

## Run in Docker

The service runs as part of the root `docker-compose.yml`:

```bash
docker compose up mpc_service
```

The Manager calls it via `http://mpc_service:8003` when
`MODEL_MPC_URL` is set in the simulation_manager environment.

## How the Manager calls it

```bash
MODEL_MPC_URL=http://mpc_service:8003 docker compose up
```

If `MODEL_MPC_URL` is not set, the Manager falls back to its in-process
MPC adapter (Phase 2 behavior).

## Per-session state

- `controllers` — one `MPCController` per intersection
- `cycle_plans` — active MPC plan per TLS (re-optimized when expired)
- `last_decisions` — diagnostics for `/internals`
- `upstream_lanes` / `lane_lengths` — cached topology for recursive queue polling
- `predictor` — LSTM `DemandPredictor` for arrival forecasting

All cleared on `/reset` or `/teardown`.

## Scenario-specific config

| Scenario | Cycle time | Max green |
|---|---|---|
| `katunayake` | 120s | 90s |
| (default) | 45s | 60s |

Mirrors the existing logic in `mpc_adapter.py:46-61`.

## Migration status

| Phase | Status |
|---|---|
| 4 — MPC over HTTP | **Current** |
| 6 — Schema validation | Pending |
| 6 — Auth tokens | Pending |
| 7 — Reconstruct controllers from network dict (drop net.xml shortcut) | Pending |
