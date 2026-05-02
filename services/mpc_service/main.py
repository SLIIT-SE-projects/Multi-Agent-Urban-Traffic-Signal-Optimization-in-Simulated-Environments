"""MPC Traffic Signal Model Service — FastAPI entry point.

Conforms to:
  contracts/openapi/model_service.yaml
  contracts/schemas/snapshot.schema.json
  contracts/schemas/action.schema.json
  contracts/schemas/network.schema.json
  contracts/schemas/model_info.schema.json

Phase 4 deliverable. Single-tenant: one active session at a time.

In addition to the standard model contract endpoints, this service exposes
a non-contract `/internals` endpoint for the Sim Control Panel UI's MPC
Internals tab (replaces /api/optimizer/mpc/internals on the Manager when
HTTP routing is active).
"""
from __future__ import annotations
import time
import glob
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from config import config
from models.mpc_model import MPCModel


app = FastAPI(
    title="MPC Traffic Signal Model Service",
    version="1.0.0",
    description=(
        "Model Predictive Control with LSTM demand forecasting. "
        "Wraps services/mpc_traffic_control for HTTP-based use by the "
        "Simulation Manager."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Single-tenant model state ──────────────────────────────────────────
_model: Optional[MPCModel] = None
_started_at: float = time.time()
_request_count: int = 0


# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/info")
def get_info() -> dict:
    """Static metadata. Conforms to contracts/schemas/model_info.schema.json."""
    return {
        "name": "mpc",
        "version": "1.0.0",
        "snapshot_schema_version": "1",
        "action_schema_version": "1",
        "decision_interval_steps": config.DECISION_INTERVAL_STEPS,
        "action_types_supported": ["set_phase"],
        "supports_warm_start": True,
        "max_inference_ms": config.MAX_INFERENCE_MS,
        "needs_vehicle_data": False,
        "description": "Model Predictive Control with LSTM demand predictor and recursive queue polling",
        "author": "internal",
        "license": "MIT",
        "tags": ["mpc", "optimization", "lstm", "qp"],
    }


@app.get("/health")
def get_health() -> dict:
    return {
        "status": "ok" if _model is not None and _model.is_loaded() else "not_ready",
        "model_loaded": _model is not None and _model.is_loaded(),
        "session_id": _model.session_id if _model else None,
        "uptime_seconds": time.time() - _started_at,
        "request_count": _request_count,
    }


@app.post("/reset")
async def reset(request: Request) -> dict:
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    network = body.get("network") or {}
    cfg = body.get("config") or {}
    scenario = (
        body.get("scenario")
        or cfg.get("scenario")
        or network.get("scenario_name")
        or "default"
    )

    # Phase 4 shortcut: accept _internal_net_xml_path so we can use sumolib
    # against the actual .net.xml file. Phase 7 will rebuild from the
    # network dict directly so external researchers don't need to mount
    # scenario files.
    net_xml_path = (
        network.get("_internal_net_xml_path")
        or body.get("net_xml_path")
        or _resolve_net_xml_from_scenario(scenario)
    )

    if not net_xml_path:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot determine network file. Provide "
                "network._internal_net_xml_path, body.net_xml_path, or scenario."
            ),
        )

    global _model
    try:
        if _model is not None:
            _model.teardown()
        _model = MPCModel(
            net_xml_path=net_xml_path,
            scenario_name=scenario,
            weights_dir=config.WEIGHTS_DIR,
        )
        _model.initialize(session_id=session_id)
        return {
            "status": "ready",
            "session_id": session_id,
            "warmup_steps": 0,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to initialize MPC: {exc}")


@app.post("/predict")
async def predict(request: Request) -> dict:
    """Compute actions for a snapshot. Returns contract-format actions."""
    global _request_count, _model

    if _model is None or not _model.is_loaded():
        raise HTTPException(
            status_code=503,
            detail="Session not initialized — call /reset first",
        )

    body = await request.json()
    session_id = body.get("session_id")
    step = body.get("step", 0)
    snapshot = body.get("snapshot", {})

    if session_id != _model.session_id:
        raise HTTPException(
            status_code=400,
            detail=f"session_id mismatch: expected {_model.session_id}, got {session_id}",
        )

    try:
        actions, telemetry = _model.predict(snapshot, step=step)
        _request_count += 1
        return {
            "session_id": session_id,
            "step": step,
            "actions": actions,
            "telemetry": telemetry,
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}")


@app.get("/internals")
def get_internals() -> dict:
    """MPC-specific internals for the Sim Control Panel UI's MPC tab.

    Not part of the standard model contract — this endpoint exists because
    the Phase-2 monolith exposed `/api/optimizer/mpc/internals` directly.
    The Manager now proxies that endpoint to this one when HTTP routing
    is active.
    """
    if _model is None or not _model.is_loaded():
        return {"status": "idle", "message": "MPC session not active"}
    try:
        data = _model.get_internals()
        data["status"] = "active"
        return data
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.post("/teardown")
async def teardown() -> dict:
    """Release the active session (called by Manager during unload)."""
    global _model
    if _model is not None:
        _model.teardown()
        _model = None
    return {"status": "released"}


# ── Helpers ────────────────────────────────────────────────────────────

def _resolve_net_xml_from_scenario(scenario_name: Optional[str]) -> Optional[str]:
    """Best-effort lookup of a .net.xml file given a scenario name."""
    if not scenario_name:
        return None
    pattern = os.path.join(config.SCENARIOS_DIR, scenario_name, "*.net.xml")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


if __name__ == "__main__":
    import uvicorn
    print(f"[MPC Service] Starting on {config.HOST}:{config.PORT}")
    print(f"[MPC Service] WEIGHTS_DIR={config.WEIGHTS_DIR}")
    print(f"[MPC Service] SCENARIOS_DIR={config.SCENARIOS_DIR}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
