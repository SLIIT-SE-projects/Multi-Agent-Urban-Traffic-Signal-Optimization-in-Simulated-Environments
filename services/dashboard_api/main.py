# services/dashboard_api/main.py
import json
import os
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket
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
        # Proxy to Simulation Backend
        sim_url = "http://localhost:5000/api/simulation/topology"
        print(f"DEBUG: Fetching topology from {sim_url}")
        response = requests.get(sim_url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching topology: {response.status_code} - {response.text}")
            return {"error": "Failed to fetch topology from simulation backend"}
    except Exception as e:
        print(f"Error proxying network graph: {e}")
        return {"error": str(e)}

# 7. WEBSOCKET ENDPOINT
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