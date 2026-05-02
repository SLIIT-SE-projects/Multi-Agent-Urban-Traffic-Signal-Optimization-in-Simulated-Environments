"""GNN Traffic Signal Model Service — FastAPI entry point.

Conforms to:
  contracts/openapi/model_service.yaml
  contracts/schemas/snapshot.schema.json
  contracts/schemas/action.schema.json
  contracts/schemas/network.schema.json
  contracts/schemas/model_info.schema.json

Phase 3 deliverable. Single-tenant: one active session at a time.
"""
from __future__ import annotations
import time
import glob
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from config import config
from models.gnn_model import GNNModel


app = FastAPI(
    title="GNN Traffic Signal Model Service",
    version="1.0.0",
    description=(
        "Recurrent HGAT MARL with MC Dropout uncertainty. "
        "Wraps services/gnn_optimizer for HTTP-based use by the Simulation Manager."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Single-tenant model state ──────────────────────────────────────────
_model: Optional[GNNModel] = None
_started_at: float = time.time()
_request_count: int = 0


# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/info")
def get_info() -> dict:
    """Static metadata. Conforms to contracts/schemas/model_info.schema.json."""
    return {
        "name": "gnn",
        "version": "1.0.0",
        "snapshot_schema_version": "1",
        "action_schema_version": "1",
        "decision_interval_steps": config.DECISION_INTERVAL_STEPS,
        "action_types_supported": ["binary_switch"],
        "supports_warm_start": True,
        "max_inference_ms": config.MAX_INFERENCE_MS,
        "needs_vehicle_data": False,
        "description": "Recurrent HGAT MARL with MC Dropout uncertainty",
        "author": "internal",
        "license": "MIT",
        "tags": ["gnn", "marl", "attention", "uncertainty"],
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
    """Initialize a new simulation session.

    Body fields (per contracts/openapi/model_service.yaml):
        session_id: required
        scenario:   optional, used as a fallback if network is empty
        network:    object (full topology) or contains _internal_net_xml_path shortcut
        config:     optional, currently unused for GNN
    """
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    network = body.get("network") or {}
    cfg = body.get("config") or {}
    scenario = body.get("scenario") or network.get("scenario_name")

    # Phase 3 shortcut: accept _internal_net_xml_path so we can use sumolib
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
        _model = GNNModel(
            net_xml_path=net_xml_path,
            model_path=config.MODEL_WEIGHTS_PATH,
            mc_samples=config.MC_DROPOUT_SAMPLES,
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
        raise HTTPException(status_code=400, detail=f"Failed to initialize model: {exc}")


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
    """Best-effort lookup of a .net.xml file given a scenario name.

    Used as a fallback when /reset doesn't include a path. Looks under
    config.SCENARIOS_DIR / <scenario> / *.net.xml.
    """
    if not scenario_name:
        return None
    pattern = os.path.join(config.SCENARIOS_DIR, scenario_name, "*.net.xml")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


# Lazy import to keep glob path resolution working
import os  # noqa: E402


if __name__ == "__main__":
    import uvicorn
    print(f"[GNN Service] Starting on {config.HOST}:{config.PORT}")
    print(f"[GNN Service] MODEL_WEIGHTS_PATH={config.MODEL_WEIGHTS_PATH}")
    print(f"[GNN Service] SCENARIOS_DIR={config.SCENARIOS_DIR}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
