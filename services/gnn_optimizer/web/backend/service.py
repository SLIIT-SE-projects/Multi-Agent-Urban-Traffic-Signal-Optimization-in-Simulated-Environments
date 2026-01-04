import socketio
import requests
import time
import threading
from config import Config

MANAGER_API = Config.MANAGER_API
MANAGER_WS = Config.MANAGER_WS

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
        if not self.running: return

        lanes = raw_data.get('lanes', {})
        
        # Safe aggregation
        total_queue = 0
        total_waiting = 0
        total_co2 = 0
        speed_sum = 0
        lane_count = 0

        for l_data in lanes.values():
            total_queue += l_data.get('queue_length', 0)
            total_waiting += l_data.get('waiting_time', 0)
            total_co2 += l_data.get('co2', 0)
            speed_sum += l_data.get('avg_speed', 0)
            lane_count += 1

        avg_speed = (speed_sum / lane_count) if lane_count > 0 else 0
        
        # Throughput (from global or calculated)
        # Check if 'global' exists in raw_data, otherwise default to 0
        throughput = raw_data.get('global', {}).get('arrived_vehicles', 0)

        # 2. Emit to GNN Frontend
        # Ensure these keys match EXACTLY what your React 'useTrafficSocket' hook expects
        self.server_socketio.emit('traffic_update', {
            'step': raw_data.get('step', 0),
            'total_queue': total_queue,
            'avg_speed': avg_speed,
            'total_co2': total_co2,
            'total_waiting_time': total_waiting,
            'throughput': throughput,
            'intersections': raw_data.get('intersections', {})
        })
