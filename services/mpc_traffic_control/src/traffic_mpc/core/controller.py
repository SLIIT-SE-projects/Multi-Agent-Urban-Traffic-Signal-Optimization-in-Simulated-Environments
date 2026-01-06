"""
MPC Controller Core (Phase Split Optimization + Anti-Spillback).
Now includes Link Capacity Constraints to prevent gridlock.
"""
import logging
import numpy as np
import casadi as ca
from typing import List, Dict

from traffic_mpc.config.settings import MPCConfig, OptimizationConfig

logger = logging.getLogger(__name__)

class MPCController:
    def __init__(self, 
                 mpc_config: MPCConfig, 
                 opt_config: OptimizationConfig,
                 lane_ids: List[str],
                 num_phases: int,
                 lane_phase_indices: List[int]): 
        self.cfg = mpc_config
        self.opt_cfg = opt_config
        self.lane_ids = lane_ids
        self.n_lanes = len(lane_ids)
        self.lane_phase_indices = lane_phase_indices
        
        # Validation
        if len(self.lane_phase_indices) != self.n_lanes:
            raise ValueError(f"lane_phase_indices length ({len(self.lane_phase_indices)}) must match lane_ids ({self.n_lanes})")
        if max(self.lane_phase_indices) >= num_phases:
            raise ValueError(f"Max phase index {max(self.lane_phase_indices)} exceeds num_phases {num_phases}")

        self.N = self.cfg.control_horizon  
        self.CycleTime = 60 # TODO: make configurable or dynamic
        self.Phases = num_phases
        
        self._setup_solver()

    def _setup_solver(self):
        self.opti = ca.Opti()
        
        # Variables
        self.G = self.opti.variable(self.Phases, self.N)
        self.Q_state = self.opti.variable(self.n_lanes, self.N + 1)
        
        # Parameters
        self.P_q0 = self.opti.parameter(self.n_lanes) 
        self.P_demand = self.opti.parameter(self.n_lanes, self.N) 
        self.P_sat = self.opti.parameter(self.n_lanes) 
        # NEW: Link Capacity Parameter
        self.P_capacity = self.opti.parameter(self.n_lanes) 
        
        # Objective
        cost = 0
        for k in range(self.N):
            cost += ca.sumsqr(self.Q_state[:, k+1])
        
        self.opti.minimize(cost)
        
        # Constraints
        self.opti.subject_to(self.Q_state[:, 0] == self.P_q0)
        
        lost_time = 4 * self.Phases 
        available_green = self.CycleTime - lost_time
        
        for k in range(self.N):
            self.opti.subject_to(ca.sum1(self.G[:, k]) == available_green)
            self.opti.subject_to(self.G[:, k] >= 10) 
            
            departures = ca.MX.zeros(self.n_lanes)
            for i in range(self.n_lanes):
                # Use the mapping provided at init
                phase_idx = self.lane_phase_indices[i]
                departures[i] = self.P_sat[i] * self.G[phase_idx, k]
            
            q_next = self.Q_state[:, k] + self.P_demand[:, k] - departures
            
            self.opti.subject_to(self.Q_state[:, k+1] >= 0)
            self.opti.subject_to(self.Q_state[:, k+1] == q_next)
            
            # --- CRITICAL FIX: SPILLBACK CONSTRAINT ---
            # Queue cannot exceed Lane Capacity (e.g. 20 cars)
            # If Q hits Max, the solver is forced to reduce Green upstream 
            # (or at least acknowledge the jam).
            # We use a soft constraint or hard limit. Hard limit is safer for gridlock.
            self.opti.subject_to(self.Q_state[:, k+1] <= self.P_capacity)

        opts = {'ipopt.print_level': 0, 'print_time': 0, 'ipopt.sb': 'yes', 'ipopt.max_iter': 100}
        self.opti.solver('ipopt', opts)

    def optimize(self, queues: Dict[str, float], demand: np.ndarray, capacities: Dict[str, float]) -> List[float]:
        """
        Returns optimal green times [g1, g2, g3, g4].
        """
        q0 = np.array([queues.get(l, 0) for l in self.lane_ids])
        self.opti.set_value(self.P_q0, q0)
        
        cycle_demand = np.mean(demand) * self.CycleTime 
        self.opti.set_value(self.P_demand, np.full((self.n_lanes, self.N), cycle_demand))
        
        self.opti.set_value(self.P_sat, np.full(self.n_lanes, 0.5))
        
        # --- NEW: Set Capacities ---
        # Default to 40 vehicles (approx 300m lane) if unknown
        caps = np.array([capacities.get(l, 40.0) for l in self.lane_ids])
        self.opti.set_value(self.P_capacity, caps)
        
        try:
            sol = self.opti.solve()
            return list(sol.value(self.G[:, 0]))
        except:
            return [15.0] * self.Phases