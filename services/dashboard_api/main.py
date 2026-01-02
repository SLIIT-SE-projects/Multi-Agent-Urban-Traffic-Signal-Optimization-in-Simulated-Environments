# services/dashboard_api/main.py
import json
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import Config (assuming running from root directory)
# If this fails, you may need the sys.path append trick again
from services.config import Config

# 1. INITIALIZE APP
app = FastAPI()

# 2. SETUP CORS (Important for your frontend to talk to this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config.DASHBOARD_CORS_ORIGIN, "*"], # Allow all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. SETUP REDIS CONNECTION
# We create the pool here so we can reuse it
redis_pool = redis.ConnectionPool(
    host=Config.REDIS_HOST, 
    port=Config.REDIS_PORT, 
    decode_responses=True
)
redis_client = redis.Redis(connection_pool=redis_pool)

# 4. DEFINE DATA MODEL
class Command(BaseModel):
    action: str
    model: str  # e.g., "gnn" or "mpc"

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