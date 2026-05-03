import os
import sys
import traci
import threading
import time
import xml.etree.ElementTree as ET
from optimizers.gnn_adapter import GNNTrafficOptimizer
from optimizers.mpc_adapter import MPCTrafficOptimizer

from routing.inprocess_router import InProcessModelRouter
from sumo.connection import (
    open_sumo_connection,
    close_sumo_connection,
    ensure_sumo_home_on_path,
)

# Add $SUMO_HOME/tools to sys.path if available (required by sumolib).
# In SUMO_MODE=remote, SUMO_HOME may not be set on the Manager host —
# that's fine; sumolib can be installed via pip in the container.
ensure_sumo_home_on_path()


class SimulationController:
    def __init__(self, config_file, socketio_instance=None, use_gui=True, step_delay=0.1, evps_adapter=None):
        self.socketio = socketio_instance
        self.config_file = config_file
        self.use_gui = use_gui
        self.default_step_delay = step_delay
        self.evps_adapter = evps_adapter
        self.is_running = False
        self.is_paused = False
        self.current_step = 0
        self.auto_stepping = False
        self.auto_step_thread = None
        self.step_lock = threading.Lock()  # Lock for thread-safe stepping
        self.stopping = False  # True while background teardown is in progress
        self.optimizer = None              # Backward-compat alias for self.model_router.adapter
        self.model_router = None           # ModelRouter abstraction (contract-shaped)
        self.session_id = None             # Set when load_model is called
        self._last_telemetry = {}          # Latest telemetry from the model router
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
        # ── Phase 5: EVPS HTTP integration ──────────────────────────
        self.ws_clients: set = set()        # Raw WebSocket connections (driver app)
        self.evps_client = None              # HTTP client to EVPS service if EVPS_URL set
        self._evps_session_id = None
        self._init_evps_client()

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
                
                if j_type != "traffic_light": continue

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

    def get_network_geojson(self):
        """
        Parses the SUMO network file and returns a GeoJSON FeatureCollection
        of all non-internal edges (roads).
        """
        import sumolib
        net_file = self._get_net_file_from_config()
        if not net_file:
            return {"error": "Network file not found"}

        try:
            # We use sumolib to get precise node coordinates and handle projections
            net = sumolib.net.readNet(net_file)
            
            features = []
            # Only iterate through standard edges (ignore internal junction paths)
            for edge in net.getEdges():
                if edge.isSpecial():
                    continue
                
                # Get raw SUMO Cartesian (x,y) coordinates for the edge shape
                shape = edge.getShape()
                line_coords = []
                
                # Convert each point to WGS84 (Lon, Lat) which GeoJSON expects
                for (x, y) in shape:
                    lon, lat = net.convertXY2LonLat(x, y)
                    line_coords.append([lon, lat])
                
                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": edge.getID(),
                        "type": edge.getType() if edge.getType() else "road",
                        "lanes": edge.getLaneNumber(),
                        "speedLimit": edge.getSpeed()
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": line_coords
                    }
                }
                features.append(feature)

            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            return geojson

        except Exception as e:
            print(f"❌ Error extracting GeoJSON: {e}")
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
                next_green = self._get_next_green_phase(tls_id, current_phase)

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

    def _get_next_green_phase(self, tls_id, current_phase):
        try:
            logics = traci.trafficlight.getAllProgramLogics(tls_id)
            total_phases = len(logics[0].phases) if logics else 4
        except Exception:
            total_phases = 4
        next_phase = (current_phase + 1) % total_phases
        if next_phase % 2 != 0:
            next_phase = (next_phase + 1) % total_phases
        return next_phase

    def load_model(self, name: str = "gnn") -> dict:
        """Load a model by name and wrap it in a ModelRouter.

        Phase 3: dispatches between InProcessModelRouter and HttpModelRouter
        based on the MODEL_<NAME>_URL env var:
          - Set    → HttpModelRouter (Phase 3+ for GNN, Phase 4+ for MPC)
          - Unset  → InProcessModelRouter (Phase 2 behavior, preserved as fallback)

        Setting MODEL_GNN_URL=http://gnn_service:8002 promotes GNN inference
        to the dedicated gnn_service container. Unsetting falls back to the
        in-process adapter without any code change — useful for development
        and as a safety net when the model service is unavailable.
        """
        print(f"🔌 Loading model: {name.upper()}")

        current_net_file = self._get_net_file_from_config()
        if not current_net_file:
            print("❌ Cannot load model: Network file could not be determined from config.")
            return {"status": "error", "message": "Network file not found"}

        scenario_name = os.path.basename(os.path.dirname(self.config_file))
        http_url = self._get_model_http_url(name)

        try:
            if http_url:
                # ── HTTP router ────────────────────────────────────────
                from routing.http_router import HttpModelRouter
                print(f"🌐 [{name.upper()}] Using HTTP router → {http_url}")

                timeout_ms = int(os.environ.get('MODEL_TIMEOUT_MS', '2000'))
                reset_timeout_ms = int(os.environ.get('MODEL_RESET_TIMEOUT_MS', '30000'))
                auth_token = os.environ.get(f'MODEL_{name.upper()}_AUTH_TOKEN')

                self.model_router = HttpModelRouter(
                    model_name=name,
                    base_url=http_url,
                    timeout_ms=timeout_ms,
                    reset_timeout_ms=reset_timeout_ms,
                    auth_token=auth_token,
                )
                self.optimizer = None   # No in-process adapter when routing over HTTP

                # Build network dict for /reset. Phase 3 uses the
                # _internal_net_xml_path shortcut so the model service
                # can use sumolib directly. Phase 7 will populate the
                # full topology dict per network.schema.json so external
                # researchers don't need to mount scenario files.
                network = self._build_network_dict_for_reset(current_net_file, scenario_name)

                self.session_id = f"sess_{int(time.time())}"
                try:
                    self.model_router.reset(
                        session_id=self.session_id,
                        network=network,
                        config={"scenario": scenario_name},
                    )
                except Exception as exc:
                    self.model_router = None
                    self.optimization_enabled = False
                    return {"status": "error", "message": f"Model service /reset failed: {exc}"}
            else:
                # ── In-process router (Phase 2 fallback) ───────────────
                print(f"📦 [{name.upper()}] Using in-process router")
                if name == "gnn":
                    adapter = GNNTrafficOptimizer(net_path=current_net_file)
                elif name == "mpc":
                    adapter = MPCTrafficOptimizer(net_path=current_net_file)
                else:
                    return {"status": "error", "message": f"Unknown model: {name}"}

                self.model_router = InProcessModelRouter(name, adapter)
                self.optimizer = adapter   # Backward-compat for endpoints that touch the adapter directly
                self.session_id = f"sess_{int(time.time())}"
                self.model_router.reset(session_id=self.session_id, network={}, config={})

            self.optimization_enabled = True

            info = self.model_router.info()
            self.action_interval = info.get('decision_interval_steps', self.action_interval)

            print(f"✅ {name.upper()} attached to: {os.path.basename(current_net_file)} — interval={self.action_interval}, types={info.get('action_types_supported')}")
            return {"status": "success", "message": f"{name.upper()} Optimizer Loaded", "info": info}
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _get_model_http_url(self, name: str):
        """Return the HTTP URL for a model service, or None if not configured.

        Looks up MODEL_<NAME>_URL environment variable.
        Examples:
            MODEL_GNN_URL=http://gnn_service:8002
            MODEL_MPC_URL=http://mpc_service:8003

        An empty-string value is treated the same as unset (so docker-compose
        env shapes like ``MODEL_GNN_URL: ""`` cleanly disable the HTTP route).
        """
        url = os.environ.get(f'MODEL_{name.upper()}_URL', '')
        return url if url else None

    def _build_network_dict_for_reset(self, net_file: str, scenario_name: str) -> dict:
        """Build a network topology dict for the /reset payload.

        Phase 3 includes a `_internal_net_xml_path` shortcut so the model
        service can use sumolib directly against the same .net.xml file
        the Manager sees. Phase 7 will populate the full intersections /
        lanes / edges / connections per
        contracts/schemas/network.schema.json so external researchers
        don't need to mount scenario files.
        """
        return {
            "scenario_name": scenario_name,
            "intersections": [],
            "lanes": [],
            "edges": [],
            "connections": [],
            "_internal_net_xml_path": net_file,
        }

    def get_mpc_internals(self) -> dict:
        """Return MPC-specific internals for the dashboard Internals tab.

        Works for both in-process and HTTP-routed MPC (Phase 4+):
          - In-process : calls adapter.get_internals() directly
          - HTTP       : proxies to <MODEL_MPC_URL>/internals

        Used by the /api/optimizer/mpc/internals endpoint in app.py.
        """
        # In-process path — adapter still attached (Phase 2 / 3 behavior)
        if self.optimizer is not None and hasattr(self.optimizer, 'get_internals'):
            try:
                data = self.optimizer.get_internals()
                data["status"] = "active"
                return data
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        # HTTP path — active model is MPC routed over HTTP
        if self.model_router is not None:
            try:
                info = self.model_router.info()
                if info.get('name') == 'mpc':
                    http_url = os.environ.get('MODEL_MPC_URL', '')
                    if http_url:
                        try:
                            import requests
                            resp = requests.get(
                                f"{http_url.rstrip('/')}/internals",
                                timeout=2.0,
                            )
                            resp.raise_for_status()
                            return resp.json()
                        except Exception as exc:
                            return {"status": "error", "message": str(exc)}
            except Exception:
                pass

        return {"status": "idle", "message": "MPC optimizer not loaded"}

    def load_optimizer(self, model_type: str = "gnn") -> dict:
        """Backward-compat alias for load_model().

        The Sim Control Panel UI calls POST /api/optimizer/load with
        {"type": "gnn"} — this method preserves that shape.
        """
        return self.load_model(model_type)

    # =========================================================================
    # CORE SIMULATION LOGIC (Refactored)
    # =========================================================================
    
    def _advance_simulation(self):
        """
        Central method to advance the simulation by one step.
        Handles: AI Inference -> Yellow Phase Management -> Traci Step
        """
        # 1. AI OPTIMIZATION HOOK
        if self.optimization_enabled and self.model_router is not None:
            if (self.current_step - self.last_action_step) >= self.action_interval:
                try:
                    snapshot = self._capture_snapshot_for_ai()

                    # Aggregate stats for logging
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
                    opt_name = self.model_router.info().get('name', 'model').upper()
                    print(f"🚦 {opt_name} Step: {self.current_step} | Max Queue: {max_queue} veh | Avg Speed: {avg_speed:.2f} m/s | Total Wait: {total_waiting:.1f} s")

                    response = self.model_router.predict(
                        session_id=self.session_id,
                        step=self.current_step,
                        snapshot=snapshot,
                    )
                    self._apply_actions(response.get('actions', {}))
                    self._last_telemetry = response.get('telemetry', {})
                    self.last_action_step = self.current_step
                except traci.exceptions.FatalTraCIError:
                    print("Simulation ended by SUMO.")
                    self.stop()
                    return
                except Exception as e:
                    print(f"⚠️ Model Router Error: {e}")

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

        # 3.6. EVPS AI LOGIC
        # Phase 5: prefer the HTTP client when configured; fall back to the
        # in-process adapter (Phase 2 behavior) otherwise.
        if self.evps_client is not None:
            self._run_evps_step_via_http()
        elif self.evps_adapter is not None:
            self.evps_adapter.execute_step()

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
                
                opt_telemetry = {}
                if self.optimization_enabled and self.optimizer and hasattr(self.optimizer, 'get_telemetry'):
                    opt_telemetry = self.optimizer.get_telemetry()
                
                if opt_telemetry:
                    print(f"DEBUG Emitter: Telemetry payload contains: {list(opt_telemetry.keys())}")
                    
                self.socketio.emit('simulation_step', {
                    'step': self.current_step,
                    'lanes': snapshot['lanes'],
                    'intersections': snapshot['intersections'],
                    'global': {
                        'arrived_vehicles': arrived_vehicles
                    },
                    'optimizer_telemetry': opt_telemetry
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

        try:
            conn_info = open_sumo_connection(
                config_file=self.config_file,
                use_gui=self.use_gui,
                suppress_demand=suppress_demand,
            )
            self.is_running = True
            self.is_paused = False
            self.current_step = 0
            print(f"Simulation started — mode={conn_info.get('mode')}, config={self.config_file}")

            # Phase 5: reset the EVPS service for the new session
            if self.evps_client is not None:
                try:
                    self._evps_session_id = f"evps_{int(time.time())}"
                    self.evps_client.reset(self._evps_session_id)
                    print(f"[EVPS] HTTP session reset: {self._evps_session_id}")
                except Exception as exc:
                    print(f"⚠️ [EVPS] /reset failed: {exc}")

            return {
                "status": "success",
                "message": "Simulation started",
                "step": self.current_step,
                "auto_stepping": self.auto_stepping,
                "suppress_demand": suppress_demand,
                "sumo_mode": conn_info.get('mode'),
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

    def _apply_actions(self, actions: dict) -> None:
        """Dispatch contract-format actions to the appropriate phase-control helper.

        Each action conforms to contracts/schemas/action.schema.json:
            {"type": "binary_switch" | "set_phase" | "set_duration", ...}

        We split by type and delegate to the existing helpers, which already
        handle yellow-phase transitions and TraCI calls.
        """
        binary_actions = {}
        set_phase_actions = {}

        for tls_id, action in (actions or {}).items():
            if not isinstance(action, dict):
                continue
            action_type = action.get('type')
            if action_type == 'binary_switch':
                binary_actions[tls_id] = action.get('value', 0)
            elif action_type == 'set_phase':
                set_phase_actions[tls_id] = action.get('value', 0)
            # set_duration is not yet implemented in TraCI side. Phase 4+
            # adds a dedicated path. For now, set_duration actions fall
            # through and the underlying TLS keeps its current phase.

        if binary_actions:
            self._apply_gnn_binary_actions(binary_actions)
        if set_phase_actions:
            self._apply_ai_actions(set_phase_actions)

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
        """Disable the currently loaded optimizer/model router."""
        if self.model_router is not None:
            try:
                self.model_router.teardown()
            except Exception as exc:
                print(f"⚠️ Router teardown error: {exc}")
        self.model_router = None
        self.optimizer = None
        self.session_id = None
        self._last_telemetry = {}
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

    # =========================================================================
    # Phase 5: EVPS HTTP integration
    # =========================================================================

    def _init_evps_client(self) -> None:
        """Configure EvpsClient if EVPS_URL is set, else None."""
        evps_url = os.environ.get('EVPS_URL', '')
        if not evps_url:
            return
        try:
            from routing.evps_client import EvpsClient
            self.evps_client = EvpsClient(
                base_url=evps_url,
                timeout_ms=int(os.environ.get('EVPS_TIMEOUT_MS', '2000')),
            )
            print(f"🌐 [EVPS] Using HTTP client → {evps_url}")
        except Exception as exc:
            print(f"⚠️ [EVPS] Failed to init client: {exc}")

    # ── WebSocket client management (driver app) ──────────────────

    def register_ws_client(self, ws) -> None:
        """Register a raw WebSocket connection from the driver app."""
        self.ws_clients.add(ws)
        # Backward compat: also register on the in-process adapter so that
        # path keeps broadcasting status to the driver app.
        if self.evps_adapter is not None and hasattr(self.evps_adapter, 'set_websocket'):
            self.evps_adapter.set_websocket(ws)

    def unregister_ws_client(self, ws) -> None:
        self.ws_clients.discard(ws)
        if self.evps_adapter is not None and hasattr(self.evps_adapter, 'disconnect_websocket'):
            self.evps_adapter.disconnect_websocket(ws)

    # ── EVPS API forwarding (in-process or HTTP) ──────────────────

    def evps_toggle(self, enable: bool) -> dict:
        """Enable/disable EVPS. Forwards to HTTP client when configured."""
        if self.evps_client is not None:
            self.evps_client.toggle(enable)
            return {"status": "success", "evps_enabled": bool(enable), "via": "http"}
        if self.evps_adapter is not None:
            self.evps_adapter.toggle_evps(bool(enable))
            return {"status": "success", "evps_enabled": bool(enable), "via": "in_process"}
        return {"status": "error", "message": "EVPS not configured"}

    def evps_set_focus(self, ev_id: str) -> dict:
        if self.evps_client is not None:
            return self.evps_client.set_focus(ev_id)
        if self.evps_adapter is not None:
            self.evps_adapter.switch_vehicle(ev_id)
            return {"status": "ok"}
        return {"status": "error", "message": "EVPS not configured"}

    def evps_set_priority(self, ev_id: str, priority) -> dict:
        if self.evps_client is not None:
            return self.evps_client.set_priority(ev_id, int(priority))
        if self.evps_adapter is not None:
            self.evps_adapter.set_ev_priority(ev_id, priority)
            return {"status": "ok"}
        return {"status": "error", "message": "EVPS not configured"}

    def evps_spawn_geo(self, start_lon, start_lat, end_lon, end_lat, ev_id=None) -> dict:
        """Spawn EV from geo coordinates.

        TraCI work happens via the in-process adapter (it owns the spawn
        logic). When HTTP routing is active, we ALSO notify the EVPS
        service so it can register the EV in its fleet.
        """
        if self.evps_adapter is None:
            return {"status": "error", "message": "EVPS not configured"}
        result = self.evps_adapter.spawn_ev_from_geo(
            start_lon, start_lat, end_lon, end_lat, ev_id=ev_id,
        )
        if self.evps_client is not None and result.get("status") == "success":
            veh_id = result.get("vehicle_id")
            if veh_id:
                try:
                    self.evps_client.register_ev(veh_id, priority=1, vehicle_type="ambulance")
                    self.evps_client.set_focus(veh_id)
                except Exception as exc:
                    print(f"⚠️ [EVPS] register_ev failed: {exc}")
        return result

    def evps_spawn_random(self, ev_id=None) -> dict:
        if self.evps_adapter is None:
            return {"status": "error", "message": "EVPS not configured"}
        result = self.evps_adapter.spawn_random_ev(ev_id=ev_id)
        if self.evps_client is not None and result.get("status") == "success":
            veh_id = result.get("vehicle_id")
            if veh_id:
                try:
                    self.evps_client.register_ev(veh_id, priority=1, vehicle_type="ambulance")
                    self.evps_client.set_focus(veh_id)
                except Exception as exc:
                    print(f"⚠️ [EVPS] register_ev failed: {exc}")
        return result

    # ── Per-step HTTP EVPS execution ──────────────────────────────

    def _run_evps_step_via_http(self) -> None:
        """Build snapshot, call /step, apply overrides, relay broadcasts."""
        try:
            snapshot = self._build_evps_snapshot()
            response = self.evps_client.step(snapshot)
            self._apply_evps_overrides(response.get('overrides', {}))
            self._handle_evps_released_locks(response.get('released_locks', []))
            self._relay_evps_broadcasts(response.get('broadcasts', {}))
        except Exception as exc:
            print(f"⚠️ [EVPS] step error: {exc}")

    def _build_evps_snapshot(self) -> dict:
        """Capture all data the EVPS service needs from TraCI for one step.

        Includes EV-prefixed vehicles, all TLS state + phase definitions,
        and lane data for lanes EVPS may need to inspect (controlled lanes
        + downstream lanes from EV routes).
        """
        vehicles_data = []

        for veh_id in traci.vehicle.getIDList():
            if not veh_id.startswith("EV_"):
                continue
            try:
                position = traci.vehicle.getPosition(veh_id)
                lat = lon = 0.0
                try:
                    lon, lat = traci.simulation.convertGeo(position[0], position[1])
                except Exception:
                    pass

                current_lane = traci.vehicle.getLaneID(veh_id)
                current_lane_halting = 0
                current_lane_length = 0.0
                try:
                    current_lane_halting = traci.lane.getLastStepHaltingNumber(current_lane)
                    current_lane_length = traci.lane.getLength(current_lane)
                except Exception:
                    pass

                next_tls = []
                try:
                    for t_id, t_index, t_dist, t_state in traci.vehicle.getNextTLS(veh_id):
                        next_tls.append({
                            "tls_id": t_id,
                            "tls_index": t_index,
                            "distance": t_dist,
                            "state": t_state,
                        })
                except Exception:
                    pass

                leader_info = None
                try:
                    leader = traci.vehicle.getLeader(veh_id, 200)
                    if leader:
                        leader_info = {
                            "id": leader[0],
                            "gap": leader[1],
                            "speed": traci.vehicle.getSpeed(leader[0]),
                        }
                except Exception:
                    pass

                vehicles_data.append({
                    "id": veh_id,
                    "type": traci.vehicle.getTypeID(veh_id),
                    "speed": traci.vehicle.getSpeed(veh_id),
                    "acceleration": traci.vehicle.getAcceleration(veh_id),
                    "position": [position[0], position[1]],
                    "geo_position": [lon, lat],
                    "current_lane": current_lane,
                    "lane_position": traci.vehicle.getLanePosition(veh_id),
                    "current_edge": traci.vehicle.getRoadID(veh_id),
                    "route": list(traci.vehicle.getRoute(veh_id)),
                    "current_lane_length": current_lane_length,
                    "current_lane_halting": current_lane_halting,
                    "next_tls": next_tls,
                    "leader": leader_info,
                })
            except Exception as exc:
                print(f"[EVPS] Failed to capture {veh_id}: {exc}")

        # TLS state with phase definitions
        tls_states = {}
        for tls_id in traci.trafficlight.getIDList():
            try:
                phase_index = traci.trafficlight.getPhase(tls_id)
                phase_state = traci.trafficlight.getRedYellowGreenState(tls_id)
                controlled_lanes = list(traci.trafficlight.getControlledLanes(tls_id))

                phases = []
                try:
                    logics = traci.trafficlight.getAllProgramLogics(tls_id)
                    if logics:
                        for i, p in enumerate(logics[0].phases):
                            phases.append({"index": i, "state": p.state})
                except Exception:
                    pass

                geo_position = None
                try:
                    pos = traci.junction.getPosition(tls_id)
                    g_lon, g_lat = traci.simulation.convertGeo(pos[0], pos[1])
                    geo_position = [g_lon, g_lat]
                except Exception:
                    pass

                tls_states[tls_id] = {
                    "phase_index": phase_index,
                    "phase_state": phase_state,
                    "controlled_lanes": controlled_lanes,
                    "phases": phases,
                    "geo_position": geo_position,
                }
            except Exception:
                pass

        # Lane data for lanes EVPS may inspect
        lanes_of_interest = set()
        for tls in tls_states.values():
            for lane in tls.get("controlled_lanes", []):
                lanes_of_interest.add(lane)
        for v in vehicles_data:
            for edge in v.get("route", []):
                lanes_of_interest.add(f"{edge}_0")

        lane_data = {}
        for lane in lanes_of_interest:
            try:
                lane_data[lane] = {
                    "halting": traci.lane.getLastStepHaltingNumber(lane),
                    "vehicle_count": traci.lane.getLastStepVehicleNumber(lane),
                    "length": traci.lane.getLength(lane),
                }
            except Exception:
                pass

        return {
            "step": self.current_step,
            "session_id": self._evps_session_id or "default",
            "sim_time": traci.simulation.getTime(),
            "vehicles": vehicles_data,
            "tls": tls_states,
            "lanes": lane_data,
        }

    def _apply_evps_overrides(self, overrides: dict) -> None:
        """Apply each EVPS override via traci.trafficlight.setRedYellowGreenState."""
        if not overrides:
            return
        for tls_id, override in overrides.items():
            phase_state = override.get("phase_state")
            if not phase_state:
                continue
            try:
                traci.trafficlight.setRedYellowGreenState(tls_id, phase_state)
            except Exception as exc:
                print(f"[EVPS] override apply failed at {tls_id}: {exc}")

    def _handle_evps_released_locks(self, released: list) -> None:
        """Restore default program for TLSes whose EVPS lock was released."""
        for tls_id in (released or []):
            try:
                traci.trafficlight.setProgram(tls_id, "0")
            except Exception:
                pass

    def _relay_evps_broadcasts(self, broadcasts: dict) -> None:
        """Forward EVPS broadcast payloads to all connected driver-app WS clients."""
        if not broadcasts or not self.ws_clients:
            return
        import json
        dead = set()
        for ws in list(self.ws_clients):
            for ev_id, payload in broadcasts.items():
                try:
                    ws.send(json.dumps(payload))
                except Exception:
                    dead.add(ws)
                    break
        for ws in dead:
            self.ws_clients.discard(ws)

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
    
