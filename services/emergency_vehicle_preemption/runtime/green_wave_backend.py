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
SAFETY_MODEL_PATH = os.path.join(BASE_DIR, "../models/saved/outcome_safety_classifier.pkl")
SUMO_CONFIG = os.path.join(BASE_DIR, "../simulation/config/colombo_mega_scenario.sumocfg")

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
        self.ev_id = "EV_0"  # Default
        self.running = False
        
        print("Loading AI Models...")
        try:
            # 1. Load ETA Predictor (LSTM)
            self.model = tf.keras.models.load_model(MODEL_PATH)
            with open(SCALER_PATH, "rb") as f:
                self.scaler = pickle.load(f)
                
            # 2. Load Safety Guard (Decision Tree)
            with open(SAFETY_MODEL_PATH, "rb") as f:
                self.safety_model = pickle.load(f)
                
            print("SUCCESS: All Models loaded (ETA Predictor & Safety Classifier).")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not load models. {e}")
            sys.exit(1)

        self.sequence_length = 10
        self.state_buffer = deque(maxlen=self.sequence_length)
        
        # State
        self.active_override_tls_ids = set()
        self.active_green_lane = None
        self.smoothed_eta = None
        self.alpha = 0.3
        self.last_broadcast_status = {}
        self.safety_blocked = False  # Tracks if the AI denied a green wave

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
                return self._build_status_packet(active=False)

            # --- CONTROL LOGIC ---
            features = self._get_live_features()
            if features:
                self.state_buffer.append(features)
                if len(self.state_buffer) == self.sequence_length:
                    raw_eta = self._predict_eta()
                    if self.smoothed_eta is None: 
                        self.smoothed_eta = raw_eta
                    else: 
                        self.smoothed_eta = (self.alpha * raw_eta) + ((1 - self.alpha) * self.smoothed_eta)
                    
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
        for old_id in list(self.active_override_tls_ids):
            self._release_control(old_id)
        self.smoothed_eta = None
        self.safety_blocked = False
        
        try:
            traci.gui.trackVehicle("View #0", self.ev_id)
            traci.gui.setZoom("View #0", 600)
        except:
            pass

    def _build_status_packet(self, active):
        if not active:
            return {
                "type": "status",
                "ev_id": self.ev_id,
                "active": False,
                "eta": 0.0,
                "speed": 0.0,
                "lat": 0.0,
                "lon": 0.0,
                "green_wave_active": False,
                "safety_blocked": False,
                "tls_id": ""
            }

        try:
            speed = traci.vehicle.getSpeed(self.ev_id)
            x, y = traci.vehicle.getPosition(self.ev_id)
            
            try:
                lon, lat = traci.simulation.convertGeo(x, y)
            except Exception:
                lat, lon = 0.0, 0.0

            dist_to_tls = 0.0
            try:
                next_tls_info = traci.vehicle.getNextTLS(self.ev_id)
                if next_tls_info:
                    dist_to_tls = next_tls_info[0][2]
            except: pass

            is_green_wave = (len(self.active_override_tls_ids) > 0)
            
            display_tls_id = ""
            try:
                next_all = traci.vehicle.getNextTLS(self.ev_id)
                for tls_item in next_all:
                    if tls_item[0] in self.active_override_tls_ids:
                        display_tls_id = tls_item[0]
                        break
            except: pass
            
            active_junctions = []
            for tls_id in self.active_override_tls_ids:
                j_lon, j_lat = 0.0, 0.0
                try:
                    lanes = traci.trafficlight.getControlledLanes(tls_id)
                    if lanes:
                        first_lane_shape = traci.lane.getShape(lanes[0])
                        if first_lane_shape:
                            j_pos = first_lane_shape[-1]
                            j_lon, j_lat = traci.simulation.convertGeo(j_pos[0], j_pos[1])
                    
                    if j_lon == 0.0 and j_lat == 0.0:
                         j_pos = traci.junction.getPosition(tls_id)
                         j_lon, j_lat = traci.simulation.convertGeo(j_pos[0], j_pos[1])
                except: pass
                
                if j_lat != 0.0 and j_lon != 0.0:
                    active_junctions.append({"id": tls_id, "lat": j_lat, "lon": j_lon})

            return {
                "type": "status",
                "ev_id": self.ev_id,
                "active": True,
                "eta": float(f"{self.smoothed_eta:.1f}") if self.smoothed_eta else 0.0,
                "speed": float(f"{speed * 3.6:.1f}"),
                "dist_to_tls": float(f"{dist_to_tls:.1f}"),
                "lat": lat,
                "lon": lon,
                "green_wave_active": is_green_wave,
                "safety_blocked": self.safety_blocked,
                "tls_id": display_tls_id,
                "active_junctions": active_junctions
            }
        except:
            return self._build_status_packet(active=False)

    def _release_control(self, tls_id):
        if tls_id in self.active_override_tls_ids:
            try:
                traci.trafficlight.setProgram(tls_id, "0")
            except: pass
            self.active_override_tls_ids.discard(tls_id)

    def _get_downstream_lane(self):
        """Helper to find the lane the EV will enter after the intersection."""
        try:
            route = traci.vehicle.getRoute(self.ev_id)
            curr_edge = traci.vehicle.getRoadID(self.ev_id)
            if curr_edge in route:
                idx = route.index(curr_edge)
                if idx + 1 < len(route):
                    next_edge = route[idx + 1]
                    return f"{next_edge}_0"
        except: pass
        return None

    def _evaluate_safety(self, tls_id):
        """Passes intersection state through the Decision Tree to determine safety."""
        try:
            ev_lane = traci.vehicle.getLaneID(self.ev_id)
            downstream_lane = self._get_downstream_lane()
            if not downstream_lane: return True 

            target_queue = traci.lane.getLastStepHaltingNumber(ev_lane)
            all_lanes = traci.trafficlight.getControlledLanes(tls_id)
            conflicting_vol = sum(
                traci.lane.getLastStepVehicleNumber(lane)
                for lane in set(all_lanes) if lane != ev_lane
            )

            # Using a stable settling time for simulation demo
            time_since_change = 10.0
            num_conflicting_lanes = len(set(all_lanes)) - 1
            downstream_len = traci.lane.getLength(downstream_lane)
            clearance_dist = num_conflicting_lanes * 3.5

            feature_cols = [
                "target_queue_length", "conflicting_volume", "time_since_last_phase",
                "num_conflicting_lanes", "downstream_lane_length", "clearance_distance"
            ]
            features_df = pd.DataFrame([[
                target_queue, conflicting_vol, time_since_change,
                max(1, num_conflicting_lanes), downstream_len, clearance_dist
            ]], columns=feature_cols)

            # Predict (0 = SAFE, 1 = UNSAFE)
            prediction = self.safety_model.predict(features_df)[0]
            return False if prediction == 1 else True

        except Exception as e:
            print(f"Safety evaluation error: {e}")
            return True 

    def _manage_preemption(self, eta_first_light):
        try:
            next_tls_list = traci.vehicle.getNextTLS(self.ev_id)
            if not next_tls_list:
                for old_id in list(self.active_override_tls_ids):
                    self._release_control(old_id)
                self.safety_blocked = False
                return

            target_green_map = {} 
            current_speed = traci.vehicle.getSpeed(self.ev_id)
            planning_speed = max(current_speed, 10.0)

            # Reset safety flag
            self.safety_blocked = False

            # Iterate through upcoming intersections sequentially
            for i, tls_info in enumerate(next_tls_list):
                t_id = tls_info[0]
                t_index = tls_info[1]
                t_dist = tls_info[2]
                
                if i == 0: 
                    t_eta = eta_first_light
                else: 
                    t_eta = t_dist / planning_speed

                # Trigger Condition: EV is within 30s or 100m
                if t_eta < 30.0 or t_dist < 100.0:
                    
                    # Evaluate safety for THIS specific intersection in the chain
                    is_safe = self._evaluate_safety(t_id)
                    
                    if is_safe:
                        # It is cleared/safe. Add to preemption map and continue to next downstream light.
                        target_green_map[t_id] = t_index
                    else:
                        # THE CHAIN BREAKS HERE.
                        # We only preempt downstream IF all upstream route intersections are cleared.
                        if i == 0:
                            self.safety_blocked = True
                            print(f"⚠️ SAFETY GUARD: Immediate intersection {t_id} is unsafe. Preemption Denied.")
                        else:
                            print(f"⚠️ SAFETY GUARD: Downstream {t_id} is unsafe. Halting Green Wave extension.")
                        
                        # Stop checking downstream. Do not preempt this or any further intersections!
                        break 

            # Apply Controls
            current_active = list(self.active_override_tls_ids)
            for old_id in current_active:
                if old_id not in target_green_map:
                    self._release_control(old_id)

            for new_id, new_index in target_green_map.items():
                if new_id not in self.active_override_tls_ids:
                    self._force_green_wave(new_id, new_index)

        except Exception as e:
            print(f"Preemption Logic Error: {e}")

    def _force_green_wave(self, tls_id, tls_index):
        try:
            logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            phases = logic.phases
            best_phase_idx = -1
            for i, phase in enumerate(phases):
                if len(phase.state) > tls_index:
                    char = phase.state[tls_index]
                    if char in ['G', 'g']:
                        best_phase_idx = i
                        break
            
            if best_phase_idx != -1:
                target_state = phases[best_phase_idx].state
                traci.trafficlight.setRedYellowGreenState(tls_id, target_state)
                self.active_override_tls_ids.add(tls_id)
        except Exception:
            pass

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
            l_gap, l_speed = (leader[1], traci.vehicle.getSpeed(leader[0])) if leader else (200, 30)
            
            tls_val = 0.0
            next_tls = traci.vehicle.getNextTLS(self.ev_id)
            if next_tls:
                s = next_tls[0][3]
                if s in ['r', 'R', 'u']: tls_val = 1.0
                elif s in ['y', 'Y']: tls_val = 0.5    
            
            return [speed, accel, dist, queue, l_gap, l_speed, tls_val]
        except: return None

    def _predict_eta(self):
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