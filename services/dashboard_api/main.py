# services/dashboard_api/main.py
import json
import os
import time
from typing import Optional
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import xml.etree.ElementTree as ET

# Import Config (assuming running from root directory)
from services.config import Config

# 1. INITIALIZE APP
app = FastAPI()

# 2. SETUP CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config.DASHBOARD_CORS_ORIGIN, "*"], # Allow all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. SETUP REDIS CONNECTION
redis_pool = redis.ConnectionPool(
    host=Config.REDIS_HOST, 
    port=Config.REDIS_PORT, 
    decode_responses=True
)
redis_client = redis.Redis(connection_pool=redis_pool)

@app.on_event("startup")
async def startup_event():
    print(f"DEBUG: Dashboard API connecting to Redis at {Config.REDIS_HOST}:{Config.REDIS_PORT}...")
    try:
        await redis_client.ping()
        print("DEBUG: Dashboard API successfully connected to Redis!")
    except Exception as e:
        print(f"DEBUG: Dashboard API failed to connect to Redis: {e}")

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

# 4. DEFINE DATA MODEL
class Command(BaseModel):
    action: str
    model: str  # e.g., "gnn" or "mpc"

# 5. CONTROL ENDPOINT
@app.post("/api/control")
async def send_command(cmd: Command):
    # Publish command to Redis. The GNN Service is listening for this!
    print(f"Sending command: {cmd.action} to channel: control_{cmd.model}")
    await redis_client.publish(f"control_{cmd.model}", cmd.action)
    return {"status": "command_sent", "details": cmd}

# 6. BASELINE PROXY ENDPOINTS
@app.post("/api/baseline/record")
async def proxy_record_baseline():
    try:
        # Publish to Redis instead of HTTP
        print("DEBUG: Sending command: record_baseline to channel: control_gnn")
        receivers = await redis_client.publish("control_gnn", "record_baseline")
        print(f"DEBUG: Command published. Receivers: {receivers}")
        return {"status": "command_sent", "action": "record_baseline", "receivers": receivers}
    except Exception as e:
        print(f"DEBUG: Error publishing: {e}")
        return {"status": "error", "details": str(e)}

@app.post("/api/baseline/stop")
async def proxy_stop_baseline():
    try:
        # Publish to Redis instead of HTTP
        print("DEBUG: Sending command: stop_baseline to channel: control_gnn")
        receivers = await redis_client.publish("control_gnn", "stop_baseline")
        print(f"DEBUG: Command published. Receivers: {receivers}")
        return {"status": "command_sent", "action": "stop_baseline", "receivers": receivers}
    except Exception as e:
        print(f"DEBUG: Error publishing: {e}")
        return {"status": "error", "details": str(e)}

@app.get("/api/baseline/data")
async def proxy_get_baseline_data():
    try:
        # Robust path finding to read the file directly
        current_dir = os.path.dirname(os.path.abspath(__file__))
        services_dir = os.path.dirname(current_dir)
        data_path = os.path.join(services_dir, 'gnn_optimizer', 'web', 'data', 'baseline_metrics.json')
        
        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error reading baseline data: {e}")
        return []

@app.get("/api/network-graph")
async def get_network_graph():
    try:
        # Proxy to Simulation Backend — uses the configured Manager API URL
        # so it works in both local dev (localhost:5000) and Docker
        # (simulation_manager:5000) environments.
        sim_url = f"{Config.MANAGER_API}/simulation/topology"
        print(f"DEBUG: Fetching topology from {sim_url}")
        response = requests.get(sim_url, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching topology: {response.status_code} - {response.text}")
            return {"error": "Failed to fetch topology from simulation backend"}
    except Exception as e:
        print(f"Error proxying network graph: {e}")
        return {"error": str(e)}

# 7. MODEL REGISTRY (Phase 6+)
# Stores model registrations in a Redis hash so external researchers can
# register their model URLs at runtime. The Simulation Manager queries
# this registry to resolve model names that aren't built in (gnn, mpc).
#
# Registration validates the candidate's /info endpoint conforms to the
# contract before storing — catches schema-version mismatches early.

REGISTRY_KEY = "models:registry"


class RegisterRequest(BaseModel):
    name: str
    url: str
    auth_token: Optional[str] = None
    description: Optional[str] = None


def _validate_model_info(url: str, auth_token: Optional[str] = None) -> dict:
    """Call /info on the candidate model service and verify schema versions."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    try:
        resp = requests.get(f"{url.rstrip('/')}/info", timeout=5.0, headers=headers)
        resp.raise_for_status()
        info = resp.json()
    except Exception as exc:
        raise ValueError(f"Could not reach /info: {exc}")

    if info.get("snapshot_schema_version") != "1":
        raise ValueError(
            f"snapshot_schema_version mismatch: expected '1', "
            f"got {info.get('snapshot_schema_version')!r}"
        )
    if info.get("action_schema_version") != "1":
        raise ValueError(
            f"action_schema_version mismatch: expected '1', "
            f"got {info.get('action_schema_version')!r}"
        )
    return info


@app.post("/api/models/register")
async def register_model(req: RegisterRequest):
    """Register a model service so the Manager can route to it by name.

    Validates the URL responds to /info with conformant metadata before
    storing. Returns the validated /info on success.
    """
    try:
        info = _validate_model_info(req.url, req.auth_token)
    except ValueError as exc:
        return {"status": "error", "reason": "validation_failed", "detail": str(exc)}

    record = {
        "name": req.name,
        "url": req.url,
        "auth_token": req.auth_token or "",
        "description": req.description or info.get("description", ""),
        "registered_at": time.time(),
        "info": info,
    }
    try:
        await redis_client.hset(REGISTRY_KEY, req.name, json.dumps(record))
    except Exception as exc:
        return {"status": "error", "reason": "redis_error", "detail": str(exc)}

    print(f"[Registry] Registered: {req.name} → {req.url}")
    return {"status": "registered", "name": req.name, "info": info}


@app.get("/api/models")
async def list_models():
    """List all registered model services."""
    try:
        all_records = await redis_client.hgetall(REGISTRY_KEY)
    except Exception as exc:
        return {"models": [], "error": str(exc)}
    return {
        "models": [json.loads(v) for v in all_records.values()],
    }


@app.get("/api/models/{name}")
async def get_model(name: str):
    """Look up one model by name. Used by Manager to resolve names."""
    try:
        raw = await redis_client.hget(REGISTRY_KEY, name)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis error: {exc}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not registered")
    return json.loads(raw)


@app.delete("/api/models/{name}")
async def unregister_model(name: str):
    """Remove a model from the registry."""
    try:
        deleted = await redis_client.hdel(REGISTRY_KEY, name)
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
    if deleted:
        print(f"[Registry] Unregistered: {name}")
        return {"status": "unregistered", "name": name}
    return {"status": "not_found", "name": name}


# 8. WEBSOCKET ENDPOINT
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    
    # Subscribe to data channels from GNN/MPC services
    await pubsub.subscribe("gnn_metrics", "mpc_metrics", "simulation_status")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_json({
                    "channel": message["channel"],
                    "data": json.loads(message["data"])
                })
    except Exception as e:
        print(f"WebSocket connection closed: {e}")
    finally:
        await pubsub.unsubscribe()
        await websocket.close()