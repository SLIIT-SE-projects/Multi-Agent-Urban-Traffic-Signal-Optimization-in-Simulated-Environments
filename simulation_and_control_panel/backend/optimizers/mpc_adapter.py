
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
        self.last_decisions = {} # tls_id -> { max_queue, green_times, lstm_mode }
        
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
                links = traci.trafficlight.getControlledLinks(tls_id)

                # ── Identify green-only phases ───────────────────────────────
                # A green phase = any phase that has at least one 'g' or 'G' and
                # no 'y'/'Y' in the state string (yellow indicator).
                # We plan durations ONLY for green phases — yellow durations are
                # handled by SUMO's built-in minimum yellow times, not by MPC.
                green_phase_sumo_indices = [
                    i for i, p in enumerate(phases)
                    if 'g' in p.state.lower() and 'y' not in p.state.lower()
                ]
                num_green_phases = len(green_phase_sumo_indices)

                if num_green_phases == 0:
                    print(f"⚠️ MPC Warning: No green phases found for {tls_id} — skipping.")
                    continue

                # Reverse map: SUMO phase index → green phase rank (0, 1, 2, …)
                sumo_to_rank = {sumo_idx: rank for rank, sumo_idx in enumerate(green_phase_sumo_indices)}

                lane_ids = []
                lane_phase_indices = []   # stores GREEN-PHASE RANK (not SUMO phase index)
                seen_lanes = set()

                for link_idx, connection_list in enumerate(links):
                    if not connection_list:
                        continue
                    for (lane_id, valid, row) in connection_list:
                        if lane_id in seen_lanes:
                            continue
                        # Find which SUMO phase lights this link green
                        my_sumo_green_phase = -1
                        for p_idx, p in enumerate(phases):
                            state = p.state
                            if link_idx < len(state):
                                char = state[link_idx].lower()
                                if char == 'g':
                                    my_sumo_green_phase = p_idx
                                    break

                        # Map to green-phase rank; skip if not in any green phase
                        if my_sumo_green_phase != -1 and my_sumo_green_phase in sumo_to_rank:
                            lane_ids.append(lane_id)
                            lane_phase_indices.append(sumo_to_rank[my_sumo_green_phase])
                            seen_lanes.add(lane_id)

                if not lane_ids:
                    print(f"⚠️ MPC Warning: No valid controlled lanes found for {tls_id}")
                    continue

                # 3. Create Controller — num_phases = green phases only
                try:
                    controller = MPCController(
                        mpc_config=self.mpc_cfg,
                        opt_config=self.opt_cfg,
                        lane_ids=lane_ids,
                        num_phases=num_green_phases,
                        lane_phase_indices=lane_phase_indices
                    )
                    self.controllers[tls_id] = {
                        "model": controller,
                        "green_indices": green_phase_sumo_indices,   # SUMO phase indices (for execution)
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
            
            # 2. Path to Model — auto-select by scenario name
            data_dir = os.path.abspath(os.path.join(mpc_service_path, "../data"))

            # Derive scenario name from the net file path (e.g. katunayake.net.xml → katunayake)
            scenario_name = "grid3x3"  # default
            if self.net_path:
                base = os.path.basename(self.net_path)          # katunayake.net.xml
                scenario_name = base.replace(".net.xml", "")    # katunayake

            # Map scenario → model/lane_ids filenames
            if scenario_name == "grid3x3":
                model_filename    = "model.pth"
                lane_ids_filename = "lane_ids.json"
            else:
                model_filename    = f"model_{scenario_name}.pth"
                lane_ids_filename = f"lane_ids_{scenario_name}.json"

            model_path     = os.path.join(data_dir, model_filename)
            lane_ids_path  = os.path.join(data_dir, lane_ids_filename)

            import json
            if os.path.exists(lane_ids_path):
                with open(lane_ids_path, "r") as f:
                    self.all_lanes_ordered = json.load(f)
            else:
                self.all_lanes_ordered = sorted(list(all_lanes_set))

            print(f"🔮 Initializing Demand Predictor for {len(self.all_lanes_ordered)} lanes...")
            print(f"   Scenario : {scenario_name}")
            print(f"   Model Path: {model_path}")
            if not os.path.exists(model_path):
                print(f"   ⚠️  Model file not found — running in Heuristic mode until trained.")

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

            # ── State Machine ───────────────────────────────────────────────
            # Fix A: NO queue-triggered mid-cycle reoptimization.
            # Previously Fix 5 discarded the plan on every poll once queues ≥5,
            # causing phase starvation: the signal never left phase 0 because it
            # kept restarting from scratch every 15 steps.
            # Correct behaviour: execute the plan to completion, THEN re-optimize.

            # 1. Do we have an active plan?
            if plan:
                elapsed = current_step - plan["start_time"]
                # Fix: Total cycle duration must include yellow lost time.
                # Previously, plan["durations"] only summed to available_green (e.g. 27s),
                # so the 45s cycle was expiring at 27s, chopping off the last phases!
                total_yellow_time = self.mpc_cfg.yellow_time * len(data["green_indices"])
                cycle_duration = sum(plan["durations"]) + total_yellow_time

                if elapsed >= cycle_duration:
                    # Plan finished → Re-optimize
                    plan = None
                else:
                    # Fix C: Only emit an action when the plan says it is time
                    # to switch to the NEXT phase.  Emitting on every 15-step
                    # poll was resetting SUMO's internal phase timer even when
                    # no switch was needed, violating minimum green times.
                    target_phase = self._get_phase_from_plan(plan, elapsed)
                    try:
                        current_sumo_phase_idx = traci.trafficlight.getPhase(tls_id)
                        logics = traci.trafficlight.getAllProgramLogics(tls_id)
                        if logics:
                            all_phases = logics[0].phases
                            green_indices = [
                                i for i, p in enumerate(all_phases)
                                if 'g' in p.state.lower() and 'y' not in p.state.lower()
                            ]
                            # Map plan phase_index → SUMO green phase index
                            if target_phase < len(green_indices):
                                sumo_target = green_indices[target_phase]
                            else:
                                sumo_target = green_indices[-1]

                            # Fix C: Only add to actions dict if SUMO currently
                            # wants a different green phase (triggers a switch).
                            if sumo_target != current_sumo_phase_idx:
                                actions[tls_id] = target_phase
                            # else: do nothing — SUMO is already on the right phase
                    except Exception:
                        # Safety fallback: emit action regardless
                        actions[tls_id] = target_phase

            # 2. If no plan (or just expired), Re-optimize
            if not plan:
                # ── Read queue lengths directly from TraCI ──────────────────
                queues = {}
                for lid in model.lane_ids:
                    try:
                        queues[lid] = traci.lane.getLastStepHaltingNumber(lid)
                    except Exception:
                        queues[lid] = 0

                # ── Build real [n_lanes, N] demand matrix from LSTM ──────────
                local_demand = np.zeros((model.n_lanes, model.N))
                for i, lid in enumerate(model.lane_ids):
                    if lid in global_demand_map:
                        full_pred = global_demand_map[lid]
                        # FIX: full_pred is in [0, 1] representing Halting/20 (queue).
                        # MPC treats demand as 'arrivals per step'.
                        # A full queue of 20 shouldn't mean 20 cars arrive per second (72000 veh/hr).
                        # We scale it to a realistic maximum arrival rate, e.g. 0.2 cars/second
                        # based on how congested the lane currently is.
                        scaled_arrivals = np.clip(full_pred[:model.N] * 0.20, 0.01, 0.40)
                        local_demand[i, :] = scaled_arrivals
                    else:
                        local_demand[i, :] = 0.10  # moderate fallback arrivals

                # ── Per-lane saturation flow ─────────────────────────────────
                sat_flows = {}
                for lid in model.lane_ids:
                    try:
                        ll = lid.lower()
                        if any(t in ll for t in ["left", "_l_", "turn", "lt"]):
                            sat_flows[lid] = 0.35
                        elif any(t in ll for t in ["right", "_r_", "rt"]):
                            sat_flows[lid] = 0.40
                        else:
                            sat_flows[lid] = 0.50
                    except Exception:
                        sat_flows[lid] = 0.50

                try:
                    green_times = model.optimize(
                        queues,
                        demand=local_demand,
                        capacities={},
                        sat_flows=sat_flows,
                    )
                except Exception as e:
                    print(f"MPC Optimization failed for {tls_id}: {e}")
                    available = model.CycleTime - model.cfg.yellow_time * model.Phases
                    green_times = [available / model.Phases] * model.Phases

                new_plan = {
                    "start_time": current_step,
                    "durations": list(green_times),
                    "phases": list(range(len(green_times)))
                }
                self.cycle_plans[tls_id] = new_plan

                # Diagnostics — only printed on reoptimization
                max_q = max(queues.values()) if queues else 0
                gt_str = ", ".join(f"{g:.1f}s" for g in green_times)
                print(f"🚦 MPC[{tls_id}] Step:{int(current_step)} MaxQ:{max_q}veh → [{gt_str}]")

                # Store decision for dashboard Internals tab
                lstm_mode = "neural_net" if (
                    self.predictor and self.predictor.model_loaded
                    and len(self.predictor.history_buffer) >= self.predictor.history_steps
                ) else "heuristic"
                self.last_decisions[tls_id] = {
                    "max_queue": int(max_q),
                    "green_times": [round(g, 1) for g in green_times],
                    "lstm_mode": lstm_mode,
                }

                # Fix C: Start phase 0 of the new plan immediately
                # (first phase always needs an explicit switch)
                actions[tls_id] = 0

        return actions


    def _get_phase_from_plan(self, plan, elapsed):
        cumulative = 0
        yellow_duration = self.mpc_cfg.yellow_time
        for i, duration in enumerate(plan["durations"]):
            # Each phase's command is held for (GreenTime + YellowTime)
            # This ensures SUMO gets exactly GreenTime seconds of actual green
            # since the first 'yellow_duration' seconds will be spent in transition.
            cumulative += duration + yellow_duration
            if elapsed < cumulative:
                return plan["phases"][i]
        return plan["phases"][-1]

    def get_internals(self):
        """Return last optimizer decisions + config for the dashboard Internals tab."""
        intersections = []
        for tls_id, dec in self.last_decisions.items():
            intersections.append({
                "id": tls_id,
                "max_queue": dec["max_queue"],
                "green_times": dec["green_times"],
                "lstm_mode": dec["lstm_mode"],
            })
        # Sort by intersection id
        intersections.sort(key=lambda x: x["id"])

        # Derive config from first controller if available
        cfg = {}
        if self.controllers:
            first = next(iter(self.controllers.values()))["model"]
            cfg = {
                "cycle_time": getattr(first, 'CycleTime', 45),
                "min_green": getattr(first.cfg, 'min_green_time', 5),
                "max_green": getattr(first.cfg, 'max_green_time', 60),
                "horizon": getattr(first, 'N', 20),
                "control_horizon": getattr(first, 'Nc', 5),
                "w_queue": getattr(self.opt_cfg, 'weight_queue', 5.0),
                "w_switch": getattr(self.opt_cfg, 'weight_switch', 2.0),
            }

        overall_lstm = "neural_net"
        if self.predictor and not self.predictor.model_loaded:
            overall_lstm = "heuristic"

        return {
            "lstm_mode": overall_lstm,
            "n_lanes": len(self.all_lanes_ordered),
            "n_intersections": len(self.controllers),
            "intersections": intersections,
            "config": cfg,
        }

    def reset(self):
        self.controllers = {}
        self.cycle_plans = {}
        self.last_decisions = {}
