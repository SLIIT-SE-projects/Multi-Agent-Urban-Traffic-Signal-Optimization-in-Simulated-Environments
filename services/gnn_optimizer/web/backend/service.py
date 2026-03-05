import socketio
import requests
import time
import threading
import json
import os
from config import Config

MANAGER_API = Config.MANAGER_API
MANAGER_WS = Config.MANAGER_WS

class RemoteOptimizationService:
    def __init__(self, server_socketio):
        self.server_socketio = server_socketio 
        # Standard client, force websocket transport to avoid polling timeouts
        self.sio_client = socketio.Client(reconnection=True, reconnection_attempts=5)
        self.running = False
        
        # Baseline Recording State
        self.recording = False
        self.baseline_data = []
        self.data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'baseline_metrics.json')
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        
        @self.sio_client.on('simulation_step')
        def on_simulation_step(data):
            self._process_and_forward(data)
            
        @self.sio_client.on('connect')
        def on_connect():
            print("✅ Connected to Simulation Manager Stream")

        @self.sio_client.on('disconnect')
        def on_disconnect():
            print("⚠️ Disconnected from Simulation Manager")

    # --- GNN MODEL MANAGEMENT ---
    def start_simulation(self):
        """Loads the GNN model and connects to the stream. Does NOT control simulation start/stop."""
        if self.running: return {"status": "Already running"}
        
        try:
            print("🚀 Loading GNN Optimizer...")
            requests.post(f"{MANAGER_API}/optimizer/load", json={"type": "gnn"})
            
            # Connect only if not connected
            if not self.sio_client.connected:
                # Use threading to connect so we don't block the API response
                threading.Thread(target=self._connect_socket).start()
            
            self.running = True
            return {"status": "GNN Model Loaded"}
            
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            return {"status": "Error", "details": str(e)}

    def stop_simulation(self):
        """Unloads the GNN model."""
        try:
            print("🛑 Unloading GNN Optimizer...")
            requests.post(f"{MANAGER_API}/optimizer/unload") 
            self.running = False
            return {"status": "GNN Model Unloaded"}
        except Exception as e:
            return {"status": "Error stopping", "details": str(e)}

    # --- BASELINE RECORDING MANAGEMENT ---
    def start_baseline_recording(self):
        """Starts simulation in auto-step mode and records data."""
        if self.recording: return {"status": "Already recording"}
        
        self.recording = True
        self.baseline_data = [] # Reset data
        
        try:
            print("📝 Starting Baseline Recording...")
            
            # 1. Reset Simulation
            print("DEBUG: Resetting Simulation...")
            requests.post(f"{MANAGER_API}/simulation/stop")
            time.sleep(1)
            requests.post(f"{MANAGER_API}/simulation/start")
            
            # 2. Start Auto-Step (No Optimizer)
            print("DEBUG: Starting Auto-Step...")
            requests.post(f"{MANAGER_API}/simulation/auto-step/start", json={"step_delay": 0.1})
            
            # 3. Connect Socket to receive data
            if not self.sio_client.connected:
                threading.Thread(target=self._connect_socket).start()
                
            return {"status": "Baseline Recording Started"}
            
        except Exception as e:
            print(f"❌ Baseline Start Failed: {e}")
            self.recording = False
            return {"status": "Error", "details": str(e)}

    def stop_baseline_recording(self):
        """Stops simulation and saves recorded data."""
        if not self.recording: return {"status": "Not recording"}
        
        try:
            print("🛑 Stopping Baseline Recording...")
            requests.post(f"{MANAGER_API}/simulation/auto-step/stop")
            requests.post(f"{MANAGER_API}/simulation/stop")
            
            print(f"💾 Saving Baseline Data ({len(self.baseline_data)} steps)...")
            with open(self.data_path, 'w') as f:
                json.dump(self.baseline_data, f)
            
            self.recording = False
            return {"status": "Baseline Saved"}
            
        except Exception as e:
            print(f"❌ Baseline Stop Failed: {e}")
            return {"status": "Error", "details": str(e)}

    def _connect_socket(self):
        """Helper to connect socket in background"""
        try:
            self.sio_client.connect(MANAGER_WS, transports=['websocket']) # Force Websocket
        except Exception as e:
            print(f"Socket connection error: {e}")

    def _process_and_forward(self, raw_data):
        # Always forward if connected, but also record if recording
        
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
        throughput = raw_data.get('global', {}).get('arrived_vehicles', 0)

        metrics = {
            'step': raw_data.get('step', 0),
            'total_queue': total_queue,
            'avg_speed': avg_speed,
            'total_co2': total_co2,
            'total_waiting_time': total_waiting,
            'throughput': throughput,
            'intersections': raw_data.get('intersections', {}),
            'model_meta': raw_data.get('model_meta', {}),
        }

        # Record if in baseline mode
        if self.recording:
            self.baseline_data.append(metrics)

        # Emit to GNN Frontend
        self.server_socketio.emit('traffic_update', metrics)
        
        if raw_data.get('model_meta', {}).get('active'):
            self.server_socketio.r.publish('model_performance', json.dumps({
                'step': metrics['step'],
                'uncertainty': raw_data['model_meta'].get('uncertainty'),
                'model_name': raw_data['model_meta'].get('model_name'),
                'inference_ms': raw_data['model_meta'].get('last_inference_ms'),
            }))
