import asyncio
import json
import sys
import os
import redis.asyncio as redis
import redis as redis_sync

# 1. PATH SETUP
from config import Config
from service import RemoteOptimizationService
import requests as requests_sync

# 2. ADAPTER CLASS
class RedisSocketAdapter:
    def __init__(self, host=Config.REDIS_HOST, port=Config.REDIS_PORT):
        self.r = redis_sync.Redis(host=host, port=port, decode_responses=True)

    def emit(self, event, data):
        if event == 'traffic_update':
            try:
                # Publish to the channel the Dashboard API is listening to
                self.r.publish("gnn_metrics", json.dumps(data))
            except Exception as e:
                print(f"Error publishing to Redis: {e}")

# 3. MAIN WORKER
async def run_gnn_cycle():
    print(" GNN Worker Service Initializing...")

    # A. Initialize the Adapter
    redis_adapter = RedisSocketAdapter()

    # B. Initialize your Legacy Service logic
    service = RemoteOptimizationService(server_socketio=redis_adapter)
    
    # C. Setup Async Redis for Control Listening
    print(f"DEBUG: Connecting to Redis at {Config.REDIS_HOST}:{Config.REDIS_PORT}...")
    control_redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, decode_responses=True)
    try:
        await control_redis.ping()
        print("DEBUG: Successfully connected to Redis!")
    except Exception as e:
        print(f"DEBUG: Failed to connect to Redis: {e}")
        
    pubsub = control_redis.pubsub()
    await pubsub.subscribe("control_gnn")

    print(" GNN Worker Ready. Listening for commands on 'control_gnn'...")

    # D. Main Event Loop
    async for message in pubsub.listen():
        if message["type"] == "message":
            command = message["data"]
            print(f" Received command: {command}")
            
            if command == "start":
                # Calls the logic in service.py
                result = service.start_simulation()
                print(f" Service Response: {result}")
            
            elif command == "stop":
                # Calls the logic in service.py
                result = service.stop_simulation()
                print(f" Service Response: {result}")

            elif command == "record_baseline":
                print(" Starting Baseline Recording...")
                result = service.start_baseline_recording()
                print(f" Service Response: {result}")

            elif command == "stop_baseline":
                print(" Stopping Baseline Recording...")
                result = service.stop_baseline_recording()
                print(f" Service Response: {result}")

            elif command == 'get_model_status':
                try:
                    r = requests_sync.get(f'{Config.MANAGER_API}/optimizer/status')
                    status = r.json()
                    redis_adapter.r.publish('model_status', json.dumps(status))
                except Exception as e:
                    print(f'Status fetch error: {e}')

if __name__ == "__main__":
    try:
        asyncio.run(run_gnn_cycle())
    except KeyboardInterrupt:
        print("\nGNN Worker shutting down.")