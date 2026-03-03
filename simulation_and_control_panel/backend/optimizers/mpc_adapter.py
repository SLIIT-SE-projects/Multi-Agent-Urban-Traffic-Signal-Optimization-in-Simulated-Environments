
import os
import sys
import traci
import numpy as np

# --- PATH ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# Root of repo
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
mpc_service_path = os.path.join(project_root, "services/mpc_traffic_control/src")

if mpc_service_path not in sys.path:
    # print(f"🔌 MPC Adapter: Adding path {mpc_service_path}")
    sys.path.append(mpc_service_path)

try:
    from traffic_mpc.core.controller import MPCController
    from traffic_mpc.core.prediction import DemandPredictor
    from traffic_mpc.config.settings import MPCConfig, OptimizationConfig
except ImportError as e:
    print(f"❌ MPC Adapter Error: Could not import traffic_mpc. Ensure services/mpc_traffic_control is usable. {e}")
    raise e

class MPCTrafficOptimizer:
    def __init__(self, net_path=None):
        """
        Adapts the MPC Controller to the Simulation Control Panel interface.
        Manages one MPCController per Traffic Light.
        """
        print(f"🔌 Initializing MPC Optimizer...")
        self.net_path = net_path
        
        # Determine all traffic lights and their configs
        self.controllers = {} # tls_id -> MPCController
        self.cycle_plans = {} # tls_id -> { "phases": [durations], "start_step": int }
        
        # Default configs
        self.mpc_cfg = MPCConfig(
            prediction_horizon=20,
            control_horizon=5,
            min_green_time=5,
            max_green_time=60
        )
        self.opt_cfg = OptimizationConfig()
        
        # New: Global Predictor
        self.predictor = None
        self.all_lanes_ordered = []
        
        self._initialize_controllers()

    def _initialize_controllers(self):
        """
        Discovers traffic lights and sets up MPC for each.
        """
        try:
            tls_ids = traci.trafficlight.getIDList()
            count = 0 
            for tls_id in tls_ids:
                # 1. Get Logic (Phases)
                logics = traci.trafficlight.getAllProgramLogics(tls_id)
                if not logics:
                    continue
                logic = logics[0]
                phases = logic.phases
                num_phases = len(phases)
                
                # 2. Get Lanes & Mapping
                # controlled_links: list of list of (lane_id, valid, right_of_way)
                # index corresponds to link index in phase state string
                links = traci.trafficlight.getControlledLinks(tls_id)
                
                lane_ids = []
                lane_phase_indices = []
                
                # We need to map each lane to the phase index that gives it valid Green.
                # Heuristic: Find first phase where this lane has 'G' or 'g'
                
                seen_lanes = set()
                
                # links is a list of connections. Some lanes appear multiple times (left, straight, right).
                # We only need to control each unique incoming lane once.
                for link_idx, connection_list in enumerate(links):
                    if not connection_list: continue
                    
                    # Usually just one connection per link index, but can be multiple
                    for (lane_id, valid, row) in connection_list:
                        if lane_id in seen_lanes:
                            continue
                        
                        # Find which phase lights this link green
                        my_green_phase = -1
                        for p_idx, p in enumerate(phases):
                            state = p.state
                            if link_idx < len(state):
                                char = state[link_idx].lower()
                                if char == 'g':
                                    my_green_phase = p_idx
                                    break
                        
                        # If meaningful green phase found (and not just always red)
                        if my_green_phase != -1:
                            lane_ids.append(lane_id)
                            lane_phase_indices.append(my_green_phase)
                            seen_lanes.add(lane_id)

                if not lane_ids:
                    print(f"⚠️ MPC Warning: No valid controlled lanes found for {tls_id}")
                    continue

                # 3. Create Controller
                try:
                    controller = MPCController(
                        mpc_config=self.mpc_cfg,
                        opt_config=self.opt_cfg,
                        lane_ids=lane_ids,
                        num_phases=num_phases,
                        lane_phase_indices=lane_phase_indices
                    )
                    self.controllers[tls_id] = {
                        "model": controller,
                        "green_indices": sorted(list(set(lane_phase_indices))), # Phases that are actually greens
                        "all_phases": phases
                    }
                    self.cycle_plans[tls_id] = None
                    count += 1
                except Exception as e:
                    print(f"❌ Failed to init MPC for {tls_id}: {e}")
                    
            print(f"✅ MPC Initialized for {count} intersections.")
            
            # --- NEW: Init Predictor ---
            # 1. Collect all lanes from all controllers
            all_lanes_set = set()
            for tls_id, data in self.controllers.items():
                # data["model"].lane_ids contains the lanes controlled by this TLS
                for lid in data["model"].lane_ids:
                    all_lanes_set.add(lid)
            
            self.all_lanes_ordered = sorted(list(all_lanes_set))
            
            # 2. Path to Model
            data_dir = os.path.abspath(os.path.join(mpc_service_path, "../data"))
            model_path = os.path.join(data_dir, "model.pth")
            lane_ids_path = os.path.join(data_dir, "lane_ids.json")
            
            import json
            if os.path.exists(lane_ids_path):
                with open(lane_ids_path, "r") as f:
                    self.all_lanes_ordered = json.load(f)
            else:
                self.all_lanes_ordered = sorted(list(all_lanes_set))
            
            print(f"🔮 Initializing Demand Predictor for {len(self.all_lanes_ordered)} lanes...")
            print(f"   Model Path: {model_path}")
            
            self.predictor = DemandPredictor(self.mpc_cfg, self.all_lanes_ordered, model_path)
            
        except Exception as e:
            print(f"❌ Error managing TraCI during init: {e}")
            # If called before simulation start, this fails. 
            pass

    def predict(self, snapshot):
        """
        main entry point called by SimulationController every step (or interval).
        """
        actions = {}
        current_step = traci.simulation.getTime() # Use time or step
        
        # --- NEW: Update Prediction (Once per Step) ---
        # 1. Gather all current flows
        # snapshot['lanes'][lid]['induction_loop_flow']... wait, need to check snapshot structure
        # Assuming snapshot has basic lane data. If flow not present, we can't update correctly.
        # But 'DemandPredictor' needs flow.
        # We'll try to extract what we can.
        
        # --- FIXED: use the same metric the LSTM was trained on ---
        # Training used: E2 detector halting vehicle counts.
        # `traci.lane.getLastStepHaltingNumber(lane_id)` == the number of stopped
        # vehicles on a lane at this step, which is what the E2 detectors measured.
        # We normalise by an assumed lane capacity of 20 vehicles so inputs stay
        # in a reasonable [0, ~1] range consistent with the training distribution.
        LANE_CAPACITY = 20.0
        current_flows = {}
        for lid in self.all_lanes_ordered:
            try:
                halting = traci.lane.getLastStepHaltingNumber(lid)
                current_flows[lid] = halting / LANE_CAPACITY   # normalised queue occupancy
            except Exception:
                current_flows[lid] = 0.0   # lane may not exist in this simulation
            
        if self.predictor:
            self.predictor.update_history(current_flows)
            all_predicted_demand = self.predictor.predict() # shape [n_all, N]
            
            # Create a lookup map: LaneID -> [Forecast Array]
            global_demand_map = {}
            for idx, lid in enumerate(self.all_lanes_ordered):
                 global_demand_map[lid] = all_predicted_demand[idx]
        else:
            global_demand_map = {}

        for tls_id, data in self.controllers.items():
            model = data["model"]
            plan = self.cycle_plans.get(tls_id)
            
            # --- State Machine ---
            
            # 1. Do we have an active plan?
            if plan:
                # Check if plan is done
                # Simple logic for now: We don't really track detailed timing here because 
                # SimulationController manages yellow/transitions aggressively.
                # Instead, we just check if we need to Generate a NEW plan (Cycle finished).
                # BUT, SimulationController expects "Target Phase Index".
                
                # REFACTOR: The SimulationController calls us every X steps.
                # If we return a phase, it tries to switch to it.
                
                # Better Logic:
                # We calculate Green Splits: [G1, G2, G3, G4]
                # We determine "Cycle Start Time".
                # relative_time = now - cycle_start
                # We see which bin relative_time falls into.
                
                elapsed = current_step - plan["start_time"]
                cycle_duration = sum(plan["durations"])
                
                if elapsed >= cycle_duration:
                    # Plan finished -> Re-optimize
                    plan = None 
                else:
                    # Execute Plan
                    target_phase = self._get_phase_from_plan(plan, elapsed)
                    actions[tls_id] = target_phase
            
            # 2. If no plan (or just expired), Optimize
            if not plan:
                # Gather Queues (and Flow for Prediction)
                queues = {}
                current_flows = {} # For predictor history
                lanes_data = snapshot.get("lanes", {})
                
                # Update Predictor History (Global) helps if we do it once per step, 
                # but doing it here locally is fine if we are careful.
                # Actually, predict() is called once per sim step (presumably).
                # So we should update predictor ONCE at top of function.
                pass 

                for lid in model.lane_ids:
                    # Default if missing
                    # Note: Queue length is in veh count
                    q = 0
                    if lid in lanes_data:
                        q = lanes_data[lid].get("queue_length", 0)
                    queues[lid] = q
                
                # Optimize
                # Get Specific Demand for this intersection's lanes
                # demand matrix shape: [n_local_lanes, N]
                local_demand = np.zeros((model.n_lanes, model.N))
                
                try:
                    # Map global demand to local lanes
                    for i, lid in enumerate(model.lane_ids):
                        if lid in global_demand_map:
                            # Slice prediction to match Control Horizon (model.N)
                            # Prediction might be 20 steps, but Optimization only cares about next 5.
                            full_pred = global_demand_map[lid]
                            local_demand[i, :] = full_pred[:model.N]
                        else:
                             # Fallback if lane not in predictor (shouldn't happen)
                            local_demand[i, :] = 0.5 # moderate demand assumption
                            
                    green_times = model.optimize(queues, demand=local_demand, capacities={})
                except Exception as e:
                    print(f"MPC Optimization failed for {tls_id}: {e}")
                    green_times = [15.0] * model.Phases
                
                # Create Plan
                # Note: green_times is length of Phases.
                # We assume strict ordering 0, 1, 2... for now.
                # IMPORTANT: MPC optimizes Green times. It assumes fixed yellow times in between.
                # The model constraints accounted for Lost Time.
                
                # Logic: Phase 0 (Green) -> Phase 1 (Yellow) -> Phase 2 (Green)... 
                # Wait, generic SUMO phases are messy (G, y, r, G, y...).
                # Simplified Assumption: The MPC 'Phases' correspond to the indices we identified as 'Greens'.
                # But MPC logic assumes continuous cycle.
                
                # Fallback: Just return the index of the phase with highest recommended time? 
                # No, that defeats the purpose of splits.
                
                # Let's map strict implementation:
                # The generic MPC returns [g0, g1, g2, g3] where indices match `lane_phase_indices`.
                
                # We construct a time-schedule.
                actual_durations = []
                for idx, g in enumerate(green_times):
                    actual_durations.append(g)
                    
                self.cycle_plans[tls_id] = {
                    "start_time": current_step,
                    "durations": actual_durations, # List of floats
                    "phases": list(range(len(green_times))) # Simple 0,1,2,3 assumption
                }
                
                # Execute immediate first step
                actions[tls_id] = 0 # Start with Phase 0
                
        return actions

    def _get_phase_from_plan(self, plan, elapsed):
        cumulative = 0
        for i, duration in enumerate(plan["durations"]):
            cumulative += duration
            if elapsed < cumulative:
                return plan["phases"][i]
        return plan["phases"][-1]

    def reset(self):
        self.controllers = {}
        self.cycle_plans = {}
