import os
import sys
import traci
import numpy as np
import pandas as pd
import tensorflow as tf
import pickle
import asyncio
import json
import uvicorn
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "../models/saved/eta_predictor.h5")
SCALER_PATH = os.path.join(BASE_DIR, "../data/scalers/eta_scaler.pkl")
SUMO_CONFIG = os.path.join(BASE_DIR, "../simulation/config/mega_scenario.sumocfg") 

# Initialize FastAPI
app = FastAPI()

# Allow CORS for Flutter Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GreenWaveController:
    def __init__(self): 
        self.ev_id = "EV_0" # Default
        self.running = False
        
        print("Loading AI Models...")
        try:
            self.model = tf.keras.models.load_model(MODEL_PATH)
            with open(SCALER_PATH, "rb") as f:
                self.scaler = pickle.load(f)
            print("SUCCESS: Models loaded.")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not load models. {e}")
            sys.exit(1)

        self.sequence_length = 10
        self.state_buffer = deque(maxlen=self.sequence_length)
        
        # State
        self.active_override_tls = None 
        self.active_green_lane = None
        self.smoothed_eta = None 
        self.alpha = 0.3
        self.last_broadcast_status = {}

    def start_sumo(self):
        """Starts SUMO in GUI mode."""
        sumo_cmd = ["sumo-gui", "-c", SUMO_CONFIG, "--start"]
        traci.start(sumo_cmd)
        self.running = True
        print("Simulation Started.")

    def stop_sumo(self):
        try:
            traci.close()
            self.running = False
        except:
            pass

    def simulation_step(self):
        """Runs ONE step of the simulation logic."""
        if not self.running: return None

        try:
            if traci.simulation.getMinExpectedNumber() <= 0:
                self.stop_sumo()
                return None

            traci.simulationStep()
            
            # If the selected EV is not in simulation, try to find it or wait
            if self.ev_id not in traci.vehicle.getIDList():
                # self.ev_id remains set, but we can't control it yet
                # Optional: Auto-switch logic could go here if requested
                return self._build_status_packet(active=False)

            # --- CONTROL LOGIC ---
            features = self._get_live_features()
            if features:
                self.state_buffer.append(features)
                if len(self.state_buffer) == self.sequence_length:
                    raw_eta = self._predict_eta()
                    if self.smoothed_eta is None: self.smoothed_eta = raw_eta
                    else: self.smoothed_eta = (self.alpha * raw_eta) + ((1 - self.alpha) * self.smoothed_eta)
                    
                    self._manage_preemption(self.smoothed_eta)
            
            return self._build_status_packet(active=True)

        except Exception as e:
            print(f"Sim Error: {e}")
            return None

    def switch_vehicle(self, new_ev_id):
        """Called by Flutter App to switch tracking."""
        print(f"Command received: Switch to {new_ev_id}")
        self.ev_id = new_ev_id
        self.state_buffer.clear()
        self._release_control()
        self.smoothed_eta = None
        
        # Try to track visually in SUMO immediately
        try:
            traci.gui.trackVehicle("View #0", self.ev_id)
            traci.gui.setZoom("View #0", 600)
        except:
            pass # Vehicle might not exist yet

    def _build_status_packet(self, active):
        if not active:
            return {
                "type": "status",
                "ev_id": self.ev_id,
                "active": False,
                # ... defaults ...
            }

        try:
            speed = traci.vehicle.getSpeed(self.ev_id)
            x, y = traci.vehicle.getPosition(self.ev_id)
            
            # --- GEO-CONVERSION ---
            # Center of the map (Arbitrary "Home" location)
            # Example: London Eye
            REF_LAT = 51.5033
            REF_LON = -0.1195
            
            # Simple Meter-to-Degree conversion (approximate but fine for demo)
            # 1 deg lat ~ 111km, 1 deg lon ~ 111km * cos(lat)
            meters_per_deg_lat = 111132.954
            meters_per_deg_lon = 111132.954 * np.cos(np.radians(REF_LAT))
            
            lat = REF_LAT + (y / meters_per_deg_lat)
            lon = REF_LON + (x / meters_per_deg_lon)
            
            is_green_wave = (self.active_override_tls is not None)
            
            return {
                "type": "status",
                "ev_id": self.ev_id,
                "active": True,
                "eta": float(f"{self.smoothed_eta:.1f}") if self.smoothed_eta else 0.0,
                "speed": float(f"{speed * 3.6:.1f}"),
                "lat": lat,
                "lon": lon,
                "green_wave_active": is_green_wave,
                "tls_id": self.active_override_tls if is_green_wave else ""
            }
        except:
            return self._build_status_packet(active=False)

    # --- REUSED LOGIC FROM PREVIOUS CONTROLLER ---
    def _release_control(self):
        if self.active_override_tls:
            try:
                traci.trafficlight.setProgram(self.active_override_tls, "0")
            except: pass
            self.active_override_tls = None

    def _manage_preemption(self, eta):
        try:
            next_tls_info = traci.vehicle.getNextTLS(self.ev_id)
            if not next_tls_info:
                if self.active_override_tls: self._release_control()
                return

            target_tls_id = next_tls_info[0][0]
            dist_to_light = next_tls_info[0][2]

            if self.active_override_tls and self.active_override_tls != target_tls_id:
                self._release_control()
            
            if eta < 30 or dist_to_light < 100:
                self._force_green_wave(target_tls_id)
        except: pass

    def _force_green_wave(self, tls_id):
        try:
            ev_lane = traci.vehicle.getLaneID(self.ev_id)
            logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            num_links = len(logic.phases[0].state)
            new_state_list = ['r'] * num_links
            
            controlled_links = traci.trafficlight.getControlledLinks(tls_id)
            for i, links in enumerate(controlled_links):
                for link in links:
                    if link[0] == ev_lane:
                        new_state_list[i] = 'G'

            traci.trafficlight.setRedYellowGreenState(tls_id, "".join(new_state_list))
            self.active_override_tls = tls_id
            
            # Visuals
            traci.vehicle.setColor(self.ev_id, (0, 0, 255, 255))
        except: pass

    def _get_live_features(self):
        try:
            speed = traci.vehicle.getSpeed(self.ev_id)
            accel = traci.vehicle.getAcceleration(self.ev_id)
            lane_id = traci.vehicle.getLaneID(self.ev_id)
            pos = traci.vehicle.getLanePosition(self.ev_id)
            try: dist = traci.lane.getLength(lane_id) - pos
            except: dist = 0
            queue = traci.lane.getLastStepHaltingNumber(lane_id)
            leader = traci.vehicle.getLeader(self.ev_id, 200)
            if leader: l_gap, l_speed = leader[1], traci.vehicle.getSpeed(leader[0])
            else: l_gap, l_speed = 200, 30
            
            tls_val = 0.0
            next_tls = traci.vehicle.getNextTLS(self.ev_id)
            if next_tls:
                s = next_tls[0][3]
                if s in ['r', 'R', 'u']: tls_val = 1.0 
                elif s in ['y', 'Y']: tls_val = 0.5    
            
            return [speed, accel, dist, queue, l_gap, l_speed, tls_val]
        except: return None

    def _predict_eta(self):
        # (Same prediction logic as before)
        raw_sequence = np.array(self.state_buffer)
        feature_cols = ['speed', 'acceleration', 'distance_to_signal', 
                        'queue_length', 'leader_gap', 'leader_speed', 'tls_state']
        scaled = np.zeros_like(raw_sequence)
        for i in range(len(raw_sequence)):
            step_df = pd.DataFrame([raw_sequence[i]], columns=feature_cols)
            scaled[i] = self.scaler.transform(step_df)[0]
        input_data = scaled.reshape(1, self.sequence_length, 7)
        return self.model.predict(input_data, verbose=0)[0][0]

# --- GLOBAL INSTANCE ---
controller = GreenWaveController()

# --- WEBSOCKET HANDLER ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Flutter Client Connected!")
    
    # Start SUMO if not running
    if not controller.running:
        controller.start_sumo()

    try:
        while True:
            # 1. Run Simulation Step
            status = controller.simulation_step()
            
            # 2. Broadcast Status to Flutter
            if status:
                await websocket.send_text(json.dumps(status))
            
            # 3. Check for Incoming Commands (Non-blocking)
            try:
                # We use a very short timeout to poll for messages
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                message = json.loads(data)
                
                if message["type"] == "switch_ev":
                    controller.switch_vehicle(message["ev_id"])
                    
            except asyncio.TimeoutError:
                pass # No message received, continue loop
            
            # Control loop rate (approx 10Hz)
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        print("Flutter Client Disconnected")
        controller.stop_sumo()
    except Exception as e:
        print(f"Socket Error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)