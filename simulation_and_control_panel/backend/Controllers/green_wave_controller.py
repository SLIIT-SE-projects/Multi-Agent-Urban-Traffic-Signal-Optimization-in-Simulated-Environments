import os
import sys
import traci
import numpy as np
import pandas as pd
import tensorflow as tf
import pickle
import json
from collections import deque

class GreenWaveController:
    def __init__(self, use_gui=True):
        self.ev_id = "EV_0"  # Default
        self.active = False # Controlled by frontend/websocket presence
        
        # --- PATHS (Relative to backend execution) ---
        # Assuming app is run from simulation_and_control_panel/backend
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # traffic.../simulation_and_control_panel/backend
        self.REPO_ROOT = os.path.dirname(os.path.dirname(self.BASE_DIR))
        
        self.MODEL_PATH = os.path.join(self.REPO_ROOT, "services", "emergency_vehicle_preemption", "models", "saved", "eta_predictor.h5")
        self.SCALER_PATH = os.path.join(self.REPO_ROOT, "services", "emergency_vehicle_preemption", "data", "scalers", "eta_scaler.pkl")
        
        print(f"GreenWave: Loading AI Models from {self.MODEL_PATH}...")
        try:
            self.model = tf.keras.models.load_model(self.MODEL_PATH)
            with open(self.SCALER_PATH, "rb") as f:
                self.scaler = pickle.load(f)
            print("GreenWave: SUCCESS - Models loaded.")
        except Exception as e:
            print(f"GreenWave: WARNING - Could not load models. Logic will run without predictions. {e}")
            self.model = None
            self.scaler = None

        self.sequence_length = 10
        self.state_buffer = deque(maxlen=self.sequence_length)
        
        # State
        self.active_override_tls_ids = set() 
        self.smoothed_eta = None 
        self.alpha = 0.3
        
        # Socket for broadcasting
        self.ws_connection = None 

    def set_websocket(self, ws):
        """Sets the active WebSocket connection for the driver app"""
        # [FLOW START] Trigger: App Connected
        # When driver opens the app, we enable the controller.
        self.ws_connection = ws
        self.active = True 
        print("GreenWave: Driver App Connected")

    def disconnect_websocket(self):
        # [FLOW END] Safety Valve: App Disconnected
        # If app closes/crashes, we immediately kill the logic and release lights.
        self.ws_connection = None
        self.active = False 
        print("GreenWave: Driver App Disconnected")
        self._release_all() # FAIL-SAFE: Reset lights to normal program

    def switch_vehicle(self, new_ev_id):
        print(f"GreenWave: Switch to {new_ev_id}")
        self.ev_id = new_ev_id
        self.state_buffer.clear()
        self._release_all()
        self.smoothed_eta = None
        
        try:
            traci.gui.trackVehicle("View #0", self.ev_id)
            traci.gui.setZoom("View #0", 600)
        except: pass

    def execute_step(self):
        """Called by SimulationController every step"""
        # [FLOW CHECK] The Kill Switch
        # If app is closed (active=False), checking stops here. 
        # No AI inference, no preemption, zero overhead.
        if not self.active or not self.ws_connection:
            return

        try:
             # Basic EV Existence Check
            if self.ev_id not in traci.vehicle.getIDList():
                self._broadcast_status(active=False)
                return

            # --- CONTROL LOGIC ---
            if self.model and self.scaler:
                features = self._get_live_features()
                if features:
                    self.state_buffer.append(features)
                    if len(self.state_buffer) == self.sequence_length:
                        raw_eta = self._predict_eta()
                        if self.smoothed_eta is None: self.smoothed_eta = raw_eta
                        else: self.smoothed_eta = (self.alpha * raw_eta) + ((1 - self.alpha) * self.smoothed_eta)
                        
                        self._manage_preemption(self.smoothed_eta)

            self._broadcast_status(active=True)

        except Exception as e:
            print(f"GreenWave Step Error: {e}")

    def _broadcast_status(self, active):
        if not self.ws_connection: return

        payload = self._build_status_packet(active)
        try:
            self.ws_connection.send(json.dumps(payload))
        except Exception as e:
            print(f"GreenWave Send Error: {e}")
            self.disconnect_websocket()

    def _build_status_packet(self, active):
        if not active:
            return {
                "type": "status", "ev_id": self.ev_id, "active": False,
                "eta": 0.0, "speed": 0.0, "lat": 0.0, "lon": 0.0,
                "green_wave_active": False, "tls_id": ""
            }

        try:
            speed = traci.vehicle.getSpeed(self.ev_id)
            x, y = traci.vehicle.getPosition(self.ev_id)
            try:
                lon, lat = traci.simulation.convertGeo(x, y)
            except:
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
            
            # Active Junctions for Map
            active_junctions = []
            for tls_id in self.active_override_tls_ids:
                j_lon, j_lat = 0.0, 0.0
                try:
                    lanes = traci.trafficlight.getControlledLanes(tls_id)
                    if lanes:
                        shape = traci.lane.getShape(lanes[0])
                        if shape:
                            j_pos = shape[-1] 
                            j_lon, j_lat = traci.simulation.convertGeo(j_pos[0], j_pos[1])
                    if j_lon == 0.0:
                         j_pos = traci.junction.getPosition(tls_id)
                         j_lon, j_lat = traci.simulation.convertGeo(j_pos[0], j_pos[1])
                except: pass
                
                if j_lat != 0.0:
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
                "tls_id": display_tls_id,
                "active_junctions": active_junctions
            }
        except:
             return self._build_status_packet(active=False)

    def _release_all(self):
        for old_id in list(self.active_override_tls_ids):
            self._release_control(old_id)

    def _release_control(self, tls_id):
        if tls_id in self.active_override_tls_ids:
            try:
                traci.trafficlight.setProgram(tls_id, "0")
            except: pass
            self.active_override_tls_ids.discard(tls_id)

    def _manage_preemption(self, eta_first_light):
        try:
            next_tls_list = traci.vehicle.getNextTLS(self.ev_id)
            if not next_tls_list:
                self._release_all()
                return

            target_green_map = {} 
            current_speed = traci.vehicle.getSpeed(self.ev_id)
            planning_speed = max(current_speed, 10.0)

            for i, tls_info in enumerate(next_tls_list):
                t_id = tls_info[0]
                t_index = tls_info[1]
                t_dist = tls_info[2]
                
                if i == 0: t_eta = eta_first_light
                else: t_eta = t_dist / planning_speed

                if i == 0:
                    # First Light: Use AI ETA
                    if t_eta < 30.0:
                        if t_id not in target_green_map:
                            target_green_map[t_id] = t_index
                else:
                     # Subsequent Lights: Distance 100m
                     if t_dist < 100.0:
                        if t_id not in target_green_map:
                            target_green_map[t_id] = t_index

            current_active = list(self.active_override_tls_ids)
            for old_id in current_active:
                if old_id not in target_green_map:
                    self._release_control(old_id)

            for new_id, new_index in target_green_map.items():
                if new_id not in self.active_override_tls_ids:
                    self._force_green_wave(new_id, new_index)

        except Exception as e:
            print(f"GreenWave Preemption Error: {e}")

    def _force_green_wave(self, tls_id, tls_index):
        try:
            logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            phases = logic.phases
            best_phase_idx = -1
            
            for i, phase in enumerate(phases):
                if len(phase.state) > tls_index:
                    char = phase.state[tls_index]
                    if char.lower() == 'g':
                        best_phase_idx = i
                        break
            
            if best_phase_idx != -1:
                target_state = phases[best_phase_idx].state
                traci.trafficlight.setRedYellowGreenState(tls_id, target_state)
                self.active_override_tls_ids.add(tls_id)
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
            
            l_gap, l_speed = 200, 30
            leader = traci.vehicle.getLeader(self.ev_id, 200)
            if leader: l_gap, l_speed = leader[1], traci.vehicle.getSpeed(leader[0])
            
            tls_val = 0.0
            next_tls = traci.vehicle.getNextTLS(self.ev_id)
            if next_tls:
                s = next_tls[0][3]
                if s.lower() in ['r', 'u']: tls_val = 1.0 
                elif s.lower() == 'y': tls_val = 0.5    
            
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
