# Contracts Changelog

All notable changes to the contract files in this directory.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to semantic versioning at the **schema** level — see
`README.md` for versioning policy.

## [1.0.0] — 2026-05-01

### Added

- Initial contract set established as Phase 1 of the microservices migration
- `openapi/model_service.yaml` — Standard model service contract (v1)
- `openapi/evps_service.yaml` — EVPS service contract (v1)
- `openapi/simulation_manager.yaml` — Simulation Manager REST API (v1)
- `openapi/dashboard_api.yaml` — Dashboard API gateway (v1)
- `schemas/snapshot.schema.json` — Per-step traffic snapshot (v1)
- `schemas/action.schema.json` — Per-step action response (v1)
- `schemas/network.schema.json` — Network topology for /reset (v1)
- `schemas/model_info.schema.json` — Model metadata (v1)
- `schemas/evps_step.schema.json` — EVPS step request/response (v1)

### Notes

- Action schema supports three action types: `binary_switch` (matches current
  GNN behavior), `set_phase` (matches current MPC behavior), `set_duration`
  (forward-compatible for cycle-based controllers)
- Snapshot schema mirrors the fields currently captured in
  `_capture_snapshot_for_ai()` plus optional fields needed by EVPS
- Network schema includes geometry (x, y, shape) so models can reason about
  spatial relationships without TraCI access
