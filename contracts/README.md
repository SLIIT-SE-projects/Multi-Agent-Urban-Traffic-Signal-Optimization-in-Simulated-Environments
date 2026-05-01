# Contracts

Source of truth for inter-service communication in the Multi-Agent Traffic
Signal Optimization Platform.

## Why this directory exists

Microservices only work when interfaces are stable and explicit. These
contracts are versioned, language-neutral, and serve as the integration
boundary between every service in the system. Internal teams and external
researchers both build against the same files.

## Layout

```
contracts/
├── openapi/                    # OpenAPI 3.0 specs (one per HTTP service)
│   ├── model_service.yaml      # GNN, MPC, and any external researcher model
│   ├── evps_service.yaml       # Emergency vehicle preemption
│   ├── simulation_manager.yaml # SUMO loop + arbitration + lifecycle
│   └── dashboard_api.yaml      # Browser-facing gateway
├── schemas/                    # JSON Schema for shared payloads
│   ├── snapshot.schema.json    # Per-step traffic state
│   ├── action.schema.json      # Per-step model decisions
│   ├── network.schema.json     # Network topology (sent on /reset)
│   ├── model_info.schema.json  # Model metadata
│   └── evps_step.schema.json   # EVPS request/response
├── migration_phases.md         # The 6-phase migration plan reference
├── researcher_onboarding.md    # External researcher integration guide
├── changelog.md                # Versioned history of contract changes
└── README.md                   # This file
```

## Reading order — internal contributor

1. `migration_phases.md` — understand the rollout
2. `openapi/model_service.yaml` — the most important contract
3. `schemas/snapshot.schema.json` and `schemas/action.schema.json` — the data shapes
4. The remaining specs as needed

## Reading order — external researcher

1. `researcher_onboarding.md` — step-by-step
2. `openapi/model_service.yaml` — the only contract you implement
3. `schemas/snapshot.schema.json` — what you receive
4. `schemas/action.schema.json` — what you return

## Versioning policy

- Each schema declares a `version` field (top-level `$comment` or `info.version`)
- Services declare supported versions in `GET /info`
- **Patch** (`1.0.x`) — typo, doc clarification, no field changes
- **Minor** (`1.x.0`) — add optional fields only
- **Major** (`x.0.0`) — remove or rename fields, change required set, change semantics

The Simulation Manager and every model service must agree on the **major** version.
Mismatches cause the Manager to refuse to load that model and surface the error
in the dashboard.

## Validation

Schemas can be validated with any standard JSON Schema validator:
- Python: `pip install jsonschema`
- Node.js: `npm install ajv`
- CLI: `npx @stoplight/spectral-cli lint contracts/openapi/*.yaml`

The contract-tester Docker image (delivered in Phase 6) will run a full
conformance suite against any model URL.

## Contract-first workflow

When you need to change a contract:

1. Open a PR with the schema/spec change
2. Bump the version in `changelog.md`
3. Update consumer services to handle the new version
4. Update producer services last
5. Never delete a major version until all consumers have migrated
