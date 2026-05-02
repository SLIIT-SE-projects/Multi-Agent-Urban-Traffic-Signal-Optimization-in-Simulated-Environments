# DEPRECATED — Migrating to `services/simulation_manager/`

This folder is the original Phase-0 monolithic backend. As of Phase 2 of
the microservices migration (see `contracts/migration_phases.md`), all
code in this folder has been **copied** into:

    services/simulation_manager/

with the following changes applied to the new location only:

- `Controllers/` lowercased to `controllers/` (Python convention)
- `config.py` rewritten to be env-driven
- `simulation_controller.py` gains a `SUMO_MODE` switch (`local` / `remote`)
  and goes through the new `ModelRouter` abstraction
- `scenario_controller.py` reads `SCENARIOS_DIR` from config rather than
  resolving a relative path
- New top-level `app.py` (Flask) wired through ModelRouter

The behavior is intentionally identical for now — same REST surface, same
WebSocket events, same port `5000`, same scenarios. The frontends and
driver app keep working without any changes.

## Use the new service

```bash
cd services/simulation_manager
python app.py
```

## Rollback

If the new service has a regression, this folder still works — just run:

```bash
cd simulation_and_control_panel/backend
python app.py
```

## When can this folder be deleted?

After Phase 5 verification passes (EVPS migrated to its own service).
Until then, this folder stays as a rollback target. Do not add new code
here — make changes in `services/simulation_manager/` instead.
