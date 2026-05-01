# Migration Phases

This document is the canonical reference for the 6-phase migration from the
current monolith to the target microservices architecture. Every phase ships
a working system — no phase leaves the project in a broken state.

## Phase 0 — Current State (baseline)

- `simulation_and_control_panel/backend/app.py` — Flask :5000 with embedded
  SUMO control, GNN/MPC/EVPS adapters in-process
- `services/dashboard_api/main.py` — FastAPI :8000 gateway
- `services/gnn_optimizer/web/backend/app.py` — Standalone GNN service :5001
  (used by the standalone GNN dashboard)
- React frontends, Flutter driver app
- Redis :6379 via docker-compose

## Phase 1 — Contracts (this phase)

**Goal:** Define every service interface formally before any code moves.

**Deliverables:** This `contracts/` directory.

**No runtime changes.** Verification: schemas validate, OpenAPI specs lint
clean.

## Phase 2 — Extract Simulation Manager

**Goal:** Pull SUMO + TraCI logic into a dedicated service. Add the
`SUMO_MODE` switch (local-spawn vs remote-connect).

**Code changes:**
- Create `services/simulation_manager/` (FastAPI)
- Move `Controllers/`, `optimizers/` from
  `simulation_and_control_panel/backend/` into the new service
- Add env-var driven mode selection:
  - `SUMO_MODE=local` (current behavior — `traci.start(cmd)`)
  - `SUMO_MODE=remote` (Docker-friendly — `traci.init(host, port)`)
- Add `ModelRouter` interface wrapping current `self.optimizer.predict()`
- Keep adapters in-process (don't network-split yet)
- Update existing `simulation_and_control_panel/backend/` to be a thin shim
  that re-exports the new package, OR replace it entirely

**No behavior change.** UI and frontends still work identically. Verification:
all current REST/WS endpoints respond identically.

## Phase 3 — GNN Service over HTTP

**Goal:** GNN runs in its own container; Manager calls it via HTTP.

**Code changes:**
- Create `services/gnn_service/` (FastAPI :8002)
- Wrap `gnn_adapter.py` logic behind `/predict`, `/reset`, `/info`, `/health`
- Validate every request/response against the snapshot/action schemas
- In Manager, add `HTTPModelClient` that implements the same interface as
  the in-process adapter
- Add timeout (default 2000ms) + fallback (last action or default control)
- Keep MPC and EVPS in-process for this phase

**Verification:** GNN dashboard shows identical telemetry. Manager survives
killing the GNN container (falls back to default control).

## Phase 4 — MPC Service over HTTP

**Goal:** MPC runs in its own container.

**Code changes:**
- Create `services/mpc_service/` (FastAPI :8003)
- Mirror Phase 3 pattern
- Now the contract is exercised by two independent implementations

**Verification:** Switching between GNN and MPC in the UI works the same as
before. Manager handles both action types (`binary_switch` and
`set_phase`/`set_duration`).

## Phase 5 — EVPS Service

**Goal:** EVPS in its own container with its own WebSocket for the driver app.

**Code changes:**
- Create `services/evps_service/` (FastAPI :8004 + WebSocket)
- Move `evps_adapter.py` logic behind `/step`, `/spawn_geo`, `/spawn_random`,
  `/toggle`, plus `/ws` for driver app
- Manager calls `POST /step` every simulation tick
- Add `ActionArbiter` in Manager: model actions + EVPS overrides → final
  TraCI commands, with EVPS winning conflicts
- Driver app updates its WebSocket URL from `ws://manager:5000/ws` to
  `ws://evps:8004/ws`

**Verification:** Spawn an EV, watch lights preempt, watch driver app receive
status. Toggle GNN on simultaneously and verify EVPS still wins on its
target lights.

## Phase 6 — Researcher Onboarding

**Goal:** External researchers can register their own model and use the
platform.

**Code changes:**
- Dashboard API gains:
  - `POST /api/models/register {name, url, auth_token}`
  - `GET /api/models` — list registered models
  - `DELETE /api/models/{name}` — unregister
- Manager calls a registered URL the same way it calls GNN/MPC
- Build `services/contract_tester/` Docker image:
  - `docker run --rm contract-tester http://researcher.host:9000`
  - Synthetic snapshot battery, schema validation, latency check
- Reference templates:
  - `services/templates/python_model_template/` — minimal FastAPI model
  - `services/templates/node_model_template/` — minimal Express model
- `researcher_onboarding.md` finalized with end-to-end walkthrough

**Verification:** A team member playing "external researcher" can ship a
working model in under an hour using the template.

## Phase 7 — Cross-cutting (ongoing, parallel to others)

- Distributed tracing — OpenTelemetry `request_id` propagated end-to-end
- Prometheus metrics on every service
- Structured JSON logs
- Service-to-service auth tokens
- `deploy/docker-compose.dev.yml` — local dev stack
- `deploy/docker-compose.prod.yml` — production stack
- `deploy/helm/` — Kubernetes deployment (optional, future)

## Phase Gate Criteria

A phase is complete when:

1. All deliverables in this document are merged
2. Existing UI workflows pass the integration test
3. Schema/spec changes (if any) are recorded in `changelog.md`
4. The next phase has been re-reviewed against the current state (drift check)

## Rollback Strategy

Each phase is in its own feature branch. Phases 2-5 keep the old
`simulation_and_control_panel/backend/` working until the new equivalent is
verified, then the old code is removed in a single follow-up commit.

If a phase reveals a flaw in the contracts, **stop and fix the contract
first** — do not patch around it in service code.
