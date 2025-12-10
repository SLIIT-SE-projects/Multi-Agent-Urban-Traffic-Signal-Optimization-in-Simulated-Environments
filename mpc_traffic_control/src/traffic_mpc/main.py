"""
Main Application Entry Point.
<<<<<<< Updated upstream
<<<<<<< Updated upstream
Orchestrates SUMO, Estimation, MPC Control Loop, and Telemetry.
=======
Phase Split Optimization + Anti-Spillback Capacity Constraints.
>>>>>>> Stashed changes
=======
Phase Split Optimization + Anti-Spillback Capacity Constraints.
>>>>>>> Stashed changes
"""
import logging
import hydra
import traci 
from omegaconf import DictConfig, OmegaConf
from traffic_mpc.config.settings import AppConfig
from traffic_mpc.interface.sumo_client import SumoClient
from traffic_mpc.core.estimation import StateEstimator
from traffic_mpc.core.controller import MPCController
<<<<<<< Updated upstream
<<<<<<< Updated upstream
=======
=======
>>>>>>> Stashed changes
from traffic_mpc.core.prediction import DemandPredictor 
>>>>>>> Stashed changes
from traffic_mpc.utils.logging import setup_logging
from traffic_mpc.utils.telemetry import TelemetryRecorder # <--- NEW IMPORT

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
<<<<<<< Updated upstream
<<<<<<< Updated upstream
        logger.info(f"Found Intersections: {tls_ids}")

        # 4. Initialize Components
        estimator = StateEstimator(link_ids=active_lanes)
        controller = MPCController(
            mpc_config=app_config.mpc,
            opt_config=app_config.optimization,
            lane_ids=active_lanes,
            phases=[]
        )

        # --- NEW: Setup Telemetry ---
        recorder = TelemetryRecorder(
            output_dir=app_config.logging.log_dir,
            filename="simulation_data.csv",
            headers=["step", "time", "avg_queue", "max_queue", "control_u"]
        )

        # 5. Main Loop
=======
        estimator = StateEstimator(link_ids=all_lanes)
        predictor = DemandPredictor(app_config.mpc, all_lanes, "data/model.pth")
        
        controllers = {}
        for tls_id in tls_ids:
            links = traci.trafficlight.getControlledLinks(tls_id)
            local_lanes = sorted(list(set([l[0][0] for l in links if l])))
            if local_lanes:
                controllers[tls_id] = MPCController(app_config.mpc, app_config.optimization, local_lanes, [])

=======
        estimator = StateEstimator(link_ids=all_lanes)
        predictor = DemandPredictor(app_config.mpc, all_lanes, "data/model.pth")
        
        controllers = {}
        for tls_id in tls_ids:
            links = traci.trafficlight.getControlledLinks(tls_id)
            local_lanes = sorted(list(set([l[0][0] for l in links if l])))
            if local_lanes:
                controllers[tls_id] = MPCController(app_config.mpc, app_config.optimization, local_lanes, [])

>>>>>>> Stashed changes
        recorder = TelemetryRecorder(app_config.logging.log_dir, "simulation_data.csv", 
                                   ["step", "time", "avg_queue", "max_queue", "avg_split"])

        # SLOW INTERVAL: Plan every 60s
        control_interval = 60 
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        step = 0
        max_steps = 3600

        while step < max_steps:
            client.step()
            
            raw_data = client.get_detector_data()
            state = estimator.update(raw_data)
            predictor.update_history({k.replace("e2_", ""): v for k, v in raw_data.items()})
            
<<<<<<< Updated upstream
<<<<<<< Updated upstream
            current_u = 0.0 # Default for plotting
            
            # Optimize (Every 5 seconds)
            if step % control_interval == 0:
                demand_matrix = np.zeros((len(active_lanes), app_config.mpc.prediction_horizon))
=======
=======
>>>>>>> Stashed changes
            avg_split = 0.0
            
            if do_control and (step % control_interval == 0):
                demand = predictor.predict()
                total_green = 0
                count = 0
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
                
                for tls_id, controller in controllers.items():
                    # Pass Capacities to Solver
                    # This prevents the "Snake Game" logic where we push cars into full lanes
                    splits = controller.optimize(state, demand, lane_capacities)
                    
<<<<<<< Updated upstream
<<<<<<< Updated upstream
                    for tls_id in tls_ids:
                        current_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                        is_green = ('G' in current_state or 'g' in current_state)
                        is_yellow = ('y' in current_state or 'Y' in current_state)
                        
                        if is_green and not is_yellow:
                            client.set_phase_duration(tls_id, extension)
                            
                    current_max_q = max(state.values()) if state else 0
                    logger.info(f"Step {step}: Queue={current_max_q:.1f} | MPC u={u_opt:.2f} -> Extending Green")
=======
=======
>>>>>>> Stashed changes
                    logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
                    phases = logic.phases
                    
                    # Apply Phase Splits
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
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

            queues = list(state.values())
            recorder.record([step, client.get_time(), sum(queues)/len(queues) if queues else 0, max(queues) if queues else 0, avg_split])
            step += 1

    finally:
        if 'recorder' in locals(): recorder.close()
        client.close()

if __name__ == "__main__":
    main()