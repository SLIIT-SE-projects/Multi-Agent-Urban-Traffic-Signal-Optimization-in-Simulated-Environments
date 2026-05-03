# EVPS Service

FastAPI service implementing emergency vehicle preemption logic. Uses
two pre-trained ML models:

- **ETA predictor** (TensorFlow/Keras LSTM) — forecasts seconds until
  an EV reaches its next signal
- **Safety classifier** (sklearn) — decides whether granting a green
  wave at a junction is safe

Phase 5 of the migration. Replaces the in-process `EVPSAdapter` from
`services/simulation_manager/optimizers/evps_adapter.py`.

## Why a separate service?

EVPS is structurally different from the model services (GNN, MPC):

| Aspect | GNN/MPC | EVPS |
|---|---|---|
| Decision rate | Every 15 steps | Every step |
| Output | Phase decisions for all TLS | Override directives for specific TLS |
| State | Per-agent (per-TLS) | Per-fleet (per-EV) |
| Lifecycle | Load/unload | Always-on, toggleable |
| Conflict | Sole controller | Wins overrides on conflict |

Putting EVPS behind the standard `/predict` Model Router would force
the router to merge two action streams every step — wrong abstraction.
EVPS is its own contract.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/info` | Service metadata + which models loaded |
| GET | `/health` | Liveness + fleet size |
| POST | `/reset` | New simulation session |
| POST | `/toggle` | Enable/disable EVPS for the session |
| POST | `/step` | Receive snapshot, return overrides + broadcasts |
| POST | `/register_ev` | Manager notifies after spawning a new EV |
| POST | `/set_focus` | Driver app changes which EV to track |
| POST | `/set_priority` | Driver app changes an EV's priority |
| GET | `/fleet` | List active EVs and override locks |
| POST | `/teardown` | Release session |

## TraCI-free operation

This service has zero TraCI access. The Manager pre-computes everything
EVPS needs into the `/step` request:

| TraCI call (in adapter) | Replacement (in service) |
|---|---|
| `traci.vehicle.getIDList()` | `snapshot.vehicles[]` |
| `traci.vehicle.getNextTLS()` | `snapshot.vehicles[i].next_tls` |
| `traci.vehicle.getSpeed()` etc. | `snapshot.vehicles[i].speed` etc. |
| `traci.lane.getLastStepHaltingNumber()` | `snapshot.lanes[lid].halting` |
| `traci.trafficlight.getControlledLanes()` | `snapshot.tls[tid].controlled_lanes` |
| `traci.trafficlight.getAllProgramLogics()` | `snapshot.tls[tid].phases` |
| `traci.trafficlight.setRedYellowGreenState()` | Manager applies returned override |
| `traci.simulation.convertGeo()` | Manager pre-converts geo positions |
| `traci.vehicle.add()` (spawn) | Manager spawns, then calls `/register_ev` |

The orchestration logic — fleet update, ETA smoothing, multi-EV
auction, hysteresis, safety check, cascade-block — is preserved bit
for bit.

## Run locally

```bash
cd services/evps_service
pip install -r requirements.txt
export EVPS_MODELS_DIR=/path/to/repo/services/emergency_vehicle_preemption
python main.py
```

Listens on `:8004`.

## Run in Docker

```bash
docker compose up evps_service
```

Manager calls it via `http://evps_service:8004` when `EVPS_URL` is set
in the simulation_manager environment.

## How the Manager calls it

```bash
EVPS_URL=http://evps_service:8004 docker compose up
```

If `EVPS_URL` is unset, the Manager falls back to its in-process
`EVPSAdapter` (Phase 2 behavior).

## Driver app WebSocket

The driver app's WebSocket stays on the Simulation Manager in Phase 5.
The Manager calls this service's `/step` every TraCI step, receives
the broadcast payload for the selected EV, and relays it to the driver
app over its existing `/ws` endpoint. This avoids a Driver-app code
change. Phase 7 may move the WebSocket here directly.

## Migration status

| Phase | Status |
|---|---|
| 5 — EVPS over HTTP | **Current** |
| 6 — Schema validation in /step | Pending |
| 7 — Move driver-app WebSocket here | Pending |
| 7 — Reconstruct topology from network dict (drop net.xml shortcut) | Pending |
