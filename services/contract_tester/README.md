# Contract Tester

CLI tool that validates any model service URL against
`contracts/openapi/model_service.yaml`. External researchers run this
before registering with the platform; internal teams run it in CI to
lock contract conformance.

## What it checks

| Test | What it verifies |
|---|---|
| `/info` responds + schema | Endpoint reachable; metadata conforms to `model_info.schema.json` |
| `/info` schema versions | Declares `snapshot_schema_version=1` and `action_schema_version=1` |
| `/info` action types | Declares at least one of `binary_switch`, `set_phase`, `set_duration` |
| `/health` responds | Endpoint reachable, returns `status` and `model_loaded` |
| `/reset` succeeds | Accepts a synthetic network and returns `status=ready` |
| `/reset` session echo | Echoes the same session_id back |
| `/predict` responds + schema | Synthetic snapshot → response conforms to `action.schema.json` |
| `/predict` latency | Stays under declared `max_inference_ms` |
| `/predict` action types | Returned actions match declared `action_types_supported` |
| `/predict` burst x5 | Five consecutive calls all succeed (avg + p95 latency reported) |
| Session isolation | `/predict` with wrong session_id rejected with 4xx |

## Usage — local Python

```bash
cd services/contract_tester
pip install -r requirements.txt
python main.py http://localhost:9000
```

## Usage — Docker

The build context must be the repository root so `contracts/schemas/` is
included in the image:

```bash
docker build -f services/contract_tester/Dockerfile -t contract-tester .
docker run --rm --network=host contract-tester http://localhost:9000
```

For an external researcher whose model is on a different machine:

```bash
docker run --rm contract-tester http://researcher-laptop:9000 \
           --auth-token MY_BEARER_TOKEN
```

## Exit codes

- `0` — all checks passed
- `1` — at least one check failed (details printed to stdout)

## Schema discovery

The tester searches for `contracts/schemas/` in this order:

1. `/workspace/contracts/schemas/` (Docker image baked-in)
2. `<repo>/contracts/schemas/` (local checkout, walking up from `main.py`)
3. `/contracts/schemas/` (Docker mounted volume)
4. `<tester>/schemas/` (local copy)

The first directory containing `model_info.schema.json` wins.

## CI integration example

```yaml
# .github/workflows/contract.yml
- name: Build contract tester
  run: docker build -f services/contract_tester/Dockerfile -t contract-tester .

- name: Validate GNN service
  run: docker run --rm --network=host contract-tester http://gnn_service:8002

- name: Validate MPC service
  run: docker run --rm --network=host contract-tester http://mpc_service:8003
```

## Limitations (deferred to Phase 7)

- Does not test EVPS service — that has its own contract
  (`evps_service.yaml`) with different shape
- Does not test `/teardown` (optional in the contract)
- Does not run a long-duration soak test
