import asyncio
import json
import sys
import os
import redis.asyncio as redis
import redis as redis_sync

# 1. PATH SETUP
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(current_dir, '../../gnn_optimizer/web/backend')
sys.path.append(backend_path)

from service import RemoteOptimizationService

# 2. ADAPTER CLASS
class RedisSocketAdapter:
    def __init__(self, host='localhost', port=6379):
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
    control_redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
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

if __name__ == "__main__":
    try:
        asyncio.run(run_gnn_cycle())
    except KeyboardInterrupt:
        print("\nGNN Worker shutting down.")