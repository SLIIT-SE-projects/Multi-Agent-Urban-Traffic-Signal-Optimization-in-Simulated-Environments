"""EVPS Service — FastAPI entry point.

Conforms to:
  contracts/openapi/evps_service.yaml
  contracts/schemas/evps_step.schema.json

Phase 5 deliverable. Single-tenant.

Note: The driver-app WebSocket stays on the Simulation Manager in
Phase 5 — the Manager relays broadcasts received from this service over
its existing /ws endpoint. This avoids a Driver-app code change. Phase 7
may move the WebSocket here directly.
"""
from __future__ import annotations
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from config import config
from core.eta_predictor import EtaPredictor
from core.safety_classifier import SafetyClassifier
from core.fleet_arbiter import FleetArbiter


app = FastAPI(
    title="EVPS Service",
    version="1.0.0",
    description=(
        "Emergency Vehicle Preemption with TF/Keras ETA predictor and "
        "sklearn safety classifier. Receives enriched snapshots from the "
        "Simulation Manager, returns override directives the Manager "
        "applies via TraCI."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_arbiter: Optional[FleetArbiter] = None
_started_at: float = time.time()
_request_count: int = 0


def _init_arbiter() -> FleetArbiter:
    """Load ETA + safety models if available, build the arbiter."""
    eta = None
    safety = None
    try:
        eta = EtaPredictor(
            model_path=config.ETA_MODEL_PATH,
            scaler_path=config.ETA_SCALER_PATH,
            target_scaler_path=config.ETA_TARGET_SCALER_PATH,
            sequence_length=config.SEQUENCE_LENGTH,
        )
        print(f"[EVPS] ETA predictor loaded from {config.ETA_MODEL_PATH}")
    except Exception as exc:
        print(f"[EVPS] ⚠️ ETA predictor unavailable: {exc}")

    try:
        safety = SafetyClassifier(model_path=config.SAFETY_MODEL_PATH)
        print(f"[EVPS] Safety classifier loaded from {config.SAFETY_MODEL_PATH}")
    except Exception as exc:
        print(f"[EVPS] ⚠️ Safety classifier unavailable: {exc}")

    return FleetArbiter(
        eta_predictor=eta,
        safety_classifier=safety,
        sequence_length=config.SEQUENCE_LENGTH,
        eta_smoothing_alpha=config.ETA_SMOOTHING_ALPHA,
    )


@app.on_event("startup")
async def startup_event() -> None:
    global _arbiter
    _arbiter = _init_arbiter()


# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/info")
def get_info() -> dict:
    return {
        "name": "evps",
        "version": "1.0.0",
        "step_schema_version": "1",
        "models_loaded": {
            "eta_predictor": _arbiter is not None and _arbiter.eta_predictor is not None,
            "safety_classifier": _arbiter is not None and _arbiter.safety_classifier is not None,
        },
        "max_inference_ms": config.MAX_INFERENCE_MS,
        "sequence_length": config.SEQUENCE_LENGTH,
        "description": "Emergency Vehicle Preemption — ETA + safety + multi-EV arbitration",
    }


@app.get("/health")
def get_health() -> dict:
    return {
        "status": "ok" if _arbiter is not None else "not_ready",
        "active": _arbiter.active if _arbiter else False,
        "fleet_size": len(_arbiter.fleet) if _arbiter else 0,
        "session_id": _arbiter.session_id if _arbiter else None,
        "uptime_seconds": time.time() - _started_at,
        "request_count": _request_count,
    }


@app.post("/reset")
async def reset(request: Request) -> dict:
    if _arbiter is None:
        raise HTTPException(status_code=503, detail="EVPS not initialized")
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    _arbiter.reset(session_id)
    return {"status": "ready", "session_id": session_id}


@app.post("/toggle")
async def toggle(request: Request) -> dict:
    if _arbiter is None:
        raise HTTPException(status_code=503, detail="EVPS not initialized")
    body = await request.json()
    enable = bool(body.get("enable", False))
    _arbiter.toggle(enable)
    print(f"[EVPS] {'Activated' if enable else 'Deactivated'}")
    return {"status": "success", "active": enable}


@app.post("/step")
async def step(request: Request) -> dict:
    """Receive enriched snapshot, return overrides + broadcasts."""
    global _request_count
    if _arbiter is None:
        raise HTTPException(status_code=503, detail="EVPS not initialized")

    body = await request.json()
    step_num = body.get("step", 0)
    snapshot = body  # the entire body is the snapshot

    try:
        result = _arbiter.step(snapshot, step=step_num)
        _request_count += 1
        return result
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"EVPS step failed: {exc}")


@app.post("/register_ev")
async def register_ev(request: Request) -> dict:
    """Manager notifies after spawning a new EV via TraCI."""
    if _arbiter is None:
        raise HTTPException(status_code=503, detail="EVPS not initialized")
    body = await request.json()
    ev_id = body.get("ev_id")
    if not ev_id:
        raise HTTPException(status_code=400, detail="ev_id is required")
    priority = int(body.get("priority", 1))
    vehicle_type = body.get("vehicle_type", "ambulance")
    _arbiter.register_ev(ev_id, priority=priority, vehicle_type=vehicle_type)
    return {"status": "registered", "ev_id": ev_id}


@app.post("/set_focus")
async def set_focus(request: Request) -> dict:
    if _arbiter is None:
        raise HTTPException(status_code=503, detail="EVPS not initialized")
    body = await request.json()
    ev_id = body.get("ev_id")
    if not ev_id:
        raise HTTPException(status_code=400, detail="ev_id is required")
    _arbiter.set_focus(ev_id)
    return {"status": "ok", "selected_ev_id": ev_id}


@app.post("/set_priority")
async def set_priority(request: Request) -> dict:
    if _arbiter is None:
        raise HTTPException(status_code=503, detail="EVPS not initialized")
    body = await request.json()
    ev_id = body.get("ev_id")
    if not ev_id:
        raise HTTPException(status_code=400, detail="ev_id is required")
    priority = int(body.get("priority", 1))
    _arbiter.set_priority(ev_id, priority)
    return {"status": "ok"}


@app.get("/fleet")
def get_fleet() -> dict:
    if _arbiter is None:
        return {"fleet": [], "selected_ev_id": "EV_0", "overrides": []}
    return {
        "fleet": [
            {
                "id": ev_id,
                "priority": data["priority"],
                "type": data.get("type", "ambulance"),
                "smoothed_eta": data.get("smoothed_eta"),
                "speed": data.get("speed", 0.0),
                "safety_blocked": data.get("safety_blocked", False),
            }
            for ev_id, data in _arbiter.fleet.items()
        ],
        "selected_ev_id": _arbiter.selected_ev_id,
        "overrides": list(_arbiter.active_overrides.keys()),
    }


@app.post("/teardown")
async def teardown() -> dict:
    if _arbiter is not None:
        _arbiter.toggle(False)
        _arbiter.reset(session_id=_arbiter.session_id or "")
    return {"status": "released"}


if __name__ == "__main__":
    import uvicorn
    print(f"[EVPS Service] Starting on {config.HOST}:{config.PORT}")
    print(f"[EVPS Service] EVPS_MODELS_DIR={config.EVPS_MODELS_DIR}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
