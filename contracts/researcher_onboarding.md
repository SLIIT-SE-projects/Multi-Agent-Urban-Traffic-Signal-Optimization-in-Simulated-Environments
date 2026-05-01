# External Researcher Onboarding

Welcome. This guide shows you how to integrate your own traffic signal
control model into the Multi-Agent Traffic Signal Optimization Platform
without ever touching SUMO, TraCI, or our codebase.

## What you build

A single HTTP service that implements four endpoints:

| Endpoint | Method | Called when |
|---|---|---|
| `/info` | GET | Platform discovers your model |
| `/health` | GET | Platform checks if you're alive |
| `/reset` | POST | A new simulation session starts |
| `/predict` | POST | Every N simulation steps (you decide N) |

That's it. Implement these four endpoints in any language, register the URL
with our platform, and your model is now controlling traffic signals.

## What you receive

Every `/predict` call gives you a **snapshot** of the simulation:
- State of every traffic light (current phase, time-to-switch)
- State of every lane (queue length, vehicle count, speed, waiting time, CO₂)

See `schemas/snapshot.schema.json` for the exact shape.

## What you return

A map of `{traffic_light_id → action}` where each action is one of:

- `binary_switch` — `0` keep current phase, `1` advance to next green
- `set_phase` — set traffic light to a specific phase index
- `set_duration` — set a phase to run for a specific duration (seconds)

You can mix action types within the same response.

See `schemas/action.schema.json`.

## Walkthrough — minimal Python model

```python
from fastapi import FastAPI
import uvicorn

app = FastAPI()
network = None
session_id = None

@app.get("/info")
def info():
    return {
        "name": "my_research_model",
        "version": "0.1.0",
        "snapshot_schema_version": "1",
        "action_schema_version": "1",
        "decision_interval_steps": 10,
        "action_types_supported": ["binary_switch"],
        "supports_warm_start": False,
        "max_inference_ms": 200,
        "description": "My PhD thesis traffic controller",
        "author": "Jane Doe <jane@uni.edu>"
    }

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": True, "session_id": session_id}

@app.post("/reset")
def reset(req: dict):
    global network, session_id
    network = req["network"]
    session_id = req["session_id"]
    # Build internal data structures from network here
    return {"status": "ready", "session_id": session_id}

@app.post("/predict")
def predict(req: dict):
    snapshot = req["snapshot"]
    actions = {}
    for tls_id, state in snapshot["intersections"].items():
        # Your control logic here. Example: switch if any incoming lane has queue > 5
        switch = 0
        # ... your logic ...
        actions[tls_id] = {"type": "binary_switch", "value": switch}
    return {
        "session_id": req["session_id"],
        "step": req["step"],
        "actions": actions
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
```

That's a complete, working researcher model.

## Step-by-step integration

### 1. Implement the contract

Use the example above as a starting point, or any framework in any language.
The contract is HTTP+JSON — there are no language requirements.

### 2. Validate your service locally

```bash
docker run --rm --network=host \
    your-org/contract-tester \
    --url http://localhost:9000
```

The tester runs synthetic snapshots through your service and checks:
- All four endpoints respond
- `/info` returns valid metadata
- `/predict` returns schema-conformant actions
- Inference latency stays under your declared `max_inference_ms`
- Your service handles a full `/reset` → 100 × `/predict` flow

### 3. Run the platform stack

On your laptop:
```bash
git clone <platform-repo>
cd platform
docker compose up -d
sumo-gui -c scenarios/grid3x3/grid3x3.sumo.cfg --remote-port 8813 --start
```

### 4. Register your model

```bash
curl -X POST http://localhost:8000/api/models/register \
    -H "Content-Type: application/json" \
    -d '{
        "name": "my_research_model",
        "url": "http://host.docker.internal:9000",
        "description": "My PhD thesis traffic controller"
    }'
```

If your model runs on another machine, replace `host.docker.internal` with
that machine's reachable address.

### 5. Activate your model

In the Sim Control Panel UI: scenario dropdown → "my_research_model" → Load.

The Manager calls `/reset` on your service, then `/predict` every
`decision_interval_steps` ticks until the simulation stops.

### 6. Watch the dashboard

The Traffic Dashboard surfaces:
- Per-intersection action history (your decisions)
- Queue, waiting time, CO₂ time series — your model's effect
- Inference latency from your `telemetry.inference_time_ms` field
- Any custom fields you put in `telemetry.model_specific`

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Manager times out calling /predict | Inference > 2000ms | Optimize, or raise `max_inference_ms` if your decision interval allows |
| 503 from Manager when you /predict | /reset not called yet | Make sure your service is registered before simulation starts |
| Schema validation error | Action type or required field mismatch | Run contract-tester locally first |
| Manager refuses to load your model | Major schema version mismatch | Bump your `snapshot_schema_version` and `action_schema_version` to match the platform's published version |
| Lights don't switch despite your `binary_switch=1` | Yellow phase still active | Manager auto-handles 3-step yellow transition before applying — be patient |

## Security & quotas

- Models registered without auth tokens can only run on the registering
  machine's local network
- Public models must register an auth token (provided by the platform admin)
- Inference rate is capped at one call per `decision_interval_steps` —
  models declaring `decision_interval_steps=1` will be heavily throttled

## What you do NOT need

You do **not** need to:
- Install SUMO
- Install TraCI
- Read our codebase
- Use Python or PyTorch
- Touch our database, Redis, or any other infrastructure
- Handle vehicle spawning, scenario switching, or lifecycle events

The platform handles all of that. You stay focused on the control logic.

## Reference

- Contract spec: `contracts/openapi/model_service.yaml`
- Snapshot shape: `contracts/schemas/snapshot.schema.json`
- Action shape: `contracts/schemas/action.schema.json`
- Network shape: `contracts/schemas/network.schema.json`
- Reference templates (Python, Node.js): `services/templates/` (Phase 6)
