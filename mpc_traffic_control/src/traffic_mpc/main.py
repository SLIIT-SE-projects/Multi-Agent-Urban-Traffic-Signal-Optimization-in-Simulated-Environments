"""
Main Application Entry Point.
Features: 
- INCIDENCE MATRIX BUILDING (Maps Phases to Lanes)
- THROUGHPUT MAXIMIZATION
- ANTI-SPILLBACK
"""
import logging
import hydra
import traci 
import numpy as np
from omegaconf import DictConfig, OmegaConf
from traffic_mpc.config.settings import AppConfig
from traffic_mpc.interface.sumo_client import SumoClient
from traffic_mpc.core.estimation import StateEstimator
from traffic_mpc.core.controller import MPCController
from traffic_mpc.core.prediction import DemandPredictor 
from traffic_mpc.utils.logging import setup_logging
from traffic_mpc.utils.telemetry import TelemetryRecorder

@hydra.main(version_base=None, config_path="../../conf", config_name="config")
def main(cfg: DictConfig):
    try:
        app_config = AppConfig(**OmegaConf.to_container(cfg, resolve=True))
    except Exception as e:
        print(f"Configuration Error: {e}")
        return

    setup_logging(app_config.logging)
    logger = logging.getLogger(__name__)
    logger.info("--- Starting MPC (Matrix Incidence Mode) ---")
    
    do_control = cfg.get("control_enabled", True)
    
    client = SumoClient(app_config.sumo)
    client.start()

    try:
        client.step()
        detectors = client.get_detector_data()
        # Map detectors to lanes
        det_lane_map = {d: traci.lanearea.getLaneID(d) for d in traci.lanearea.getIDList()}
        all_lanes = sorted(list(set(det_lane_map.values())))
        
        # Capacities
        lane_capacities = {}
        for lid in all_lanes:
            try:
                lane_capacities[lid] = traci.lane.getLength(lid) / 7.5
            except:
                lane_capacities[lid] = 40.0

        tls_ids = traci.trafficlight.getIDList()
        estimator = StateEstimator(link_ids=all_lanes)
        predictor = DemandPredictor(app_config.mpc, all_lanes, "data/model.pth")
        
        controllers = {}
        # Store incidence matrices per TLS
        tls_matrices = {}
        
        for tls_id in tls_ids:
            links = traci.trafficlight.getControlledLinks(tls_id)
            # Get unique incoming lanes
            local_lanes = sorted(list(set([l[0][0] for l in links if l])))
            
            # Filter for monitored
            local_lanes = [l for l in local_lanes if l in all_lanes]
            
            if local_lanes:
                controllers[tls_id] = MPCController(app_config.mpc, app_config.optimization, local_lanes, [])
                
                # --- BUILD INCIDENCE MATRIX ---
                # Rows = Lanes, Cols = Phases (Assume 4)
                phases = 4
                inc_matrix = np.zeros((len(local_lanes), phases))
                
                logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
                # Look at first 4 Green phases (or as many as exist)
                p_idx = 0
                for phase in logic.phases:
                    if 'G' in phase.state or 'g' in phase.state:
                        if p_idx >= phases: break
                        
                        # Check which lanes are Green in this phase state string
                        for i, char in enumerate(phase.state):
                            if char.lower() == 'g':
                                # Find which lane corresponds to index i
                                # links[i] is a list of connections from one lane
                                if i < len(links):
                                    for link in links[i]:
                                        lane_id = link[0]
                                        if lane_id in local_lanes:
                                            l_idx = local_lanes.index(lane_id)
                                            inc_matrix[l_idx, p_idx] = 1
                        p_idx += 1
                        
                tls_matrices[tls_id] = inc_matrix

        recorder = TelemetryRecorder(app_config.logging.log_dir, "simulation_data.csv", 
                                   ["step", "time", "avg_queue", "max_queue", "avg_split"])

        control_interval = 60 
        step = 0
        max_steps = 3600

        while step < max_steps:
            client.step()
            
            raw_det = client.get_detector_data()
            lane_data = {det_lane_map.get(d): val for d, val in raw_det.items() if d in det_lane_map}
            
            state = estimator.update(lane_data)
            predictor.update_history(lane_data)
            
            avg_split = 0.0
            
            if do_control and (step % control_interval == 0):
                # Shape [n_total_lanes, Horizon]
                global_demand = predictor.predict() 
                
                total_green = 0
                count = 0
                
                for tls_id, controller in controllers.items():
                    # 1. Prepare Local Data
                    indices = [all_lanes.index(l) for l in controller.lane_ids]
                    
                    # Ensure Demand is [n_local_lanes, N]
                    # global_demand might be 1D or 2D. 
                    if global_demand.ndim == 1:
                        # Reshape to (n_total, N) if needed, or assume N=1
                        # For safety, let controller handle reshaping if we pass flat slice
                        local_demand = global_demand[indices] # This is 1D slice
                        # Reshape for controller [n_local, 1] -> broadcast to N
                        local_demand = local_demand.reshape(-1, 1) 
                    else:
                        local_demand = global_demand[indices, :]

                    # 2. Get Incidence Matrix
                    inc_matrix = tls_matrices.get(tls_id, np.zeros((len(controller.lane_ids), 4)))
                    
                    # 3. Optimize
                    splits = controller.optimize(state, local_demand, lane_capacities, inc_matrix)
                    
                    # 4. Apply
                    logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
                    phases = logic.phases
                    
                    # Update durations of Green phases
                    # Assume pattern G-y-G-y...
                    g_idx = 0
                    for p in range(len(phases)):
                        if 'G' in phases[p].state or 'g' in phases[p].state:
                            if g_idx < len(splits):
                                phases[p].duration = splits[g_idx]
                                g_idx += 1
                                
                    logic.phases = phases
                    traci.trafficlight.setCompleteRedYellowGreenDefinition(tls_id, logic)
                    
                    if splits:
                        total_green += splits[0]
                        count += 1
                
                avg_split = total_green / max(1, count)
                if step % 60 == 0:
                    logger.info(f"Step {step}: Cycle Optimized. Avg Main Green: {avg_split:.1f}s")

            queues = list(state.values())
            recorder.record([step, client.get_time(), sum(queues)/len(queues) if queues else 0, max(queues) if queues else 0, avg_split])
            step += 1

    finally:
        if 'recorder' in locals(): recorder.close()
        client.close()

if __name__ == "__main__":
    main()