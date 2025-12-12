"""
Main Application Entry Point.
Phase Split Optimization + Anti-Spillback Capacity Constraints.
Orchestrates SUMO, Estimation, MPC Control Loop, and Telemetry.
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
    logger.info("--- Starting MPC (Anti-Gridlock Mode) ---")
    
    do_control = cfg.get("control_enabled", True)
    
    client = SumoClient(app_config.sumo)
    client.start()

    try:
        client.step()
        detectors = client.get_detector_data()
        # Clean lane IDs by removing 'e2_' prefix
        all_lanes = sorted(list(set([d.replace("e2_", "") for d in detectors.keys()])))
        
        # --- MEASURE CAPACITIES ---
        # Calculate max vehicles per lane based on length
        lane_capacities = {}
        for lid in all_lanes:
            try:
                length = traci.lane.getLength(lid)
                # Assume 7.5m per vehicle (jam distance)
                capacity = length / 7.5
                lane_capacities[lid] = capacity
            except:
                lane_capacities[lid] = 40.0 # Fallback
                
        logger.info(f"Measured capacities for {len(lane_capacities)} lanes.")

        tls_ids = traci.trafficlight.getIDList()
        
        # Initialize Components
        estimator = StateEstimator(link_ids=all_lanes)
        predictor = DemandPredictor(app_config.mpc, all_lanes, "data/model.pth")
        
        controllers = {}
        for tls_id in tls_ids:
            links = traci.trafficlight.getControlledLinks(tls_id)
            local_lanes = sorted(list(set([l[0][0] for l in links if l])))
            if local_lanes:
                controllers[tls_id] = MPCController(app_config.mpc, app_config.optimization, local_lanes, [])

        # Setup Telemetry - Saves to CSV for the Dashboard
        recorder = TelemetryRecorder(
            app_config.logging.log_dir, 
            "simulation_data.csv", 
            ["step", "time", "avg_queue", "max_queue", "avg_split"]
        )

        # CONTROL LOOP CONFIG
        control_interval = 60 
        step = 0
        max_steps = 3600

        while step < max_steps:
            client.step()
            
            raw_data = client.get_detector_data()
            state = estimator.update(raw_data)
            
            # Update predictor with clean IDs
            predictor.update_history({k.replace("e2_", ""): v for k, v in raw_data.items()})
            
            avg_split = 0.0
            
            if do_control and (step % control_interval == 0):
                demand = predictor.predict()
                total_green = 0
                count = 0
                
                for tls_id, controller in controllers.items():
                    # Pass Capacities to Solver (Anti-Spillback Logic)
                    splits = controller.optimize(state, demand, lane_capacities)
                    
                    logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
                    phases = logic.phases
                    
                    # Apply Phase Splits (Assuming Standard 4-Phase Cycle)
                    if len(phases) >= 4:
                        phases[0].duration = splits[0]
                        phases[2].duration = splits[1]
                        logic.phases = phases
                        traci.trafficlight.setCompleteRedYellowGreenDefinition(tls_id, logic)
                    
                    total_green += splits[0]
                    count += 1
                
                avg_split = total_green / max(1, count)
                if step % 60 == 0:
                    logger.info(f"Step {step}: Planning Cycle. Avg Main Green: {avg_split:.1f}s")

            queues = list(state.values())
            
            # Record Data for Dashboard
            avg_q = sum(queues)/len(queues) if queues else 0
            max_q = max(queues) if queues else 0
            
            recorder.record([step, client.get_time(), avg_q, max_q, avg_split])
            step += 1

    finally:
        if 'recorder' in locals(): recorder.close()
        client.close()

if __name__ == "__main__":
    main()