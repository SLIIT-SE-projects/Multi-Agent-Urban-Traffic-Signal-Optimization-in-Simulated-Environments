"""Multi-EV priority arbitration and override decisions.

Ported from `services/simulation_manager/optimizers/evps_adapter.py` with
TraCI calls replaced by reads from the snapshot the Manager sends in
each `/step` request. The Manager applies returned overrides back via
TraCI itself.

Per-session state (cleared on /reset):
- fleet:            {ev_id: {buffer, smoothed_eta, target_tls, priority, ...}}
- active_overrides: {tls_id: ev_id_owning_lock}
- tls_phase_states: {tls_id: phase_state_currently_forced}

Decision pipeline per /step:
1. _update_fleet           — refresh per-EV state + LSTM ETA
2. _manage_fleet_preemption — auction → resolve → safety check
3. _build_broadcasts        — selected EV status + fleet summary

The full algorithm matches evps_adapter.py exactly.
"""
from __future__ import annotations
import random
from collections import deque
from typing import Optional, Tuple

from core.eta_predictor import EtaPredictor
from core.safety_classifier import SafetyClassifier


_DEFAULT_LOCK_DURATION_STEPS = 60


class FleetArbiter:
    def __init__(
        self,
        eta_predictor: Optional[EtaPredictor] = None,
        safety_classifier: Optional[SafetyClassifier] = None,
        sequence_length: int = 10,
        eta_smoothing_alpha: float = 0.3,
    ):
        self.eta_predictor = eta_predictor
        self.safety_classifier = safety_classifier
        self.sequence_length = sequence_length
        self.alpha = eta_smoothing_alpha

        self.fleet: dict = {}
        self.active_overrides: dict = {}
        self.tls_phase_states: dict = {}

        self.active = False
        self.selected_ev_id: str = "EV_0"
        self.session_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle / control
    # ------------------------------------------------------------------

    def reset(self, session_id: str) -> None:
        self.fleet = {}
        self.active_overrides = {}
        self.tls_phase_states = {}
        self.session_id = session_id

    def toggle(self, enable: bool) -> None:
        self.active = enable
        if not enable:
            self.fleet = {}
            self.active_overrides = {}
            self.tls_phase_states = {}

    def set_focus(self, ev_id: str) -> None:
        self.selected_ev_id = ev_id

    def set_priority(self, ev_id: str, priority: int) -> None:
        if ev_id in self.fleet:
            self.fleet[ev_id]["priority"] = int(priority)

    def register_ev(self, ev_id: str, priority: int = 1, vehicle_type: str = "ambulance") -> None:
        """Manager notifies after spawning a new EV via TraCI."""
        self.fleet[ev_id] = self._make_fleet_entry(priority, vehicle_type)
        self.selected_ev_id = ev_id

    @staticmethod
    def _make_fleet_entry(priority: int, vehicle_type: str = "ambulance") -> dict:
        return {
            "buffer": deque(maxlen=10),
            "smoothed_eta": None,
            "target_tls": None,
            "priority": int(priority),
            "safety_blocked": False,
            "speed": 0.0,
            "type": vehicle_type,
        }

    # ------------------------------------------------------------------
    # Per-step entry point
    # ------------------------------------------------------------------

    def step(self, snapshot: dict, step: int) -> dict:
        """Process one /step. Returns dict with overrides + broadcasts."""
        if not self.active:
            return {
                "overrides": {},
                "broadcasts": {self.selected_ev_id: self._inactive_status_base()},
                "released_locks": list(self.active_overrides.keys()),
            }

        vehicles = snapshot.get("vehicles", []) or []
        tls_states = snapshot.get("tls", {}) or {}
        lane_data = snapshot.get("lanes", {}) or {}

        vehicles_by_id = {v["id"]: v for v in vehicles}

        # 1. Update fleet state and LSTM ETA
        self._update_fleet(vehicles_by_id)

        # 2. Run priority arbiter
        overrides, released = self._manage_fleet_preemption(
            vehicles_by_id=vehicles_by_id,
            tls_states=tls_states,
            lane_data=lane_data,
            step=step,
        )

        # 3. Build broadcasts (driver app payload for the selected EV)
        broadcasts = self._build_broadcasts(vehicles_by_id, tls_states)

        return {
            "overrides": overrides,
            "broadcasts": broadcasts,
            "released_locks": released,
        }

    # ------------------------------------------------------------------
    # Fleet update
    # ------------------------------------------------------------------

    def _update_fleet(self, vehicles_by_id: dict) -> None:
        """Mirror of evps_adapter._update_global_fleet_state."""
        active_ids = set(vehicles_by_id.keys())

        # Remove EVs that finished their route or were removed
        for ev in [e for e in self.fleet.keys() if e not in active_ids]:
            del self.fleet[ev]

        # Update or initialize each active EV
        for ev_id, v_data in vehicles_by_id.items():
            if ev_id not in self.fleet:
                self.fleet[ev_id] = self._make_fleet_entry(
                    priority=random.choice([1, 2]),
                    vehicle_type=v_data.get("type", "ambulance"),
                )

            fleet_ev = self.fleet[ev_id]

            next_tls_list = v_data.get("next_tls", []) or []
            current_tls = next_tls_list[0]["tls_id"] if next_tls_list else None

            # Reset feature buffer if target TLS changed
            if fleet_ev["target_tls"] is not None and fleet_ev["target_tls"] != current_tls:
                fleet_ev["buffer"].clear()
                fleet_ev["smoothed_eta"] = None
            fleet_ev["target_tls"] = current_tls

            speed = v_data.get("speed", 0.0)
            fleet_ev["speed"] = speed

            if self.eta_predictor:
                features = self._extract_features(v_data)
                if features is not None:
                    fleet_ev["buffer"].append(features)
                    current_dist = features[2]

                    # Bypass AI if very close or no upcoming TLS
                    if current_tls is None or current_dist < 15.0:
                        fleet_ev["smoothed_eta"] = 0.0
                    elif len(fleet_ev["buffer"]) == self.sequence_length:
                        try:
                            raw_eta = self.eta_predictor.predict(
                                list(fleet_ev["buffer"]),
                                current_distance=current_dist,
                            )
                            if fleet_ev["smoothed_eta"] is None:
                                fleet_ev["smoothed_eta"] = raw_eta
                            else:
                                fleet_ev["smoothed_eta"] = (
                                    self.alpha * raw_eta
                                    + (1.0 - self.alpha) * fleet_ev["smoothed_eta"]
                                )
                        except Exception as exc:
                            print(f"[FleetArbiter] ETA prediction failed for {ev_id}: {exc}")

    @staticmethod
    def _extract_features(v_data: dict) -> Optional[list]:
        """Extract the 6-feature frame the LSTM expects."""
        try:
            speed = v_data.get("speed", 0.0)
            accel = v_data.get("acceleration", 0.0)

            next_tls = v_data.get("next_tls", []) or []
            if next_tls:
                dist = next_tls[0].get("distance", 0.0)
            else:
                lane_pos = v_data.get("lane_position", 0.0)
                lane_len = v_data.get("current_lane_length", 0.0)
                dist = max(0.0, lane_len - lane_pos)

            queue = v_data.get("current_lane_halting", 0)

            leader = v_data.get("leader") or {}
            l_gap = leader.get("gap", 200.0)
            l_speed = leader.get("speed", 30.0)

            return [speed, accel, dist, queue, l_gap, l_speed]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Preemption arbiter
    # ------------------------------------------------------------------

    def _manage_fleet_preemption(
        self,
        vehicles_by_id: dict,
        tls_states: dict,
        lane_data: dict,
        step: int,
    ) -> Tuple[dict, list]:
        """Mirror of evps_adapter._manage_fleet_preemption."""
        overrides: dict = {}
        released_locks: list = []

        # 1. CLEANUP STALE LOCKS
        locks_to_remove: list = []
        for tls_id, owner_id in self.active_overrides.items():
            if owner_id not in vehicles_by_id:
                locks_to_remove.append(tls_id)
            else:
                v_data = vehicles_by_id[owner_id]
                next_tls_ids = [t["tls_id"] for t in v_data.get("next_tls", []) or []]
                if tls_id not in next_tls_ids:
                    locks_to_remove.append(tls_id)

        for tls_id in locks_to_remove:
            released_locks.append(tls_id)
            self.active_overrides.pop(tls_id, None)
            self.tls_phase_states.pop(tls_id, None)

        # 2. AUCTION HOUSE — gather bids
        intersection_bids: dict = {}
        for ev_id, fleet_ev in self.fleet.items():
            if fleet_ev["smoothed_eta"] is None:
                continue
            v_data = vehicles_by_id.get(ev_id)
            if not v_data:
                continue

            next_tls_list = v_data.get("next_tls", []) or []
            planning_speed = max(fleet_ev["speed"], 10.0)

            for i, tls_info in enumerate(next_tls_list):
                t_id = tls_info["tls_id"]
                t_index = tls_info["tls_index"]
                t_dist = tls_info["distance"]

                if i == 0:
                    t_eta = fleet_ev["smoothed_eta"]
                else:
                    t_eta = t_dist / planning_speed

                if t_eta < 30.0:
                    if t_id not in intersection_bids:
                        intersection_bids[t_id] = []

                    # Hysteresis: existing owner gets infinite priority
                    bid_priority = fleet_ev["priority"]
                    if self.active_overrides.get(t_id) == ev_id:
                        bid_priority = 999

                    intersection_bids[t_id].append({
                        "ev_id": ev_id,
                        "priority": bid_priority,
                        "eta": t_eta,
                        "speed": fleet_ev["speed"],
                        "tls_index": t_index,
                        "order": i,
                    })

        # 3. RESOLVE CONFLICTS
        provisional_wins: dict = {ev: [] for ev in self.fleet.keys()}
        for tls_id, bids in intersection_bids.items():
            bids.sort(key=lambda x: (-x["priority"], x["eta"], -x["speed"]))
            winner = bids[0]
            provisional_wins[winner["ev_id"]].append({
                "tls_id": tls_id,
                "tls_index": winner["tls_index"],
                "order": winner["order"],
            })

        # 4. SAFETY CHECK & EXECUTION (cascade-block per EV)
        for ev_id, won_lights in provisional_wins.items():
            self.fleet[ev_id]["safety_blocked"] = False
            won_lights.sort(key=lambda x: x["order"])

            for light in won_lights:
                t_id = light["tls_id"]
                t_index = light["tls_index"]

                # Hysteresis: skip safety check if already locked by us
                if self.active_overrides.get(t_id) == ev_id:
                    if t_id in self.tls_phase_states:
                        overrides[t_id] = {
                            "phase_state": self.tls_phase_states[t_id],
                            "ev_id": ev_id,
                            "lock_until_step": step + _DEFAULT_LOCK_DURATION_STEPS,
                            "reason": f"Active lock (hysteresis) for {ev_id}",
                        }
                    continue

                is_safe = self._evaluate_safety(
                    ev_id, t_id, vehicles_by_id, tls_states, lane_data
                )

                if not is_safe:
                    self.fleet[ev_id]["safety_blocked"] = True
                    if light["order"] == 0:
                        print(f"⚠️ SAFETY: {ev_id} denied at {t_id} (gridlock risk)")
                    break  # cascade block: don't preempt downstream lights either

                target_state = self._compute_force_green_state(t_id, t_index, tls_states)
                if target_state:
                    overrides[t_id] = {
                        "phase_state": target_state,
                        "ev_id": ev_id,
                        "lock_until_step": step + _DEFAULT_LOCK_DURATION_STEPS,
                        "reason": f"Green wave for {ev_id}",
                    }
                    self.active_overrides[t_id] = ev_id
                    self.tls_phase_states[t_id] = target_state

        return overrides, released_locks

    def _evaluate_safety(
        self,
        ev_id: str,
        tls_id: str,
        vehicles_by_id: dict,
        tls_states: dict,
        lane_data: dict,
    ) -> bool:
        """Mirror of evps_adapter._evaluate_safety, snapshot-driven."""
        if not self.safety_classifier:
            return True
        try:
            v_data = vehicles_by_id[ev_id]
            ev_lane = v_data.get("current_lane")
            if not ev_lane:
                return True

            downstream_lane = self._get_downstream_lane(v_data)
            if not downstream_lane:
                return True

            target_queue = lane_data.get(ev_lane, {}).get("halting", 0)

            tls = tls_states.get(tls_id, {})
            controlled_lanes = tls.get("controlled_lanes", []) or []
            conflicting_vol = sum(
                lane_data.get(lane, {}).get("vehicle_count", 0)
                for lane in set(controlled_lanes) if lane != ev_lane
            )

            time_since_change = 10.0  # constant in original
            num_conflicting_lanes = max(1, len(set(controlled_lanes)) - 1)
            downstream_len = lane_data.get(downstream_lane, {}).get("length", 100.0)
            clearance_dist = num_conflicting_lanes * 3.5

            features = {
                "target_queue_length": target_queue,
                "conflicting_volume": conflicting_vol,
                "time_since_last_phase": time_since_change,
                "num_conflicting_lanes": num_conflicting_lanes,
                "downstream_lane_length": downstream_len,
                "clearance_distance": clearance_dist,
            }
            return self.safety_classifier.predict(features) != 1
        except Exception as exc:
            print(f"[FleetArbiter] Safety eval failed for {ev_id}@{tls_id}: {exc}")
            return True

    @staticmethod
    def _get_downstream_lane(v_data: dict) -> Optional[str]:
        """Mirror of evps_adapter._get_downstream_lane."""
        try:
            route = v_data.get("route", []) or []
            curr_edge = v_data.get("current_edge")
            if curr_edge in route:
                idx = route.index(curr_edge)
                if idx + 1 < len(route):
                    return f"{route[idx + 1]}_0"
        except Exception:
            pass
        return None

    @staticmethod
    def _compute_force_green_state(
        tls_id: str,
        tls_index: int,
        tls_states: dict,
    ) -> Optional[str]:
        """Find the phase state string that lights `tls_index` green.

        Mirrors evps_adapter._force_green_wave (without the TraCI side-effect).
        """
        tls = tls_states.get(tls_id, {})
        phases = tls.get("phases", []) or []
        for phase in phases:
            state = phase.get("state", "")
            if len(state) > tls_index and state[tls_index] in ('G', 'g'):
                return state
        return None

    # ------------------------------------------------------------------
    # Broadcasts
    # ------------------------------------------------------------------

    def _build_broadcasts(self, vehicles_by_id: dict, tls_states: dict) -> dict:
        """Driver-app payload for the selected EV. Manager relays this via WS."""
        # Fleet summary used in every broadcast
        fleet_telemetry = []
        for v_id, v_data in self.fleet.items():
            fleet_telemetry.append({
                "id": v_id,
                "speed": float(f"{v_data['speed'] * 3.6:.1f}"),
                "priority": v_data["priority"],
                "safety_blocked": v_data["safety_blocked"],
            })

        ev_id = self.selected_ev_id
        if ev_id not in self.fleet or ev_id not in vehicles_by_id:
            base = self._inactive_status_base()
            base.update({
                "ev_id": ev_id,
                "active": True,
                "active_fleet": list(self.fleet.keys()),
                "fleet": fleet_telemetry,
                "active_evs": len(self.fleet),
                "override_junctions": list(self.active_overrides.keys()),
            })
            return {ev_id: base}

        ev_state = self.fleet[ev_id]
        v_data = vehicles_by_id[ev_id]

        speed = ev_state["speed"]
        geo = v_data.get("geo_position") or [0.0, 0.0]
        lat = geo[1] if isinstance(geo, (list, tuple)) and len(geo) >= 2 else 0.0
        lon = geo[0] if isinstance(geo, (list, tuple)) and len(geo) >= 2 else 0.0

        next_tls = v_data.get("next_tls", []) or []
        dist_to_tls = next_tls[0]["distance"] if next_tls else 0.0

        display_tls_id = ""
        for tls_item in next_tls:
            if self.active_overrides.get(tls_item["tls_id"]) == ev_id:
                display_tls_id = tls_item["tls_id"]
                break
        is_green_wave = bool(display_tls_id)

        # Active junctions for the driver app's map (locked by selected EV)
        active_junctions = []
        for tls_id, owner in self.active_overrides.items():
            if owner != ev_id:
                continue
            tls_pos = tls_states.get(tls_id, {}).get("geo_position")
            if tls_pos and isinstance(tls_pos, (list, tuple)) and len(tls_pos) >= 2:
                active_junctions.append({
                    "id": tls_id,
                    "lat": tls_pos[1],
                    "lon": tls_pos[0],
                })

        return {
            ev_id: {
                "type": "status",
                "ev_id": ev_id,
                "active": True,
                "eta": float(f"{ev_state['smoothed_eta']:.1f}") if ev_state["smoothed_eta"] else 0.0,
                "speed": float(f"{speed * 3.6:.1f}"),
                "dist_to_tls": float(f"{dist_to_tls:.1f}"),
                "lat": lat,
                "lon": lon,
                "priority": ev_state["priority"],
                "green_wave_active": is_green_wave,
                "safety_blocked": ev_state["safety_blocked"],
                "tls_id": display_tls_id,
                "active_junctions": active_junctions,
                "active_fleet": list(self.fleet.keys()),
                "fleet": fleet_telemetry,
                "active_evs": len(self.fleet),
                "override_junctions": list(self.active_overrides.keys()),
            }
        }

    def _inactive_status_base(self) -> dict:
        return {
            "type": "status",
            "ev_id": self.selected_ev_id,
            "active": False,
            "eta": 0.0,
            "speed": 0.0,
            "lat": 0.0,
            "lon": 0.0,
            "priority": 1,
            "green_wave_active": False,
            "safety_blocked": False,
            "tls_id": "",
            "active_junctions": [],
            "active_fleet": [],
            "fleet": [],
            "active_evs": 0,
            "override_junctions": [],
        }
