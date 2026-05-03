"""Minimal FastAPI model service template.

Implements the model_service.yaml contract with stub /predict logic.
Replace the body of `predict()` with your inference and you're done.

Run:
    pip install -r requirements.txt
    python main.py
"""
from __future__ import annotations
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request


app = FastAPI(title="Researcher Model Template")

# ── Per-session state ──────────────────────────────────────────────────
_session_id: Optional[str] = None
_network: Optional[dict] = None
_started_at: float = time.time()


# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/info")
def info() -> dict:
    """Static metadata. Conforms to model_info.schema.json."""
    return {
        "name": os.getenv("MODEL_NAME", "researcher_template"),
        "version": "0.1.0",
        "snapshot_schema_version": "1",
        "action_schema_version": "1",
        "decision_interval_steps": int(os.getenv("DECISION_INTERVAL_STEPS", "15")),
        "action_types_supported": ["binary_switch"],
        "supports_warm_start": True,
        "max_inference_ms": int(os.getenv("MAX_INFERENCE_MS", "500")),
        "description": "Stub template — replace the predict() body with your model",
        "author": os.getenv("AUTHOR", "researcher"),
        "license": "MIT",
    }


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _session_id else "not_ready",
        "model_loaded": _session_id is not None,
        "session_id": _session_id,
        "uptime_seconds": time.time() - _started_at,
    }


@app.post("/reset")
async def reset(request: Request) -> dict:
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    global _session_id, _network
    _session_id = session_id
    _network = body.get("network") or {}

    # ╭─ RESEARCHER HOOK 1 ────────────────────────────────────────────╮
    # │  Build internal data structures from the network topology      │
    # │  here. The network dict contains intersections, lanes, edges,  │
    # │  and connections — see contracts/schemas/network.schema.json.  │
    # │                                                                 │
    # │  Examples of what you might do:                                 │
    # │    - Build a graph (nodes=intersections, edges=lanes)           │
    # │    - Pre-compute shortest paths or distance matrices            │
    # │    - Allocate per-intersection state (queues, history buffers)  │
    # │    - Load any auxiliary data files                              │
    # ╰─────────────────────────────────────────────────────────────────╯

    return {"status": "ready", "session_id": session_id, "warmup_steps": 0}


@app.post("/predict")
async def predict(request: Request) -> dict:
    if not _session_id:
        raise HTTPException(
            status_code=503,
            detail="Session not initialized — call /reset first",
        )

    body = await request.json()
    if body.get("session_id") != _session_id:
        raise HTTPException(
            status_code=400,
            detail=f"session_id mismatch: expected {_session_id}, got {body.get('session_id')}",
        )

    step = body.get("step", 0)
    snapshot = body.get("snapshot", {})

    t0 = time.time()

    # ╭─ RESEARCHER HOOK 2 ────────────────────────────────────────────╮
    # │  Replace this stub with your model's inference logic.           │
    # │                                                                 │
    # │  Inputs:                                                        │
    # │    snapshot["intersections"]: {tls_id: {phase_index,            │
    # │                                          time_to_switch, ...}}  │
    # │    snapshot["lanes"]:         {lane_id: {queue_length,          │
    # │                                          avg_speed,             │
    # │                                          waiting_time, ...}}    │
    # │                                                                 │
    # │  Output: actions dict, one entry per intersection you control.  │
    # │    Action shapes (declared in /info action_types_supported):    │
    # │      {"type": "binary_switch", "value": 0|1}                    │
    # │      {"type": "set_phase",     "value": <int>}                  │
    # │      {"type": "set_duration",  "phase": <int>, "duration": <s>} │
    # ╰─────────────────────────────────────────────────────────────────╯

    actions = {}
    for tls_id, state in snapshot.get("intersections", {}).items():
        # STUB: always keep current phase. Replace with real logic.
        actions[tls_id] = {"type": "binary_switch", "value": 0}

    inference_ms = (time.time() - t0) * 1000.0

    return {
        "session_id": _session_id,
        "step": step,
        "actions": actions,
        "telemetry": {
            "inference_time_ms": round(inference_ms, 2),
            # Optional fields — surface anything you want to expose to the
            # Traffic Dashboard via telemetry.model_specific:
            # "model_specific": {"my_metric": 0.42},
        },
    }


@app.post("/teardown")
async def teardown() -> dict:
    """Optional. Called by the Manager when the operator unloads this model."""
    global _session_id, _network
    _session_id = None
    _network = None
    return {"status": "released"}


# ── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "9000"))
    print(f"[Researcher Template] Listening on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
