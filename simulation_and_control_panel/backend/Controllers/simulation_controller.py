import os
import sys
import traci
import threading
import time
import xml.etree.ElementTree as ET
from optimizers.gnn_adapter import GNNTrafficOptimizer
from optimizers.mpc_adapter import MPCTrafficOptimizer

# Add SUMO tools to path
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please set SUMO_HOME environment variable")


class SimulationController:
    def __init__(self, config_file, socketio_instance=None, use_gui=True, step_delay=0.1, green_wave_controller=None):
        self.socketio = socketio_instance
        self.config_file = config_file
        self.use_gui = use_gui
        self.default_step_delay = step_delay
        self.green_wave_controller = green_wave_controller
        self.is_running = False
        self.is_paused = False
        self.current_step = 0
        self.auto_stepping = False
        self.auto_step_thread = None
        self.step_lock = threading.Lock()  # Lock for thread-safe stepping
        self.stopping = False  # True while background teardown is in progress
        self.optimizer = None
        self.optimization_enabled = False
        self.action_interval = 15
        self.last_action_step = 0
        self.green_phases = {}
        self.pending_switches = {}
        self.yellow_timers = {}
        self.YELLOW_DURATION = 3
        # Dynamic flow-rate injection state
        self.flow_rates: dict = {}          # route_id -> vehicles_per_hour
        self._flow_last_injections: dict = {}  # route_id -> last sim-time (s)
        self._flow_vehicle_counter: int = 0

    def _get_net_file_from_config(self):
        """
        Parses the current .sumo.cfg to find the associated .net.xml file.
        This ensures the AI uses the EXACT same map as the simulation.
        """
        try:
            tree = ET.parse(self.config_file)
            root = tree.getroot()
            
            # Look for <net-file value="..."/>
            net_file_entry = root.find(".//net-file")
            if net_file_entry is None or 'value' not in net_file_entry.attrib:
                raise ValueError("Could not find <net-file> in sumo config")
            
            relative_net_path = net_file_entry.attrib['value']
            
            # Resolve path relative to the config file location
            config_dir = os.path.dirname(self.config_file)
            net_file_path = os.path.normpath(os.path.join(config_dir, relative_net_path))
            
            if not os.path.exists(net_file_path):
                raise FileNotFoundError(f"Network file not found at: {net_file_path}")
                
            return net_file_path
            
        except Exception as e:
            print(f"❌ Error resolving network file: {e}")
            return None

    def get_network_topology(self):
        """
        Parses the SUMO network file to extract topology for visualization.
        Returns a dictionary with nodes (intersections, lanes) and edges (adjacency, flow, membership).
        """
        net_file = self._get_net_file_from_config()
        if not net_file:
            return {"error": "Network file not found"}

        try:
            tree = ET.parse(net_file)
            root = tree.getroot()

            intersections = []
            lanes = []
            edges = [] # Adjacency (Intersection -> Intersection)
            flow_edges = [] # Flow (Lane -> Lane)
            membership_edges = [] # Membership (Lane -> Intersection)

            # 1. Parse Intersections (Junctions)
            junctions = {}
            for junction in root.findall('junction'):
                j_id = junction.get('id')
                j_type = junction.get('type')
                
                if j_type == "internal": continue # Skip internal junctions

                try:
                    x = float(junction.get('x'))
                    y = float(junction.get('y'))
                    junctions[j_id] = {"x": x, "y": y}
                    intersections.append({
                        "id": j_id,
                        "x": x,
                        "y": y,
                        "type": j_type
                    })
                except:
                    continue

            # 2. Parse Edges (Roads) & Lanes
            # Map edge_id -> from_node, to_node
            edge_map = {} 
            
            for edge in root.findall('edge'):
                e_id = edge.get('id')
                e_from = edge.get('from')
                e_to = edge.get('to')
                e_func = edge.get('function')

                if e_func == "internal": continue
                if not e_from or not e_to: continue

                edge_map[e_id] = {"from": e_from, "to": e_to}

                # Add Adjacency Edge (Intersection -> Intersection)
                # We use a set later to remove duplicates if multiple edges connect same nodes
                edges.append({
                    "from": e_from,
                    "to": e_to,
                    "id": e_id
                })

                # Parse Lanes within this Edge
                for lane in edge.findall('lane'):
                    l_id = lane.get('id')
                    shape_str = lane.get('shape')
                    
                    # Calculate lane position (center of shape or start)
                    # Shape is "x1,y1 x2,y2 ..."
                    try:
                        coords = [tuple(map(float, p.split(','))) for p in shape_str.split()]
                        # Use midpoint for visualization
                        mid_idx = len(coords) // 2
                        lx, ly = coords[mid_idx]
                        
                        lanes.append({
                            "id": l_id,
                            "x": lx,
                            "y": ly,
                            "parent_edge": e_id
                        })

                        # Add Membership Edge (Lane -> Intersection (to_node))
                        # A lane "belongs" to the edge, which flows INTO 'to_node'
                        membership_edges.append({
                            "from": l_id,
                            "to": e_to
                        })

                    except:
                        continue

            # 3. Parse Connections (Lane -> Lane Flow)
            for conn in root.findall('connection'):
                from_lane = f"{conn.get('from')}_{conn.get('fromLane')}"
                to_lane = f"{conn.get('to')}_{conn.get('toLane')}"
                
                # Verify both lanes exist (sometimes internal lanes are referenced)
                # For simplicity, we just add the edge. The frontend can filter if needed.
                flow_edges.append({
                    "from": from_lane,
                    "to": to_lane
                })

            return {
                "intersections": intersections,
                "lanes": lanes,
                "adjacency": edges,
                "flow": flow_edges,
                "membership": membership_edges
            }

        except Exception as e:
            print(f"❌ Error parsing topology: {e}")
            return {"error": str(e)}

    def _apply_gnn_binary_actions(self, actions):
        """
        Applies GNN binary keep/switch actions.
        action=0: keep current phase (do nothing)
        action=1: advance to next green phase with yellow transition
        Matches apply_actions_unified() from training — must stay identical.
        """
        for tls_id, action_val in actions.items():
            try:
                if int(action_val) == 0:
                    continue  # KEEP: do nothing

                # SWITCH: advance to next green phase
                if tls_id in self.pending_switches:
                    continue  # Already transitioning

                current_phase = traci.trafficlight.getPhase(tls_id)
                next_green = self._get_next_green_phase(current_phase)

                if next_green == current_phase:
                    continue  # Already on target

                yellow_phase = self._get_yellow_phase(tls_id, current_phase)

                if yellow_phase == current_phase:
                    self.pending_switches[tls_id] = next_green
                    self.yellow_timers[tls_id] = 1
                else:
                    traci.trafficlight.setPhase(tls_id, yellow_phase)
                    self.pending_switches[tls_id] = next_green
                    self.yellow_timers[tls_id] = self.YELLOW_DURATION

            except Exception as e:
                print(f"Error applying GNN action to {tls_id}: {e}")

    def _get_next_green_phase(self, current_phase, total_phases=4):
        """
        Advances to next green phase, skipping yellow phases.
        Matches get_next_green_phase() from training exactly.
        """
        next_phase = (current_phase + 1) % total_phases
        if next_phase % 2 != 0:  # odd phases are yellow in your SUMO setup
            next_phase = (next_phase + 1) % total_phases
        return next_phase

    def load_optimizer(self, model_type="gnn"):
        """Load the AI model with the CURRENT simulation map"""
        print(f"🔌 Loading {model_type.upper()} Optimizer...")
        
        # 1. Dynamically find the map file
        current_net_file = self._get_net_file_from_config()
        
        if not current_net_file:
            print("❌ Cannot load Optimizer: Network file could not be determined from config.")
            return {"status": "error", "message": "Network file not found"}

        try:
            if model_type == "gnn":
                # 2. Inject the map file into the GNN Adapter
                self.optimizer = GNNTrafficOptimizer(
                    net_path=current_net_file
                )
                self.optimization_enabled = True
                print(f"✅ GNN Optimizer attached to: {os.path.basename(current_net_file)}")
                return {"status": "success", "message": "GNN Optimizer Loaded"}
            
            elif model_type == "mpc":
                # 3. Inject MPC Optimizer
                self.optimizer = MPCTrafficOptimizer(
                    net_path=current_net_file
                )
                self.optimization_enabled = True
                print(f"✅ MPC Optimizer attached to: {os.path.basename(current_net_file)}")
                return {"status": "success", "message": "MPC Optimizer Loaded"}
                
        except Exception as e:
            print(f"❌ Failed to load optimizer: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # CORE SIMULATION LOGIC (Refactored)
    # =========================================================================
    
    def _advance_simulation(self):
        """
        Central method to advance the simulation by one step.
        Handles: AI Inference -> Yellow Phase Management -> Traci Step
        """
        # 1. AI OPTIMIZATION HOOK
        if self.optimization_enabled and self.optimizer:
            if (self.current_step - self.last_action_step) >= self.action_interval:
                # print(f"🚦 AI Action Step: {self.current_step} | Calculating phases...")
                try:
                    snapshot = self._capture_snapshot_for_ai()
                    
                    # Calculate stats for logging
                    lanes_data = snapshot.get("lanes", {})
                    max_queue = 0
                    total_waiting = 0
                    total_speed = 0
                    valid_lanes = 0
                    
                    for lane_data in lanes_data.values():
                        q = lane_data.get("queue_length", 0)
                        w = lane_data.get("waiting_time", 0)
                        s = lane_data.get("avg_speed", 0)
                        
                        if q > max_queue: max_queue = q
                        total_waiting += w
                        total_speed += s
                        valid_lanes += 1
                        
                    avg_speed = (total_speed / valid_lanes) if valid_lanes > 0 else 0
                    
                    # Determine the name based on the class of the loaded optimizer
                    opt_name = "GNN" if "GNN" in self.optimizer.__class__.__name__ else "MPC"

                    print(f"🚦 {opt_name} Step: {self.current_step} | Max Queue: {max_queue} veh | Avg Speed: {avg_speed:.2f} m/s | Total Wait: {total_waiting:.1f} s")
                    
                    actions = self.optimizer.predict(snapshot)
                    if getattr(self.optimizer, 'is_binary_action', False):
                        self._apply_gnn_binary_actions(actions)
                    else:
                        self._apply_ai_actions(actions)
                    self.last_action_step = self.current_step
                except traci.exceptions.FatalTraCIError:
                    print("Simulation ended by SUMO.")
                    self.stop()
                    return
                except Exception as e:
                    print(f"⚠️ AI Prediction Error: {e}")

        # 2. YELLOW PHASE MANAGEMENT (Critical for Safety)
        completed_transitions = []
        for tls_id in list(self.yellow_timers.keys()):
            self.yellow_timers[tls_id] -= 1
            if self.yellow_timers[tls_id] <= 0:
                if tls_id in self.pending_switches:
                    final_phase = self.pending_switches[tls_id]
                    try:
                        traci.trafficlight.setPhase(tls_id, final_phase)
                    except:
                        pass
                    del self.pending_switches[tls_id]
                completed_transitions.append(tls_id)
        
        for tls_id in completed_transitions:
            del self.yellow_timers[tls_id]

        # 3. ADVANCE SUMO
        try:
            traci.simulationStep()
        except traci.exceptions.FatalTraCIError:
             print("Simulation ended by SUMO (FatalTraCIError).")
             self.stop()
             return

        self.current_step += 1

        # 3.5. DYNAMIC FLOW INJECTION
        self._inject_flow_vehicles()

        # 3.6. GREEN WAVE LOGIC
        if self.green_wave_controller:
            self.green_wave_controller.execute_step()

        # 4. DATA BROADCAST (Optimized)
        if self.socketio:
            # Run broadcast in a separate lightweight thread to prevent blocking the sim loop
            # Or just use the native emit which is async in 'threading' mode
            try:
                # Reuse snapshot logic efficiently
                # Only capture if we didn't capture it for AI above
                # (For simplicity, we capture again to ensure fresh data after the step)
                snapshot = self._capture_snapshot_for_ai()
                
                # Capture global metrics
                arrived_vehicles = traci.simulation.getArrivedNumber()
                
                self.socketio.emit('simulation_step', {
                    'step': self.current_step,
                    'lanes': snapshot['lanes'],
                    'intersections': snapshot['intersections'],
                    'global': {
                        'arrived_vehicles': arrived_vehicles
                    }
                })
            except Exception as e:
                print(f"Socket Emit Error: {e}")

    def start_auto_stepping(self, step_delay=None):
        """Start automatic stepping in background"""
        if not self.is_running:
            return {"status": "error", "message": "Simulation not running. Call /start first"}
        
        if self.is_paused:
            return {"status": "error", "message": "Simulation is paused. Resume the simulation first"}
        
        if self.auto_stepping:
            return {"status": "error", "message": "Auto-stepping already active"}
        
        # Use provided delay or default
        if step_delay is None:
            step_delay = self.default_step_delay
        
        self.auto_stepping = True

        def step_loop():
            while self.auto_stepping and self.is_running:
                if not self.is_paused:
                    try:
                        with self.step_lock:
                            self._advance_simulation()
                        time.sleep(step_delay)
                    except Exception as e:
                        print(f"Error in auto-stepping: {e}")
                        self.auto_stepping = False
                        break
                else:
                    time.sleep(0.1)

        self.auto_step_thread = threading.Thread(target=step_loop, daemon=True)
        self.auto_step_thread.start()

        return {"status": "success", "message": "Auto-stepping started", "step_delay": step_delay}
    
    def _capture_snapshot_for_ai(self):
        tls_ids = traci.trafficlight.getIDList()
        intersections = {}
        for tls in tls_ids:
            intersections[tls] = {
                "phase_index": traci.trafficlight.getPhase(tls),
                "time_to_switch": traci.trafficlight.getNextSwitch(tls) - traci.simulation.getTime()
            }
        
        lane_ids = traci.lane.getIDList()
        lanes = {}
        for lane in lane_ids:
            lanes[lane] = {
                "queue_length": traci.lane.getLastStepHaltingNumber(lane),
                "vehicle_count": traci.lane.getLastStepVehicleNumber(lane),
                "occupancy": traci.lane.getLastStepOccupancy(lane),
                # NOTE: SUMO returns the free-flow speed limit (not 0) when a
                # lane is empty.  Consumers must filter by vehicle_count > 0
                # before averaging this value.
                "avg_speed": traci.lane.getLastStepMeanSpeed(lane),
                "co2": traci.lane.getCO2Emission(lane),
                "waiting_time": traci.lane.getWaitingTime(lane)
            }
        return {"intersections": intersections, "lanes": lanes}

    def _get_yellow_phase(self, tls_id, current_phase):
        try:
            logics = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            phases = logics.phases
            num_phases = len(phases)
            next_p_idx = (current_phase + 1) % num_phases
            next_state = phases[next_p_idx].state.lower()
            if 'y' in next_state or 'u' in next_state:
                return next_p_idx
            return current_phase
        except:
            return current_phase

    def _apply_ai_actions(self, actions):
        for tls_id, action_idx in actions.items():
            try:
                # Initialize greens if unknown
                if tls_id not in self.green_phases:
                    logics = traci.trafficlight.getAllProgramLogics(tls_id)
                    if len(logics) > 0:
                        phases = logics[0].phases
                        greens = []
                        for i, p in enumerate(phases):
                            state = p.state.lower()
                            if ('g' in state) and ('y' not in state) and ('u' not in state):
                                greens.append(i)
                        self.green_phases[tls_id] = greens if greens else [0]
                    else:
                        self.green_phases[tls_id] = [0]

                valid_greens = self.green_phases[tls_id]
                action_idx = int(action_idx)
                if action_idx >= len(valid_greens):
                    action_idx = len(valid_greens) - 1
                
                target_phase = valid_greens[action_idx]
                current_phase = traci.trafficlight.getPhase(tls_id)
                
                if current_phase == target_phase: continue
                if tls_id in self.pending_switches:
                    self.pending_switches[tls_id] = target_phase
                    continue

                yellow_phase = self._get_yellow_phase(tls_id, current_phase)
                
                if yellow_phase == current_phase:
                    self.pending_switches[tls_id] = target_phase
                    self.yellow_timers[tls_id] = 1
                else:
                    traci.trafficlight.setPhase(tls_id, yellow_phase)
                    self.pending_switches[tls_id] = target_phase
                    self.yellow_timers[tls_id] = self.YELLOW_DURATION
            except Exception as e:
                print(f"Error applying action to {tls_id}: {e}")

    def stop_auto_stepping(self):
        """Stop automatic stepping"""
        if not self.auto_stepping:
            return {"status": "error", "message": "Auto-stepping not active"}
        
        self.auto_stepping = False
        if self.auto_step_thread:
            self.auto_step_thread.join(timeout=2)

        return {"status": "success", "message": "Auto-stepping stopped"}

    def pause_auto_stepping(self):
        """Pause auto-stepping (freeze simulation while keeping thread alive)"""
        if not self.auto_stepping:
            return {"status": "error", "message": "Auto-stepping not active"}
        
        self.is_paused = True
        return {"status": "success", "message": "Auto-stepping paused", "step": self.current_step}

    def resume_auto_stepping(self):
        """Resume auto-stepping"""
        if not self.auto_stepping:
            return {"status": "error", "message": "Auto-stepping not active"}
        
        if not self.is_paused:
            return {"status": "error", "message": "Auto-stepping not paused"}
        
        self.is_paused = False
        return {"status": "success", "message": "Auto-stepping resumed", "step": self.current_step}

    def start(self, suppress_demand: bool = False):
        """Start the simulation.

        Args:
            suppress_demand: When True, passes ``--scale 0`` to SUMO so that no
                pre-defined vehicles from the route/trip files are inserted.  Use
                this when you want vehicle flow to be driven exclusively by the
                dynamic flow-rate injection API.
        """
        if self.stopping:
            return {"status": "error", "message": "Simulation is still shutting down, please wait a moment"}

        if self.is_running:
            return {"status": "error", "message": "Simulation already running"}

        # Reset dynamic flow state so stale rates from a previous run don't
        # carry over into the new session.
        self.flow_rates.clear()
        self._flow_last_injections.clear()
        self._flow_vehicle_counter = 0

        # Choose SUMO binary based on use_gui setting
        sumo_binary = "sumo-gui" if self.use_gui else "sumo"
        sumo_cmd = [sumo_binary, "-c", self.config_file, "--start"]

        if suppress_demand:
            # Scale the built-in demand to zero — none of the vehicles defined
            # in the scenario's route/trip files will be inserted by SUMO.
            sumo_cmd += ["--scale", "0"]
            print("[FlowRate] Built-in demand suppressed (--scale 0). Only injected vehicles will run.")
        
        try:
            traci.start(sumo_cmd)
            self.is_running = True
            self.is_paused = False
            self.current_step = 0
            print(f"Simulation started with config: {self.config_file}")
            print(f"GUI mode: {self.use_gui}")
            
            return {
                "status": "success", 
                "message": "Simulation started", 
                "step": self.current_step,
                "auto_stepping": self.auto_stepping,
                "suppress_demand": suppress_demand,
            }
        except Exception as e:
            # traci.start() may have partially opened a connection/process before
            # failing (e.g. SUMO config error). Clean it up so the next Start call
            # doesn't stack another SUMO process on top.
            try:
                traci.close()
            except Exception:
                pass
            self.is_running = False
            self.stopping = False
            return {"status": "error", "message": str(e)}
    
    def step(self):
        """Execute one simulation step"""
        if not self.is_running:
            return {"status": "error", "message": "Simulation not running"}
        
        if self.auto_stepping:
            return {"status": "error", "message": "Cannot manually step when auto-stepping is active. Stop auto-stepping first."}
        
        if self.is_paused:
            return {"status": "error", "message": "Simulation is paused"}
            
        try:
            with self.step_lock:
                self._advance_simulation()
                # traci.simulationStep() # REMOVED DOUBLE STEP
                # self.current_step += 1 # REMOVED DOUBLE INCREMENT
            return {"status": "success", "message": "Step executed", "step": self.current_step}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        
    def _capture_snapshot_for_ai(self):
        """Helper to get data in the format GNN expects"""
        # Mirror the logic from GNN's sumo_manager.get_snapshot()
        tls_ids = traci.trafficlight.getIDList()
        intersections = {}
        for tls in tls_ids:
            intersections[tls] = {
                "phase_index": traci.trafficlight.getPhase(tls),
                "time_to_switch": traci.trafficlight.getNextSwitch(tls) - traci.simulation.getTime()
            }
            
        lane_ids = traci.lane.getIDList()
        lanes = {}
        for lane in lane_ids:
            lanes[lane] = {
                "queue_length": traci.lane.getLastStepHaltingNumber(lane),
                "occupancy": traci.lane.getLastStepOccupancy(lane),
                "avg_speed": traci.lane.getLastStepMeanSpeed(lane),
                "co2": traci.lane.getCO2Emission(lane),
                "waiting_time": traci.lane.getWaitingTime(lane)
            }
        return {"intersections": intersections, "lanes": lanes}

    def _apply_ai_actions(self, actions):
        for tls_id, action_idx in actions.items():
            try:
                # 1. Discover Valid Green Phases (Once per light)
                if tls_id not in self.green_phases:
                    logics = traci.trafficlight.getAllProgramLogics(tls_id)
                    if len(logics) > 0:
                        phases = logics[0].phases
                        greens = []
                        for i, p in enumerate(phases):
                            state = p.state.lower()
                            # STRICTER CHECK: Must have 'g' AND no 'y' (yellow) AND no 'u' (red-yellow)
                            if ('g' in state) and ('y' not in state) and ('u' not in state):
                                greens.append(i)
                        
                        if len(greens) == 0: greens = [0] 
                        self.green_phases[tls_id] = greens
                    else:
                        self.green_phases[tls_id] = [0]

                # Map AI Action to Valid Green
                valid_greens = self.green_phases[tls_id]
                action_idx = int(action_idx)
                if action_idx >= len(valid_greens):
                    action_idx = len(valid_greens) - 1
                
                target_phase = valid_greens[action_idx]
                
                # Logic for Transition
                current_phase = traci.trafficlight.getPhase(tls_id)
                if current_phase == target_phase: continue
                if tls_id in self.pending_switches:
                    self.pending_switches[tls_id] = target_phase
                    continue

                yellow_phase = self._get_yellow_phase(tls_id, current_phase)
                
                # If we are already in yellow (or transition is impossible), force target
                if yellow_phase == current_phase:
                    # Just schedule it instantly
                    self.pending_switches[tls_id] = target_phase
                    self.yellow_timers[tls_id] = 1 
                else:
                    # Switch to Yellow
                    traci.trafficlight.setPhase(tls_id, yellow_phase)
                    self.pending_switches[tls_id] = target_phase
                    self.yellow_timers[tls_id] = self.YELLOW_DURATION

            except Exception as e:
                print(f"❌ Error applying action to {tls_id}: {e}")

    # -----------------------------------------------------------------------
    # DYNAMIC FLOW RATE CONTROL
    # -----------------------------------------------------------------------

    def set_flow_rate(self, route_id: str, vehicles_per_hour: float) -> dict:
        """Adjust vehicle insertion rate on *route_id* at runtime via TraCI.

        Args:
            route_id: A route ID that must already exist in the SUMO network.
            vehicles_per_hour: Desired arrival rate (0 disables injection).

        Returns:
            A result dict with ``status`` and ``message``.
        """
        if not self.is_running:
            return {"status": "error", "message": "Simulation is not running"}

        try:
            known_routes = traci.route.getIDList()
        except Exception as e:
            return {"status": "error", "message": f"TraCI error: {e}"}

        if route_id not in known_routes:
            return {
                "status": "error",
                "message": f"Route '{route_id}' not found. Available: {list(known_routes)}",
            }

        if vehicles_per_hour < 0:
            return {"status": "error", "message": "vehicles_per_hour must be >= 0"}

        self.flow_rates[route_id] = float(vehicles_per_hour)
        # Reset injection timer so the new rate takes effect immediately
        try:
            self._flow_last_injections[route_id] = traci.simulation.getTime()
        except Exception:
            self._flow_last_injections[route_id] = 0.0

        print(f"[FlowRate] route='{route_id}' rate={vehicles_per_hour} veh/h")
        return {
            "status": "success",
            "message": f"Flow rate for '{route_id}' set to {vehicles_per_hour} veh/h",
            "route_id": route_id,
            "vehicles_per_hour": vehicles_per_hour,
        }

    def set_global_flow_rate(self, vehicles_per_hour: float) -> dict:
        """Apply *vehicles_per_hour* to every route currently in the simulation.

        Args:
            vehicles_per_hour: Desired arrival rate shared across all routes
                               (0 disables injection on all routes).

        Returns:
            A result dict with ``status``, ``message``, and ``route_count``.
        """
        if not self.is_running:
            return {"status": "error", "message": "Simulation is not running"}

        if vehicles_per_hour < 0:
            return {"status": "error", "message": "vehicles_per_hour must be >= 0"}

        try:
            known_routes = list(traci.route.getIDList())
            current_time = traci.simulation.getTime()
        except Exception as e:
            return {"status": "error", "message": f"TraCI error: {e}"}

        for route_id in known_routes:
            self.flow_rates[route_id] = float(vehicles_per_hour)
            self._flow_last_injections[route_id] = current_time

        print(f"[FlowRate] global rate={vehicles_per_hour} veh/h applied to {len(known_routes)} routes")
        return {
            "status": "success",
            "message": f"Global flow rate set to {vehicles_per_hour} veh/h across {len(known_routes)} routes",
            "vehicles_per_hour": vehicles_per_hour,
            "route_count": len(known_routes),
        }

    def get_routes(self) -> dict:
        """Return all route IDs currently loaded in SUMO via TraCI."""
        if not self.is_running:
            return {"status": "error", "message": "Simulation is not running"}

        try:
            route_ids = list(traci.route.getIDList())
            return {"status": "success", "routes": route_ids}
        except Exception as e:
            return {"status": "error", "message": f"TraCI error: {e}"}

    def _inject_flow_vehicles(self):
        """Called every simulation step to insert vehicles according to ``flow_rates``."""
        if not self.flow_rates:
            return

        try:
            current_time = traci.simulation.getTime()
        except Exception:
            return

        for route_id, rate in list(self.flow_rates.items()):
            if rate <= 0:
                continue

            period = 3600.0 / rate  # seconds between insertions
            last = self._flow_last_injections.get(route_id, current_time - period)

            if (current_time - last) >= period:
                self._flow_vehicle_counter += 1
                veh_id = f"flow_{route_id}_{self._flow_vehicle_counter}"
                try:
                    traci.vehicle.add(vehID=veh_id, routeID=route_id)
                    self._flow_last_injections[route_id] = current_time
                except traci.exceptions.TraCIException as exc:
                    # Vehicle may already exist or route is invalid — skip silently
                    print(f"[FlowRate] Could not add vehicle '{veh_id}': {exc}")

    def unload_optimizer(self):
        """Disable the currently loaded optimizer"""
        self.optimizer = None
        self.optimization_enabled = False
        print("🔌 Optimizer Unloaded (Reverted to Default Control)")
        return {"status": "success", "message": "Optimizer unloaded"}
    
    def pause(self):
        """Pause simulation"""
        if not self.is_running:
            return {"status": "error", "message": "Simulation not running"}
            
        self.is_paused = True
        return {"status": "success", "message": "Simulation paused", "step": self.current_step}
    
    def resume(self):
        """Resume simulation"""
        if not self.is_running:
            return {"status": "error", "message": "Simulation not running"}
            
        if not self.is_paused:
            return {"status": "error", "message": "Simulation not paused"}
            
        self.is_paused = False
        return {"status": "success", "message": "Simulation resumed", "step": self.current_step}
    
    def stop(self):
        """Stop and close simulation"""
        if not self.is_running:
            return {"status": "error", "message": "Simulation not running"}

        if self.stopping:
            return {"status": "error", "message": "Simulation is already shutting down"}

        # Immediately update state so no new steps / starts can be issued
        self.auto_stepping = False
        self.is_running = False
        self.is_paused = False
        self.stopping = True

        # Capture thread reference before clearing it
        auto_step_thread = self.auto_step_thread

        def _teardown():
            """Run blocking SUMO teardown in background so the HTTP response returns fast."""
            try:
                # Wait for the auto-step loop to exit (it checks is_running / auto_stepping)
                if auto_step_thread and auto_step_thread.is_alive():
                    auto_step_thread.join(timeout=2)

                # traci.close() blocks until SUMO fully exits — safe to do here in background
                traci.close()
                self.current_step = 0
                # Clear dynamic flow state so old rates don't persist after restart
                self.flow_rates.clear()
                self._flow_last_injections.clear()
                self._flow_vehicle_counter = 0
                print("Simulation stopped (teardown complete)")
            except Exception as e:
                print(f"Error during simulation teardown: {e}")
            finally:
                self.stopping = False

        teardown_thread = threading.Thread(target=_teardown, daemon=True)
        teardown_thread.start()

        return {"status": "success", "message": "Simulation stopped"}
    
