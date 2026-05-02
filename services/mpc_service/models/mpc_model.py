"""MPC inference model wrapper for the HTTP service.

Reuses MPCController, DemandPredictor, and configs from
services/mpc_traffic_control/src/traffic_mpc/. **No TraCI dependency:**
- Static topology (TLS phases, controlled lanes, lane lengths) is loaded
  from the .net.xml file via sumolib at /reset time
- Dynamic state (queue lengths, current SUMO phase index) is read from
  the snapshot dict passed in /predict

This preserves the orchestration logic from
`services/simulation_manager/optimizers/mpc_adapter.py` exactly, while
swapping every TraCI call for a sumolib lookup or a snapshot field.

Per-session state (cleared on /reset):
- controllers:    {tls_id: {model, green_indices, phase_states}}
- cycle_plans:    {tls_id: active plan or None}
- last_decisions: {tls_id: diagnostics for /internals dashboard tab}
- upstream_lanes: {lane_id: [predecessor_lane_ids]} (for recursive queue polling)
- lane_lengths:   {lane_id: length_meters} (cached from net.xml)
- predictor:      DemandPredictor (LSTM)
"""
from __future__ import annotations
import os
import sys
import json
import time
from typing import Optional, Tuple

import numpy as np

# Ensure mpc_traffic_control source is on sys.path. Path resolution:
#   /workspace/services/mpc_service/models/mpc_model.py
#   ../../../mpc_traffic_control/src  →  /workspace/services/mpc_traffic_control/src
_MPC_SRC_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'mpc_traffic_control', 'src')
)
if _MPC_SRC_PATH not in sys.path:
    sys.path.append(_MPC_SRC_PATH)

from traffic_mpc.core.controller import MPCController  # noqa: E402
from traffic_mpc.core.prediction import DemandPredictor  # noqa: E402
from traffic_mpc.config.settings import MPCConfig, OptimizationConfig  # noqa: E402

import sumolib  # noqa: E402


# Lane capacity heuristic — same value as the in-process MPC adapter
_LANE_CAPACITY = 20.0


class MPCModel:
    """HTTP-friendly facade over the MPC pipeline. Single-tenant."""

    def __init__(
        self,
        net_xml_path: str,
        scenario_name: str = "default",
        weights_dir: Optional[str] = None,
    ):
        self.net_xml_path = net_xml_path
        self.scenario_name = scenario_name
        self.weights_dir = weights_dir

        # Per-controller state
        self.controllers: dict = {}     # tls_id -> {model, green_indices, phase_states}
        self.cycle_plans: dict = {}     # tls_id -> active plan or None
        self.last_decisions: dict = {}  # tls_id -> diagnostics

        # Cached static topology (replaces TraCI calls)
        self.upstream_lanes: dict = {}
        self.lane_lengths: dict = {}

        # Demand prediction
        self.predictor: Optional[DemandPredictor] = None
        self.all_lanes_ordered: list = []

        # Scenario-specific MPC config
        self.mpc_cfg = self._build_mpc_config(scenario_name)
        self.opt_cfg = OptimizationConfig()

        self.session_id: Optional[str] = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _build_mpc_config(scenario_name: str) -> MPCConfig:
        """Mirror the scenario-specific config logic from mpc_adapter.py."""
        if scenario_name == 'katunayake':
            print("🚀 Detected Katunayake — extending MPC cycle to 120s, max green to 90s")
            return MPCConfig(
                prediction_horizon=20,
                control_horizon=5,
                min_green_time=5,
                max_green_time=90,
                cycle_time=120,
            )
        return MPCConfig(
            prediction_horizon=20,
            control_horizon=5,
            min_green_time=5,
            max_green_time=60,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self, session_id: str) -> None:
        """Build per-TLS controllers and the demand predictor.

        All static topology comes from sumolib reading the .net.xml file —
        no TraCI required.
        """
        if not os.path.exists(self.net_xml_path):
            raise FileNotFoundError(f"Network file not found: {self.net_xml_path}")

        net = sumolib.net.readNet(self.net_xml_path)

        # ── 1. Build per-TLS controllers ──────────────────────────────
        count = 0
        for tls in net.getTrafficLights():
            tls_id = tls.getID()

            programs = tls.getPrograms()
            if not programs:
                continue
            program = next(iter(programs.values()))
            phases = program.getPhases()

            # Identify green-only phases
            green_phase_indices = []
            phase_states = []
            for i, phase in enumerate(phases):
                state = phase.state
                phase_states.append(state)
                if 'g' in state.lower() and 'y' not in state.lower():
                    green_phase_indices.append(i)

            num_green_phases = len(green_phase_indices)
            if num_green_phases == 0:
                print(f"⚠️ MPC: No green phases for {tls_id} — skipping")
                continue

            sumo_to_rank = {sumo_idx: rank for rank, sumo_idx in enumerate(green_phase_indices)}

            # Resolve controlled lanes per phase
            connections = tls.getConnections()  # [(inLane, outLane, linkIdx), ...]

            lane_ids = []
            lane_phase_indices = []
            seen_lanes = set()

            for conn in connections:
                # sumolib returns (Lane, Lane, link_index)
                from_lane_obj = conn[0]
                link_idx = conn[2] if len(conn) >= 3 else 0
                try:
                    lane_id = from_lane_obj.getID()
                except AttributeError:
                    # Some sumolib versions return strings instead of Lane objects
                    lane_id = str(from_lane_obj)

                if lane_id in seen_lanes:
                    continue

                # Find which phase first lights this link green
                my_sumo_green_phase = -1
                for p_idx, state in enumerate(phase_states):
                    if link_idx < len(state):
                        char = state[link_idx].lower()
                        if char == 'g':
                            my_sumo_green_phase = p_idx
                            break

                if my_sumo_green_phase != -1 and my_sumo_green_phase in sumo_to_rank:
                    lane_ids.append(lane_id)
                    lane_phase_indices.append(sumo_to_rank[my_sumo_green_phase])
                    seen_lanes.add(lane_id)

            if not lane_ids:
                print(f"⚠️ MPC: No valid controlled lanes for {tls_id}")
                continue

            try:
                controller = MPCController(
                    mpc_config=self.mpc_cfg,
                    opt_config=self.opt_cfg,
                    lane_ids=lane_ids,
                    num_phases=num_green_phases,
                    lane_phase_indices=lane_phase_indices,
                )
                self.controllers[tls_id] = {
                    "model": controller,
                    "green_indices": green_phase_indices,   # SUMO absolute phase indices
                    "phase_states": phase_states,
                }
                self.cycle_plans[tls_id] = None
                count += 1
            except Exception as exc:
                print(f"❌ MPC init failed for {tls_id}: {exc}")

        print(f"✅ MPC initialized for {count} intersections")

        # ── 2. Cache static topology: lane lengths + upstream lanes ───
        # Replaces traci.lane.getLength() and the upstream traversal in
        # _get_recursive_queue() of mpc_adapter.py.
        for edge in net.getEdges():
            for lane in edge.getLanes():
                lid = lane.getID()
                self.lane_lengths[lid] = lane.getLength()
                self.upstream_lanes[lid] = []
                for in_lane in lane.getIncoming():
                    if in_lane is not None:
                        try:
                            self.upstream_lanes[lid].append(in_lane.getID())
                        except AttributeError:
                            self.upstream_lanes[lid].append(str(in_lane))

        # ── 3. Init demand predictor ──────────────────────────────────
        all_lanes_set = set()
        for tls_id, data in self.controllers.items():
            for lid in data["model"].lane_ids:
                all_lanes_set.add(lid)
        self.all_lanes_ordered = sorted(list(all_lanes_set))

        if self.weights_dir:
            if self.scenario_name == "grid3x3" or self.scenario_name == "default":
                lane_ids_filename = "lane_ids.json"
                model_filename = "model.pth"
            else:
                lane_ids_filename = f"lane_ids_{self.scenario_name}.json"
                model_filename = f"model_{self.scenario_name}.pth"

            lane_ids_path = os.path.join(self.weights_dir, lane_ids_filename)
            model_path = os.path.join(self.weights_dir, model_filename)

            if os.path.exists(lane_ids_path):
                try:
                    with open(lane_ids_path, "r") as f:
                        self.all_lanes_ordered = json.load(f)
                except Exception as exc:
                    print(f"⚠️ Could not read {lane_ids_path}: {exc}")

            print(f"🔮 Initializing Demand Predictor for {len(self.all_lanes_ordered)} lanes")
            print(f"   Scenario: {self.scenario_name}")
            print(f"   Model:    {model_path}")
            if not os.path.exists(model_path):
                print(f"   ⚠️ Model file not found — predictor will run in heuristic mode")

            self.predictor = DemandPredictor(self.mpc_cfg, self.all_lanes_ordered, model_path)

        self.session_id = session_id
        self._loaded = True

    def teardown(self) -> None:
        self.controllers = {}
        self.cycle_plans = {}
        self.last_decisions = {}
        self.upstream_lanes = {}
        self.lane_lengths = {}
        self.predictor = None
        self.all_lanes_ordered = []
        self.session_id = None
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, snapshot: dict, step: int) -> Tuple[dict, dict]:
        """Run MPC inference. Returns (actions, telemetry).

        actions:   {tls_id: {"type": "set_phase", "value": <SUMO phase index>}}
        telemetry: {inference_time_ms, model_specific}
        """
        if not self._loaded:
            raise RuntimeError("MPC not initialized — call initialize() first")

        snapshot_lanes = snapshot.get("lanes", {})
        snapshot_intersections = snapshot.get("intersections", {})
        # Use step as the time reference (each step = 1 sim second by default).
        # mpc_adapter.py used traci.simulation.getTime() for the same purpose.
        current_step = float(step)

        start_inference = time.time()

        # ── 1. Update predictor with current flows ──────────────────
        # Same normalization as mpc_adapter.py: halting / LANE_CAPACITY.
        current_flows = {}
        for lid in self.all_lanes_ordered:
            try:
                halting = self._get_recursive_queue(lid, snapshot_lanes)
                current_flows[lid] = halting / _LANE_CAPACITY
            except Exception:
                current_flows[lid] = 0.0

        global_demand_map = {}
        if self.predictor:
            self.predictor.update_history(current_flows)
            all_predicted_demand = self.predictor.predict()
            for idx, lid in enumerate(self.all_lanes_ordered):
                global_demand_map[lid] = all_predicted_demand[idx]

        # ── 2. Per-TLS state machine (mirrors mpc_adapter.predict) ──
        mpc_phase_actions = {}   # tls_id -> MPC's internal green-phase index
        for tls_id, data in self.controllers.items():
            model = data["model"]
            plan = self.cycle_plans.get(tls_id)

            # 2a. Active plan branch
            if plan:
                elapsed = current_step - plan["start_time"]
                total_yellow_time = self.mpc_cfg.yellow_time * len(data["green_indices"])
                cycle_duration = sum(plan["durations"]) + total_yellow_time

                if elapsed >= cycle_duration:
                    plan = None
                else:
                    target_phase = self._get_phase_from_plan(plan, elapsed)

                    # Read current SUMO phase from snapshot (replaces
                    # traci.trafficlight.getPhase() in mpc_adapter.py)
                    inter_state = snapshot_intersections.get(tls_id, {})
                    current_sumo_phase_idx = inter_state.get("phase_index", -1)

                    green_indices = data["green_indices"]
                    if target_phase < len(green_indices):
                        sumo_target = green_indices[target_phase]
                    else:
                        sumo_target = green_indices[-1]

                    # Only emit an action if SUMO is on a different phase
                    if sumo_target != current_sumo_phase_idx:
                        mpc_phase_actions[tls_id] = target_phase

            # 2b. Re-optimize branch
            if not plan:
                queues = {}
                for lid in model.lane_ids:
                    try:
                        queues[lid] = self._get_recursive_queue(lid, snapshot_lanes)
                    except Exception:
                        queues[lid] = 0

                # Build [n_lanes, N] demand matrix using the LSTM forecast
                local_demand = np.zeros((model.n_lanes, model.N))
                for i, lid in enumerate(model.lane_ids):
                    if lid in global_demand_map:
                        full_pred = global_demand_map[lid]
                        scaled_arrivals = np.clip(full_pred[:model.N] * 0.20, 0.01, 0.40)
                        local_demand[i, :] = scaled_arrivals
                    else:
                        local_demand[i, :] = 0.10

                sat_flows = self._compute_saturation_flows(model.lane_ids)

                try:
                    green_times = model.optimize(
                        queues,
                        demand=local_demand,
                        capacities={},
                        sat_flows=sat_flows,
                    )
                except Exception as exc:
                    print(f"MPC optimization failed for {tls_id}: {exc}")
                    available = model.CycleTime - model.cfg.yellow_time * model.Phases
                    green_times = [available / model.Phases] * model.Phases

                self.cycle_plans[tls_id] = {
                    "start_time": current_step,
                    "durations": list(green_times),
                    "phases": list(range(len(green_times))),
                }

                # Diagnostics for /internals
                max_q = max(queues.values()) if queues else 0
                gt_str = ", ".join(f"{g:.1f}s" for g in green_times)
                print(f"🚦 MPC[{tls_id}] Step:{int(current_step)} MaxQ:{max_q}veh → [{gt_str}]")

                lstm_mode = "neural_net" if (
                    self.predictor and self.predictor.model_loaded
                    and len(self.predictor.history_buffer) >= self.predictor.history_steps
                ) else "heuristic"
                self.last_decisions[tls_id] = {
                    "max_queue": int(max_q),
                    "green_times": [round(g, 1) for g in green_times],
                    "lstm_mode": lstm_mode,
                }

                # Start phase 0 of the new plan immediately
                mpc_phase_actions[tls_id] = 0

        # ── 3. Build contract-shaped actions (set_phase) ────────────
        # mpc_adapter.py returned MPC's internal phase index and the
        # Manager mapped it to a SUMO absolute phase via the apply path.
        # Here we do that mapping inside the model so the contract is
        # uniform (set_phase carries an absolute SUMO phase index).
        contract_actions = {}
        for tls_id, mpc_phase in mpc_phase_actions.items():
            data = self.controllers.get(tls_id)
            if not data:
                continue
            green_indices = data["green_indices"]
            if mpc_phase < len(green_indices):
                sumo_phase = green_indices[mpc_phase]
            else:
                sumo_phase = green_indices[-1] if green_indices else 0
            contract_actions[tls_id] = {
                "type": "set_phase",
                "value": int(sumo_phase),
            }

        inference_ms = (time.time() - start_inference) * 1000.0

        telemetry = {
            "inference_time_ms": round(inference_ms, 2),
            "model_specific": {
                "active_plans": sum(1 for v in self.cycle_plans.values() if v is not None),
                "controllers": len(self.controllers),
                "predictor_mode": (
                    "neural_net"
                    if self.predictor and self.predictor.model_loaded
                    else "heuristic"
                ),
                "step": step,
            },
        }

        return contract_actions, telemetry

    def get_internals(self) -> dict:
        """MPC-specific internals for the dashboard's MPC Internals tab.

        Mirrors `MPCTrafficOptimizer.get_internals()` in the in-process adapter.
        """
        intersections = []
        for tls_id, dec in self.last_decisions.items():
            intersections.append({
                "id": tls_id,
                "max_queue": dec["max_queue"],
                "green_times": dec["green_times"],
                "lstm_mode": dec["lstm_mode"],
            })
        intersections.sort(key=lambda x: x["id"])

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_recursive_queue(
        self,
        lane_id: str,
        snapshot_lanes: dict,
        max_distance: float = 250.0,
    ) -> int:
        """Recursive halting count.

        Replaces traci.lane.getLastStepHaltingNumber + traci.lane.getLength
        with snapshot lookups + cached lane lengths. Logic preserved from
        mpc_adapter._get_recursive_queue() — same Katunayake fix for
        short pocket-lanes masking arterial congestion.
        """
        visited = set()
        total_halting = 0

        def _traverse(cur_lid: str, distance_acc: float) -> None:
            nonlocal total_halting
            if cur_lid in visited or distance_acc >= max_distance:
                return
            visited.add(cur_lid)

            lane_state = snapshot_lanes.get(cur_lid, {}) or {}
            halting = (
                lane_state.get("queue_length")
                or lane_state.get("halting_number")
                or 0
            )
            try:
                total_halting += int(halting)
            except (TypeError, ValueError):
                pass

            length = self.lane_lengths.get(cur_lid)
            if length is None:
                return

            new_dist = distance_acc + length
            if new_dist < max_distance:
                for pred in self.upstream_lanes.get(cur_lid, []):
                    _traverse(pred, new_dist)

        _traverse(lane_id, 0.0)
        return total_halting

    def _get_phase_from_plan(self, plan: dict, elapsed: float) -> int:
        """Same logic as mpc_adapter._get_phase_from_plan."""
        cumulative = 0.0
        yellow_duration = self.mpc_cfg.yellow_time
        for i, duration in enumerate(plan["durations"]):
            cumulative += duration + yellow_duration
            if elapsed < cumulative:
                return plan["phases"][i]
        return plan["phases"][-1]

    @staticmethod
    def _compute_saturation_flows(lane_ids: list) -> dict:
        """Same lane-name heuristic as the in-process adapter."""
        sat = {}
        for lid in lane_ids:
            ll = lid.lower()
            if any(t in ll for t in ["left", "_l_", "turn", "lt"]):
                sat[lid] = 0.35
            elif any(t in ll for t in ["right", "_r_", "rt"]):
                sat[lid] = 0.40
            else:
                sat[lid] = 0.50
        return sat
