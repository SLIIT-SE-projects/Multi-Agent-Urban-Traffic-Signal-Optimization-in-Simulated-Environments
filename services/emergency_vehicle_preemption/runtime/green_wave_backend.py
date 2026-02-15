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
import random
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GreenWaveController:
    def __init__(self): 
        self.ev_id = "EV_0" # The EV currently focused on the Mobile App
        self.running = False
        
        print("Loading AI Models...")
        try:
            self.model = tf.keras.models.load_model(MODEL_PATH)
            with open(SCALER_PATH, "rb") as f:
                self.scaler = pickle.load(f)
            with open(SAFETY_MODEL_PATH, "rb") as f:
                self.safety_model = pickle.load(f)
            print("SUCCESS: All Models loaded.")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not load models. {e}")
            sys.exit(1)

        self.sequence_length = 10
        self.alpha = 0.3
        
        # --- FLEET ARCHITECTURE ---
        # self.fleet manages the state of ALL active EVs in the simulation
        self.fleet = {} 
        
        # State Lock-In: Maps {tls_id: winner_ev_id}
        # Ensures that once an EV wins and locks a light, it keeps it until it passes.
        self.active_override_tls_ids = {} 

    def start_sumo(self):
        sumo_cmd = ["sumo-gui", "-c", SUMO_CONFIG, "--start"]
        traci.start(sumo_cmd)
        self.running = True
        print("Simulation Started.")

    def stop_sumo(self):
        try:
            traci.close()
            self.running = False
        except: pass

    def simulation_step(self):
        if not self.running: return None

        try:
            if traci.simulation.getMinExpectedNumber() <= 0:
                self.stop_sumo()
                return None

            traci.simulationStep()
            
            # --- 1. GLOBAL RADAR: Update state for ALL vehicles ---
            self._update_global_fleet_state()
            
            # --- 2. THE ARBITER: Manage conflicts and preemption for ALL vehicles ---
            self._manage_fleet_preemption()

            # --- 3. PRESENTATION: Return data only for the selected EV to the App ---
            return self._build_status_packet()

        except Exception as e:
            print(f"Sim Error: {e}")
            return None

    def switch_vehicle(self, new_ev_id):
        """Called by Flutter App to change the UI Focus."""
        print(f"UI Focus switched to {new_ev_id}")
        self.ev_id = new_ev_id
        try:
            traci.gui.trackVehicle("View #0", self.ev_id)
            traci.gui.setZoom("View #0", 600)
        except: pass

    def set_ev_priority(self, target_ev_id, new_priority):
        """Called by Flutter App to dynamically change an EV's dispatch priority."""
        if target_ev_id in self.fleet:
            self.fleet[target_ev_id]["priority"] = int(new_priority)
            print(f"Elevated {target_ev_id} to Priority Level {new_priority}")

    # ==========================================
    # --- FLEET RADAR & STATE MANAGEMENT ---
    # ==========================================
    def _update_global_fleet_state(self):
        active_vehicles = traci.vehicle.getIDList()
        current_evs = [v for v in active_vehicles if v.startswith("EV_")]
        
        # Remove EVs that finished their route
        stale_evs = [ev for ev in self.fleet.keys() if ev not in current_evs]
        for ev in stale_evs:
            del self.fleet[ev]

        # Update or initialize active EVs
        for ev in current_evs:
            if ev not in self.fleet:
                self.fleet[ev] = {
                    "buffer": deque(maxlen=self.sequence_length),
                    "smoothed_eta": None,
                    "priority": random.choice([1, 2]), # Default to Standard or Medium
                    "safety_blocked": False,
                    "speed": 0.0
                }
            
            # Extract features for ETA Prediction
            features = self._get_live_features(ev)
            if features:
                fleet_ev = self.fleet[ev]
                fleet_ev["buffer"].append(features)
                fleet_ev["speed"] = features[0]
                
                # Predict ETA if buffer is full
                if len(fleet_ev["buffer"]) == self.sequence_length:
                    raw_eta = self._predict_eta(ev)
                    if fleet_ev["smoothed_eta"] is None: 
                        fleet_ev["smoothed_eta"] = raw_eta
                    else: 
                        fleet_ev["smoothed_eta"] = (self.alpha * raw_eta) + ((1 - self.alpha) * fleet_ev["smoothed_eta"])

    # ==========================================
    # --- MULTI-EV PRIORITY ARBITER ---
    # ==========================================
    def _manage_fleet_preemption(self):
        # 1. CLEANUP STALE LOCKS (Hysteresis Release)
        # If the winning EV passed the light or disconnected, release the lock.
        locks_to_remove = []
        for tls_id, owner_id in self.active_override_tls_ids.items():
            if owner_id not in self.fleet:
                locks_to_remove.append(tls_id)
            else:
                try:
                    next_tls_list = [t[0] for t in traci.vehicle.getNextTLS(owner_id)]
                    if tls_id not in next_tls_list:
                        locks_to_remove.append(tls_id) # EV passed the intersection
                except:
                    locks_to_remove.append(tls_id)
        
        for tls_id in locks_to_remove:
            self._release_control(tls_id)

        # 2. THE AUCTION HOUSE (Gather all bids)
        intersection_bids = {} # {tls_id: [ {ev_id, priority, eta, index} ] }
        
        for ev, data in self.fleet.items():
            if data["smoothed_eta"] is None: continue
            
            try:
                next_tls_list = traci.vehicle.getNextTLS(ev)
                planning_speed = max(data["speed"], 10.0)

                for i, tls_info in enumerate(next_tls_list):
                    t_id = tls_info[0]
                    t_index = tls_info[1]
                    t_dist = tls_info[2]
                    
                    if i == 0: t_eta = data["smoothed_eta"]
                    else: t_eta = t_dist / planning_speed

                    if t_eta < 30.0 or t_dist < 100.0:
                        if t_id not in intersection_bids:
                            intersection_bids[t_id] = []
                        
                        # Apply Hysteresis: If this EV already owns the lock, give it infinite priority
                        bid_priority = data["priority"]
                        if self.active_override_tls_ids.get(t_id) == ev:
                            bid_priority = 999 

                        intersection_bids[t_id].append({
                            "ev_id": ev,
                            "priority": bid_priority,
                            "eta": t_eta,
                            "tls_index": t_index,
                            "order": i # Track if it's the immediate light (0) or downstream
                        })
            except: pass

        # 3. RESOLVE CONFLICTS (Who wins?)
        provisional_wins = {ev: [] for ev in self.fleet.keys()} # {ev_id: [tls_id_1, tls_id_2]}

        for tls_id, bids in intersection_bids.items():
            # Hierarchy of Needs: Sort by Priority (Desc), then ETA (Asc)
            bids.sort(key=lambda x: (-x["priority"], x["eta"]))
            winner = bids[0]
            provisional_wins[winner["ev_id"]].append({
                "tls_id": tls_id, 
                "index": winner["tls_index"],
                "order": winner["order"]
            })

        # 4. SAFETY CHECK & EXECUTION (Cascading Block logic)
        for ev, won_lights in provisional_wins.items():
            self.fleet[ev]["safety_blocked"] = False # Reset flag
            won_lights.sort(key=lambda x: x["order"]) # Ensure we process sequential order A -> B -> C

            for light in won_lights:
                t_id = light["tls_id"]
                t_index = light["index"]

                # If we already locked it, skip safety check (Hysteresis)
                if self.active_override_tls_ids.get(t_id) == ev:
                    continue 

                # Ask the Gatekeeper
                is_safe = self._evaluate_safety(t_id, ev)
                
                if is_safe:
                    self._force_green_wave(t_id, t_index, ev)
                else:
                    # AI DENIED PREEMPTION -> CASCADE BLOCK
                    self.fleet[ev]["safety_blocked"] = True
                    if light["order"] == 0:
                        print(f"⚠️ SAFETY GUARD: {ev} denied at {t_id} (Gridlock risk).")
                    break # Halt downstream preemption for this EV

    def _release_control(self, tls_id):
        if tls_id in self.active_override_tls_ids:
            try: traci.trafficlight.setProgram(tls_id, "0")
            except: pass
            del self.active_override_tls_ids[tls_id]

    # ==========================================
    # --- AI INFERENCE METHODS (Updated for Fleet) ---
    # ==========================================
    def _evaluate_safety(self, tls_id, ev_id):
        try:
            ev_lane = traci.vehicle.getLaneID(ev_id)
            downstream_lane = self._get_downstream_lane(ev_id)
            if not downstream_lane: return True

            target_queue = traci.lane.getLastStepHaltingNumber(ev_lane)
            all_lanes = traci.trafficlight.getControlledLanes(tls_id)
            conflicting_vol = sum(
                traci.lane.getLastStepVehicleNumber(lane) 
                for lane in set(all_lanes) if lane != ev_lane
            )
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

            prediction = self.safety_model.predict(features_df)[0]
            if prediction == 1: return False # UNSAFE
            return True # SAFE

        except Exception as e:
            return True 

    def _force_green_wave(self, tls_id, tls_index, ev_id):
        try:
            logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            phases = logic.phases
            best_phase_idx = -1
            for i, phase in enumerate(phases):
                if len(phase.state) > tls_index:
                    char = phase.state[tls_index]
                    if char == 'G' or char == 'g':
                        best_phase_idx = i
                        break
            
            if best_phase_idx != -1:
                target_state = phases[best_phase_idx].state
                traci.trafficlight.setRedYellowGreenState(tls_id, target_state)
                # Assign Lock Ownership to this EV!
                self.active_override_tls_ids[tls_id] = ev_id
        except Exception as e:
            pass

    def _get_live_features(self, ev_id):
        try:
            speed = traci.vehicle.getSpeed(ev_id)
            accel = traci.vehicle.getAcceleration(ev_id)
            lane_id = traci.vehicle.getLaneID(ev_id)
            pos = traci.vehicle.getLanePosition(ev_id)
            try: dist = traci.lane.getLength(lane_id) - pos
            except: dist = 0
            queue = traci.lane.getLastStepHaltingNumber(lane_id)
            leader = traci.vehicle.getLeader(ev_id, 200)
            if leader: l_gap, l_speed = leader[1], traci.vehicle.getSpeed(leader[0])
            else: l_gap, l_speed = 200, 30
            
            tls_val = 0.0
            next_tls = traci.vehicle.getNextTLS(ev_id)
            if next_tls:
                s = next_tls[0][3]
                if s in ['r', 'R', 'u']: tls_val = 1.0 
                elif s in ['y', 'Y']: tls_val = 0.5    
            
            return [speed, accel, dist, queue, l_gap, l_speed, tls_val]
        except: return None

    def _predict_eta(self, ev_id):
        raw_sequence = np.array(self.fleet[ev_id]["buffer"])
        feature_cols = ['speed', 'acceleration', 'distance_to_signal', 
                        'queue_length', 'leader_gap', 'leader_speed', 'tls_state']
        scaled = np.zeros_like(raw_sequence)
        for i in range(len(raw_sequence)):
            step_df = pd.DataFrame([raw_sequence[i]], columns=feature_cols)
            scaled[i] = self.scaler.transform(step_df)[0]
        input_data = scaled.reshape(1, self.sequence_length, 7)
        return self.model.predict(input_data, verbose=0)[0][0]

    def _get_downstream_lane(self, ev_id):
        try:
            route = traci.vehicle.getRoute(ev_id)
            curr_edge = traci.vehicle.getRoadID(ev_id)
            if curr_edge in route:
                idx = route.index(curr_edge)
                if idx + 1 < len(route):
                    next_edge = route[idx + 1]
                    return f"{next_edge}_0" 
        except: pass
        return None

    # ==========================================
    # --- PRESENTATION / API ---
    # ==========================================
    def _build_status_packet(self):
        # We only send data for the UI-selected vehicle
        if self.ev_id not in self.fleet:
            return {
                "type": "status", "ev_id": self.ev_id, "active": False,
                "eta": 0.0, "speed": 0.0, "lat": 0.0, "lon": 0.0,
                "priority": 1, "green_wave_active": False, "safety_blocked": False,
                "tls_id": "", "active_junctions": []
            }

        ev_data = self.fleet[self.ev_id]
        
        try:
            speed = ev_data["speed"]
            x, y = traci.vehicle.getPosition(self.ev_id)
            try: lon, lat = traci.simulation.convertGeo(x, y)
            except: lat, lon = 0.0, 0.0

            dist_to_tls = 0.0
            display_tls_id = ""
            try:
                next_tls_info = traci.vehicle.getNextTLS(self.ev_id)
                if next_tls_info:
                    dist_to_tls = next_tls_info[0][2]
                    # Find if any upcoming lights are locked by THIS specific EV
                    for tls_item in next_tls_info:
                        if self.active_override_tls_ids.get(tls_item[0]) == self.ev_id:
                            display_tls_id = tls_item[0]
                            break
            except: pass

            is_green_wave = (display_tls_id != "")
            
            # Show ONLY junctions locked by this specific EV on the map
            active_junctions = []
            for tls_id, owner in self.active_override_tls_ids.items():
                if owner == self.ev_id:
                    try:
                        j_pos = traci.junction.getPosition(tls_id)
                        j_lon, j_lat = traci.simulation.convertGeo(j_pos[0], j_pos[1])
                        active_junctions.append({"id": tls_id, "lat": j_lat, "lon": j_lon})
                    except: pass

            return {
                "type": "status",
                "ev_id": self.ev_id,
                "active": True,
                "eta": float(f"{ev_data['smoothed_eta']:.1f}") if ev_data['smoothed_eta'] else 0.0,
                "speed": float(f"{speed * 3.6:.1f}"),
                "dist_to_tls": float(f"{dist_to_tls:.1f}"),
                "lat": lat,
                "lon": lon,
                "priority": ev_data["priority"],
                "green_wave_active": is_green_wave,
                "safety_blocked": ev_data["safety_blocked"],
                "tls_id": display_tls_id,
                "active_junctions": active_junctions
            }
        except:
            return {"type": "status", "ev_id": self.ev_id, "active": False}

# --- GLOBAL INSTANCE ---
controller = GreenWaveController()

# --- WEBSOCKET HANDLER ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Flutter Client Connected!")
    
    if not controller.running:
        controller.start_sumo()

    try:
        while True:
            status = controller.simulation_step()
            if status:
                await websocket.send_text(json.dumps(status))
            
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                message = json.loads(data)
                
                if message["type"] == "switch_ev":
                    controller.switch_vehicle(message["ev_id"])
                elif message["type"] == "set_priority":
                    # NEW: Flutter app can dictate priority level dynamically
                    controller.set_ev_priority(message["ev_id"], message["priority"])
                    
            except asyncio.TimeoutError:
                pass 
            
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        print("Flutter Client Disconnected")
        controller.stop_sumo()
    except Exception as e:
        print(f"Socket Error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)