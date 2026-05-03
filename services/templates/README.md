# Researcher Model Service Templates

Reference implementations of the model service contract
(`contracts/openapi/model_service.yaml`) in different languages.
External researchers can fork any of these as a starting point.

## Available templates

| Directory | Language | Framework | Lines of glue code |
|---|---|---|---|
| `python_model_template/` | Python 3.11 | FastAPI + uvicorn | ~80 |
| `node_model_template/` | Node.js 18+ | Express | ~70 |

Both implement the same four endpoints (`/info`, `/health`, `/reset`,
`/predict`) plus optional `/teardown`. Replace the body of `predict()`
with your model's inference logic and you're done.

## Quick start with the Python template

```bash
cd services/templates/python_model_template
pip install -r requirements.txt
python main.py
# Listens on :9000

# In another terminal, validate the contract:
docker build -f services/contract_tester/Dockerfile -t contract-tester .
docker run --rm --network=host contract-tester http://localhost:9000

# Register with the platform:
curl -X POST http://localhost:8000/api/models/register \
  -H "Content-Type: application/json" \
  -d '{"name": "researcher_x", "url": "http://host.docker.internal:9000"}'

# Activate via the Sim Control Panel UI: Load Model → researcher_x
```

## Quick start with the Node.js template

```bash
cd services/templates/node_model_template
npm install
npm start
# Listens on :9000
```

The rest of the workflow is identical.

## What you replace

In each template, two regions are marked as researcher hooks:

1. **`/reset`** — initialize internal data structures from the
   network topology
2. **`/predict`** — turn snapshots into actions

Everything else (HTTP routing, schema, error handling, port binding) is
boilerplate. Don't change it unless you're sure.

## See also

- `contracts/researcher_onboarding.md` — full integration walkthrough
- `contracts/openapi/model_service.yaml` — formal contract
- `contracts/schemas/snapshot.schema.json` — what you receive
- `contracts/schemas/action.schema.json` — what you return
- `services/contract_tester/` — validate your implementation before registering
