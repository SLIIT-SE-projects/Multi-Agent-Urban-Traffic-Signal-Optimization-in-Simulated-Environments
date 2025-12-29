# services/dashboard_api/main.py
import asyncio
import json
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# 1. Allow React Frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Redis Connection
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# 3. HTTP Endpoints
class Command(BaseModel):
    action: str
    model: str

@app.post("/api/control")
async def send_command(cmd: Command):
    # Publish command to Redis. The GNN Service is listening for this!
    print(f"Sending command: {cmd.action} to channel: control_{cmd.model}")
    await redis_client.publish(f"control_{cmd.model}", cmd.action)
    return {"status": "command_sent", "details": cmd}

# 4. WebSocket (Data Stream to Frontend)
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
        print(f"WebSocket Error: {e}")
    finally:
        await websocket.close()