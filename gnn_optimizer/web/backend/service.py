import socketio
import requests
import time
import threading

MANAGER_API = "http://localhost:5000/api"
MANAGER_WS = "http://localhost:5000"

class RemoteOptimizationService:
    def __init__(self, server_socketio):
        self.server_socketio = server_socketio 
        # Standard client, force websocket transport to avoid polling timeouts
        self.sio_client = socketio.Client(reconnection=True, reconnection_attempts=5)
        self.running = False
        
        @self.sio_client.on('simulation_step')
        def on_simulation_step(data):
            self._process_and_forward(data)
            
        @self.sio_client.on('connect')
        def on_connect():
            print("✅ Connected to Simulation Manager Stream")

        @self.sio_client.on('disconnect')
        def on_disconnect():
            print("⚠️ Disconnected from Simulation Manager")

    def start_simulation(self):
        if self.running: return {"status": "Already running"}
        
        try:
            print("🚀 Remote Starting Simulation Manager...")
            # try: requests.post(f"{MANAGER_API}/simulation/start")
            # except: pass
            
            requests.post(f"{MANAGER_API}/optimizer/load", json={"type": "gnn"})
            
            # Connect only if not connected
            if not self.sio_client.connected:
                # Use threading to connect so we don't block the API response
                threading.Thread(target=self._connect_socket).start()
                
            # requests.post(f"{MANAGER_API}/simulation/auto-step/start", json={"step_delay": 0.1})
            
            self.running = True
            return {"status": "Remote Simulation Started"}
            
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            return {"status": "Error", "details": str(e)}

    def _connect_socket(self):
        """Helper to connect socket in background"""
        try:
            self.sio_client.connect(MANAGER_WS, transports=['websocket']) # Force Websocket
        except Exception as e:
            print(f"Socket connection error: {e}")

    def stop_simulation(self):
        """Stops the remote auto-stepping and unloads GNN"""
        try:
            # Option A: Stop the loop (Pause)
            # requests.post(f"{MANAGER_API}/simulation/auto-step/stop")
            
            # Option B: Keep loop running, but detach GNN
            requests.post(f"{MANAGER_API}/optimizer/unload") 
            
            self.running = False
            return {"status": "Stopped"}
        except:
            return {"status": "Error stopping"}

    def _process_and_forward(self, raw_data):
        """
        Receives raw SUMO data from Manager, calculates GNN Dashboard metrics,
        and forwards to GNN Frontend.
        """
        if not self.running: return

        # 1. Calculate Metrics
        lanes = raw_data.get('lanes', {})
        total_queue = sum(l['queue_length'] for l in lanes.values())
        avg_speed = 0
        if len(lanes) > 0:
            avg_speed = sum(l['avg_speed'] for l in lanes.values()) / len(lanes)

        # 2. Emit to GNN Frontend (So the dashboard updates!)
        self.server_socketio.emit('traffic_update', {
            'step': raw_data['step'],
            'total_queue': total_queue,
            'avg_speed': avg_speed,
            'intersections': raw_data['intersections']
        })
