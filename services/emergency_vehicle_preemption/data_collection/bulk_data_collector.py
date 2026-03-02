import os
import sys
import glob
import pandas as pd
import numpy as np
import traci

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.abspath(os.path.join(BASE_DIR, "../simulation/config/bulk_scenarios"))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../data/raw"))
os.makedirs(DATA_DIR, exist_ok=True)

class UnifiedDataCollector:
    def __init__(self):
        self.eta_data_log = []
        self.safety_data_log = []
        
        # Safety Data state tracker
        self.active_observations = {}

    def run_bulk(self):
        configs = glob.glob(os.path.join(CONFIGS_DIR, "*.sumocfg"))
        print(f"Found {len(configs)} scenarios to process. Starting unified ETA + Safety extraction.")
        
        for idx, config_path in enumerate(configs):
            run_id = f"scenario_{idx}"
            print(f"--- Running {run_id} ({idx+1}/{len(configs)}) ---")
            
            # Using --no-warnings and --no-step-log for speed
            sumo_cmd = ["sumo", "-c", config_path, "--no-step-log", "--no-warnings"]
            try:
                traci.start(sumo_cmd)
                step = 0
                while traci.simulation.getMinExpectedNumber() > 0:
                    traci.simulationStep()
                    self._process_eta(step, run_id)
                    self._process_safety(step, run_id)
                    step += 1
                traci.close()
            except Exception as e:
                print(f"Error in {run_id}: {e}")
                try: traci.close()
                except: pass
                
        self._save_data()

    def _process_eta(self, step, run_id):
        active_evs = [v for v in traci.vehicle.getIDList() if v.startswith("EV_")]
        for ev_id in active_evs:
            try:
                ev_speed = traci.vehicle.getSpeed(ev_id)
                ev_accel = traci.vehicle.getAcceleration(ev_id)
                ev_lane_id = traci.vehicle.getLaneID(ev_id)
                ev_pos = traci.vehicle.getLanePosition(ev_id)
                try:
                    lane_len = traci.lane.getLength(ev_lane_id)
                    dist_to_signal = lane_len - ev_pos
                except:
                    dist_to_signal = 0

                queue_len = traci.lane.getLastStepHaltingNumber(ev_lane_id)
                leader_info = traci.vehicle.getLeader(ev_id, 200)
                if leader_info:
                    leader_gap = leader_info[1]
                    try: leader_speed = traci.vehicle.getSpeed(leader_info[0])
                    except: leader_speed = 30
                else:
                    leader_gap = 200
                    leader_speed = 30

                # Target dataset shape equivalent to data_logger.py
                self.eta_data_log.append({
                    "run_id": run_id,
                    "step": step,
                    "ev_id": f"{run_id}_{ev_id}", # Unique EV ID globally
                    "speed": ev_speed,
                    "acceleration": ev_accel,
                    "distance_to_signal": dist_to_signal,
                    "queue_length": queue_len,
                    "leader_gap": leader_gap,
                    "leader_speed": leader_speed
                })
            except: pass

    def _process_safety(self, step, run_id):
        active_evs = [v for v in traci.vehicle.getIDList() if v.startswith("EV_")]
        for ev_id in active_evs:
            obs_key = f"{run_id}_{ev_id}"
            if obs_key in self.active_observations:
                self._monitor_observation_window(ev_id, obs_key)
            else:
                self._check_for_new_experiment(ev_id, obs_key)

    def _check_for_new_experiment(self, ev_id, obs_key):
        try:
            next_tls = traci.vehicle.getNextTLS(ev_id)
            if not next_tls: return

            tls_id = next_tls[0][0]
            dist = next_tls[0][2]
            tls_index = next_tls[0][1]

            # EV approaches intersection -> Capture simulation dynamics
            if 50 < dist < 150:
                ev_lane = traci.vehicle.getLaneID(ev_id)
                downstream_lane = self._get_downstream_lane(ev_id)
                if not downstream_lane: return

                features = self._extract_safety_features(ev_lane, tls_id, downstream_lane)
                if features:
                    self._force_green_wave(tls_id, tls_index)
                    self.active_observations[obs_key] = {
                        'tls_id': tls_id,
                        'features': features,
                        'stuck_timer': 0,
                        'downstream_lane': downstream_lane,
                        'start_step': traci.simulation.getTime(),
                        'ev_id': ev_id
                    }
        except: pass

    def _monitor_observation_window(self, ev_id, obs_key):
        obs = self.active_observations[obs_key]
        tls_id = obs['tls_id']
        downstream_lane = obs['downstream_lane']
        
        try:
            speed = traci.vehicle.getSpeed(ev_id)
            curr_lane = traci.vehicle.getLaneID(ev_id)
            curr_pos = traci.vehicle.getLanePosition(ev_id)

            # Failure Criteria = 1
            if traci.simulation.getCollidingVehiclesNumber() > 0:
                self._resolve_experiment(obs_key, 1)
                return
            if traci.simulation.getStartingTeleportNumber() > 0:
                self._resolve_experiment(obs_key, 1)
                return

            if speed < 1.0:
                obs['stuck_timer'] += 0.1
                if obs['stuck_timer'] > 5.0:
                    self._resolve_experiment(obs_key, 1)
                    return
            else:
                obs['stuck_timer'] = 0

            if traci.simulation.getTime() - obs['start_step'] > 60:
                self._resolve_experiment(obs_key, 1)
                return

            # Success Criteria = 0
            if curr_lane == downstream_lane and curr_pos > 30.0:
                self._resolve_experiment(obs_key, 0)
                return

        except traci.exceptions.TraCIException:
            # Vehicle safely finished route
            self._resolve_experiment(obs_key, 0)

    def _resolve_experiment(self, obs_key, label):
        obs = self.active_observations[obs_key]
        
        row = obs['features'].copy()
        row['label'] = label
        self.safety_data_log.append(row)
        
        try: traci.trafficlight.setProgram(obs['tls_id'], "0")
        except: pass
        
        del self.active_observations[obs_key]

    def _extract_safety_features(self, ev_lane, tls_id, downstream_lane):
        try:
            target_queue = traci.lane.getLastStepHaltingNumber(ev_lane)
            all_lanes = traci.trafficlight.getControlledLanes(tls_id)
            conflicting_vol = sum(traci.lane.getLastStepVehicleNumber(lane) for lane in set(all_lanes) if lane != ev_lane)
            time_since_change = np.random.uniform(2, 60)
            num_conflicting_lanes = len(set(all_lanes)) - 1
            downstream_len = traci.lane.getLength(downstream_lane)
            clearance_dist = num_conflicting_lanes * 3.5
            
            return {
                "target_queue_length": float(target_queue),
                "conflicting_volume": float(conflicting_vol),
                "time_since_last_phase": float(time_since_change),
                "num_conflicting_lanes": float(max(1, num_conflicting_lanes)),
                "downstream_lane_length": float(downstream_len),
                "clearance_distance": float(clearance_dist)
            }
        except: return None

    def _get_downstream_lane(self, ev_id):
        try:
            route = traci.vehicle.getRoute(ev_id)
            curr_edge = traci.vehicle.getRoadID(ev_id)
            if curr_edge in route:
                idx = route.index(curr_edge)
                if idx + 1 < len(route): return f"{route[idx + 1]}_0"
        except: pass
        return None

    def _force_green_wave(self, tls_id, tls_index):
        try:
            logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            for phase in logic.phases:
                if len(phase.state) > tls_index and phase.state[tls_index] in ('G', 'g'):
                    traci.trafficlight.setRedYellowGreenState(tls_id, phase.state)
                    break
        except: pass

    def _save_data(self):
        print("\n--- SAVING MASSIVE DATASETS ---")
        eta_df = pd.DataFrame(self.eta_data_log)
        eta_path = os.path.join(DATA_DIR, "massive_eta_data.csv")
        eta_df.to_csv(eta_path, index=False)
        print(f"Saved {len(eta_df)} ETA sequence records to {eta_path}")

        if self.safety_data_log:
            safety_df = pd.DataFrame(self.safety_data_log).drop_duplicates()
        else:
            safety_df = pd.DataFrame(columns=["target_queue_length","conflicting_volume","time_since_last_phase","num_conflicting_lanes","downstream_lane_length","clearance_distance","label"])
        
        safety_path = os.path.join(DATA_DIR, "massive_safety_data.csv")
        safety_df.to_csv(safety_path, index=False)
        print(f"Saved {len(safety_df)} Safety outcome records to {safety_path}")

if __name__ == "__main__":
    UnifiedDataCollector().run_bulk()
