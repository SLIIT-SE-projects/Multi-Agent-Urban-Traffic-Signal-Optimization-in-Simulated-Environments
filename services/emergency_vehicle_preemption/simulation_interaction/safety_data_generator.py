import os
import sys
import time
import pandas as pd
import numpy as np
import traci

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "../data/raw")
os.makedirs(DATA_DIR, exist_ok=True)
SUMO_CONFIG = os.path.join(BASE_DIR, "../simulation/config/colombo_mega_scenario.sumocfg")

class OutcomeBasedDataGenerator:
    def __init__(self):
        self.data_log = []
        self.ev_ids = [f"EV_{i}" for i in range(50)]
        
        # State machine to track active observation windows
        # Format: { ev_id: { 'tls_id': ..., 'features': {}, 'stuck_timer': 0, 'downstream_lane': ... } }
        self.active_observations = {}

    def run(self):
        print("Starting Outcome-Based Data Generation...")
        # Run headless for speed
        traci.start(["sumo", "-c", SUMO_CONFIG]) 

        step = 0
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1
            
            # Get currently active EVs
            active_evs = [ev for ev in self.ev_ids if ev in traci.vehicle.getIDList()]
            
            for ev_id in active_evs:
                if ev_id in self.active_observations:
                    # 1. EV is already being monitored -> Check Outcomes
                    self._monitor_observation_window(ev_id)
                else:
                    # 2. EV is not monitored -> Check if we should start an experiment
                    self._check_for_new_experiment(ev_id)
        
        traci.close()
        self._save_data()

    def _check_for_new_experiment(self, ev_id):
        try:
            next_tls = traci.vehicle.getNextTLS(ev_id)
            if not next_tls: return

            tls_id = next_tls[0][0]
            dist = next_tls[0][2]
            tls_index = next_tls[0][1]

            # Trigger condition: EV is between 50m and 150m away from the intersection
            if 50 < dist < 150:
                ev_lane = traci.vehicle.getLaneID(ev_id)
                downstream_lane = self._get_downstream_lane(ev_id)
                
                if not downstream_lane: return

                # A. Extract the 6 Context-Aware Features
                features = self._extract_features(ev_id, ev_lane, tls_id, downstream_lane)
                
                if features:
                    # B. Force the Green Wave (Start the Experiment)
                    self._force_green_wave(tls_id, tls_index)
                    
                    # C. Open the Observation Window
                    self.active_observations[ev_id] = {
                        'tls_id': tls_id,
                        'features': features,
                        'stuck_timer': 0,
                        'downstream_lane': downstream_lane,
                        'start_step': traci.simulation.getTime()
                    }
                    print(f"[{traci.simulation.getTime()}] Started observing {ev_id} at {tls_id}")
        except Exception as e:
            pass # Ignore temporary TraCI errors

    def _monitor_observation_window(self, ev_id):
        obs = self.active_observations[ev_id]
        tls_id = obs['tls_id']
        downstream_lane = obs['downstream_lane']
        
        try:
            speed = traci.vehicle.getSpeed(ev_id)
            curr_lane = traci.vehicle.getLaneID(ev_id)
            curr_pos = traci.vehicle.getLanePosition(ev_id)
            
            # --- CHECK FAILURE CONDITIONS (UNSAFE = 1) ---
            
            # Failure 1: Physical Collision / T-Bone
            if traci.simulation.getCollidingVehiclesNumber() > 0:
                self._resolve_experiment(ev_id, 1, "Collision Detected")
                return

            # Failure 2: Catastrophic Deadlock (Teleport)
            if traci.simulation.getStartingTeleportNumber() > 0:
                self._resolve_experiment(ev_id, 1, "Teleport/Deadlock Detected")
                return

            # Failure 3: Blocked Box (Gridlock)
            # If EV speed drops below 1 m/s inside or right after intersection
            if speed < 1.0:
                obs['stuck_timer'] += 0.1 # Assuming 0.1s step length
                if obs['stuck_timer'] > 5.0: # 5 seconds stuck
                    self._resolve_experiment(ev_id, 1, "EV Blocked in Box")
                    return
            else:
                obs['stuck_timer'] = 0 # Reset if moving

            # Timeout Failure (e.g., took longer than 60s to cross)
            if traci.simulation.getTime() - obs['start_step'] > 60:
                self._resolve_experiment(ev_id, 1, "Timeout (Gridlocked)")
                return

            # --- CHECK SUCCESS CONDITION (SAFE = 0) ---
            
            # Success: EV has reached the downstream lane AND travelled 30 meters safely
            if curr_lane == downstream_lane and curr_pos > 30.0:
                self._resolve_experiment(ev_id, 0, "Cleared Intersection Safely")
                return

        except traci.exceptions.TraCIException:
            # Vehicle might have left the simulation
            self._resolve_experiment(ev_id, 0, "Vehicle Exited Route Safely")

    def _resolve_experiment(self, ev_id, label, reason):
        obs = self.active_observations[ev_id]
        tls_id = obs['tls_id']
        
        # 1. Log the data
        row = obs['features'].copy()
        row['label'] = label # 0 = SAFE, 1 = UNSAFE
        self.data_log.append(row)
        
        status = "🟢 SAFE" if label == 0 else "🔴 UNSAFE"
        print(f"[{traci.simulation.getTime()}] {status} | {ev_id} | Reason: {reason}")
        
        # 2. Release the traffic light (Return to normal operation)
        try:
            traci.trafficlight.setProgram(tls_id, "0")
        except: pass
        
        # 3. Close observation window
        del self.active_observations[ev_id]

    def _extract_features(self, ev_id, ev_lane, tls_id, downstream_lane):
        try:
            # 1. Target Queue Length (Dynamic)
            target_queue = traci.lane.getLastStepHaltingNumber(ev_lane)
            
            # 2. Conflicting Volume (Dynamic)
            all_lanes = traci.trafficlight.getControlledLanes(tls_id)
            conflicting_vol = sum(
                traci.lane.getLastStepVehicleNumber(lane) 
                for lane in set(all_lanes) if lane != ev_lane
            )

            # 3. Time Since Last Phase Change (Dynamic)
            # Simulated variance for training robustness (0 to 60 seconds)
            time_since_change = np.random.uniform(2, 60)

            # 4. Num Conflicting Lanes (Geometric)
            num_conflicting_lanes = len(set(all_lanes)) - 1
            
            # 5. Downstream Lane Length (Geometric)
            downstream_len = traci.lane.getLength(downstream_lane)
            
            # 6. Intersection Clearance Distance (Geometric proxy)
            # We approximate this based on the number of intersecting lanes
            clearance_dist = num_conflicting_lanes * 3.5 # Approx 3.5m per lane width
            
            return {
                "target_queue_length": float(target_queue),
                "conflicting_volume": float(conflicting_vol),
                "time_since_last_phase": float(time_since_change),
                "num_conflicting_lanes": float(max(1, num_conflicting_lanes)),
                "downstream_lane_length": float(downstream_len),
                "clearance_distance": float(clearance_dist)
            }
        except Exception as e:
            return None

    def _get_downstream_lane(self, ev_id):
        try:
            route = traci.vehicle.getRoute(ev_id)
            curr_edge = traci.vehicle.getRoadID(ev_id)
            if curr_edge in route:
                idx = route.index(curr_edge)
                if idx + 1 < len(route):
                    next_edge = route[idx + 1]
                    return f"{next_edge}_0" # Default to lane 0 of next edge
        except: pass
        return None

    def _force_green_wave(self, tls_id, tls_index):
        # Force the state to Red for everyone except EV
        try:
            logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            for phase in logic.phases:
                if len(phase.state) > tls_index and (phase.state[tls_index] == 'G' or phase.state[tls_index] == 'g'):
                    # Found the green phase, lock it
                    traci.trafficlight.setRedYellowGreenState(tls_id, phase.state)
                    break
        except: pass

    def _save_data(self):
        df = pd.DataFrame(self.data_log)
        # Drop duplicates in case of identical snapshots
        df = df.drop_duplicates()
        save_path = os.path.join(DATA_DIR, "outcome_based_safety_data.csv")
        df.to_csv(save_path, index=False)
        print(f"\n--- DATA COLLECTION COMPLETE ---")
        print(f"Total Samples Generated: {len(df)}")
        print(f"Saved to: {save_path}")
        print("\nLabel Distribution:")
        print(df['label'].value_counts())

if __name__ == "__main__":
    OutcomeBasedDataGenerator().run()