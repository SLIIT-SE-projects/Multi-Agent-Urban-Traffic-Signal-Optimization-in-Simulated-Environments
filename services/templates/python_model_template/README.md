# Python Model Service Template

Minimal FastAPI implementation of `model_service.yaml`. Replace two
hooks in `main.py` and you have a working model service.

## Quick start

```bash
pip install -r requirements.txt
python main.py
# Listens on :9000
```

## Validate against the contract

From the repository root:

```bash
docker build -f services/contract_tester/Dockerfile -t contract-tester .
docker run --rm --network=host contract-tester http://localhost:9000
```

You should see ~12 PASS lines and `All checks passed.`.

## What to change

Two regions in `main.py` are marked **RESEARCHER HOOK 1** and
**RESEARCHER HOOK 2**:

### Hook 1 — `/reset` body
Build internal data structures from the network topology. Examples:
- Parse intersections + lanes into a graph
- Pre-compute shortest paths or distance matrices
- Allocate per-intersection state buffers
- Load auxiliary data files

### Hook 2 — `/predict` body
Your inference logic. Read `snapshot.intersections` and `snapshot.lanes`,
return a dict of `{tls_id: {type, value}}`.

Don't change anything else — the rest is boilerplate (HTTP routing,
session validation, telemetry plumbing, port binding).

## Configure via environment

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `9000` | Port to listen on |
| `MODEL_NAME` | `researcher_template` | Stable identifier (used at registration) |
| `DECISION_INTERVAL_STEPS` | `15` | How often the Manager calls `/predict` |
| `MAX_INFERENCE_MS` | `500` | Hard upper bound on `/predict` latency |
| `AUTHOR` | `researcher` | Surfaced in `/info` |

## Register with the platform

```bash
curl -X POST http://localhost:8000/api/models/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_model",
    "url": "http://host.docker.internal:9000",
    "description": "My PhD thesis traffic controller"
  }'
```

After registration, your model name appears in the Sim Control Panel UI's
optimizer dropdown. Click "Load" and the Manager will start calling your
`/predict` every `decision_interval_steps` ticks.

## Run in Docker

```bash
docker build -t my-researcher-model .
docker run --rm -p 9000:9000 \
  -e MODEL_NAME=my_model \
  -e AUTHOR="Jane Doe <jane@uni.edu>" \
  my-researcher-model
```

## See also

- `contracts/researcher_onboarding.md` — full walkthrough
- `services/contract_tester/` — pre-flight validation
- `../node_model_template/` — Node.js equivalent
