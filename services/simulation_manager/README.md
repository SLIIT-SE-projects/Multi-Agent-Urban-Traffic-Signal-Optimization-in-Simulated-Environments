# Simulation Manager

Owns the SUMO/TraCI loop. Drives the simulation step. Calls the active
model service (in-process today, HTTP from Phase 3) and the EVPS service
(in-process today, HTTP from Phase 5). Arbitrates their outputs into
final TraCI commands.

This is the **only service in the platform that touches TraCI**.

## Run locally (no Docker)

```bash
cd services/simulation_manager
pip install -r requirements.txt
export SUMO_HOME=/usr/share/sumo  # or wherever your SUMO install lives
python app.py
```

Defaults to `SUMO_MODE=local` (spawns its own sumo-gui).

## Run in Docker (SUMO on host)

1. Start SUMO on the host (Windows native, Mac, or Linux):
   ```bash
   sumo-gui -c simulation_and_control_panel/scenarios/grid3x3/grid3x3.sumo.cfg \
            --remote-port 8813 --start
   ```

2. Run the container with `SUMO_MODE=remote`:
   ```bash
   docker compose up simulation_manager
   ```

The container connects to the host's SUMO via `host.docker.internal:8813`.
On Linux Docker, the compose file adds an `extra_hosts` mapping for the
same hostname.

## Configuration

See `.env.example` for all environment variables. The most important:

| Variable | Default | Purpose |
|---|---|---|
| `SUMO_MODE` | `local` | `local` (spawn) or `remote` (connect) |
| `SUMO_HOST` | `localhost` | Host SUMO is reachable at (in remote mode) |
| `SUMO_PORT` | `8813` | TraCI TCP port |
| `USE_GUI` | `1` | Spawn sumo-gui (local mode only) |
| `SCENARIOS_DIR` | `<repo>/simulation_and_control_panel/scenarios` | Where to find `.sumo.cfg` files |
| `DEFAULT_SCENARIO` | `grid3x3` | Initial scenario name |

## Architecture

```
app.py                      Flask + SocketIO REST/WS surface (port 5000)
config.py                   Env-driven configuration
controllers/
  simulation_controller.py  TraCI loop, ModelRouter integration, arbitration
  scenario_controller.py    Scenario discovery and switching
  data_controller.py        Live snapshot capture
  state_controller.py       Save/restore session state
optimizers/                 In-process model adapters (GNN, MPC) and EVPS
  gnn_adapter.py
  mpc_adapter.py
  evps_adapter.py
routing/
  model_router.py           Abstract interface (matches contracts/openapi/model_service.yaml)
  inprocess_router.py       Phase 2 implementation wrapping local adapters
sumo/
  connection.py             SUMO_MODE switch (local-spawn vs remote-connect)
```

## Migration status

| Phase | Status |
|---|---|
| 2 — Service extracted, ModelRouter abstraction, SUMO_MODE switch | **Current** |
| 3 — GNN over HTTP | Pending |
| 4 — MPC over HTTP | Pending |
| 5 — EVPS service + arbiter | Pending |
| 6 — Researcher onboarding | Pending |

See `contracts/migration_phases.md` for the full plan.

## Phase 2 verification checklist

- `python app.py` starts the service and listens on `:5000`
- The Sim Control Panel UI (existing frontend on `:5173`) connects without changes
- Loading GNN or MPC produces identical step-by-step traffic behavior compared to the pre-migration backend
- EVPS toggle, EV spawn, scenario switch, flow-rate control all behave identically
- `SUMO_MODE=remote` connects successfully when SUMO is launched on the host with `--remote-port 8813`
