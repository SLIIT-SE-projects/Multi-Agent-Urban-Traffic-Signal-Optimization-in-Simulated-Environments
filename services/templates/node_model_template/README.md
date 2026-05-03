# Node.js Model Service Template

Minimal Express implementation of `model_service.yaml`. Replace two
hooks in `server.js` and you have a working model service.

## Quick start

```bash
npm install
npm start
# Listens on :9000
```

## Validate against the contract

From the repository root:

```bash
docker build -f services/contract_tester/Dockerfile -t contract-tester .
docker run --rm --network=host contract-tester http://localhost:9000
```

## What to change

Two regions in `server.js` are marked **RESEARCHER HOOK 1** and
**RESEARCHER HOOK 2**:

### Hook 1 — `/reset` body
Build internal data structures from the network topology.

### Hook 2 — `/predict` body
Your inference logic. Read `snapshot.intersections` and `snapshot.lanes`,
return a dict of `{tls_id: {type, value}}`.

## Configure via environment

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `9000` | Port to listen on |
| `MODEL_NAME` | `researcher_template_node` | Stable identifier |
| `DECISION_INTERVAL_STEPS` | `15` | Manager `/predict` cadence |
| `MAX_INFERENCE_MS` | `500` | Hard upper bound on `/predict` latency |
| `AUTHOR` | `researcher` | Surfaced in `/info` |

## Run in Docker

```bash
docker build -t my-researcher-model .
docker run --rm -p 9000:9000 my-researcher-model
```

## See also

- `contracts/researcher_onboarding.md`
- `services/contract_tester/`
- `../python_model_template/`
