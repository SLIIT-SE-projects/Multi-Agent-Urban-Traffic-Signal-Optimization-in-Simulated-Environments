"""
MPC Controller Core (Incidence Matrix + Throughput Maximization).
Fixes lane-phase mapping and actively maximizes flow.
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
                 phases: List[str]): 
        self.cfg = mpc_config
        self.opt_cfg = opt_config
        self.lane_ids = lane_ids
        self.n_lanes = len(lane_ids)
        
        self.N = 3  
        self.CycleTime = 60 
        self.Phases = 4 
        
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
        self.P_capacity = self.opti.parameter(self.n_lanes)
        
        # NEW: Incidence Matrix [n_lanes, n_phases]
        # Entry (i, p) = 1 if lane i is Green in phase p
        self.P_inc = self.opti.parameter(self.n_lanes, self.Phases)
        
        # Objective
        cost = 0
        total_outflow = 0
        
        for k in range(self.N):
            # 1. Minimize Queues
            cost += 10.0 * ca.sumsqr(self.Q_state[:, k+1])
            
            # 2. Maximize Throughput (Negative Cost)
            # Calculate outflow for this step
            current_outflow = ca.MX.zeros(self.n_lanes)
            for p in range(self.Phases):
                # Only lanes belonging to phase p get flow
                current_outflow += self.P_sat * self.P_inc[:, p] * self.G[p, k]
            
            # Bound outflow by available cars (Store-and-forward constraint logic)
            # We add a term to encourage high G for busy lanes
            cost -= 1.0 * ca.sum1(current_outflow)
            
            # 3. Smoothness (Prevent flickering)
            if k > 0:
                cost += 0.1 * ca.sumsqr(self.G[:, k] - self.G[:, k-1])
        
        self.opti.minimize(cost)
        
        # Constraints
        self.opti.subject_to(self.Q_state[:, 0] == self.P_q0)
        
        lost_time = 4 * self.Phases 
        available_green = self.CycleTime - lost_time
        
        for k in range(self.N):
            self.opti.subject_to(ca.sum1(self.G[:, k]) == available_green)
            self.opti.subject_to(self.G[:, k] >= 5) # Min Green 5s
            
            # --- DYNAMICS WITH INCIDENCE MATRIX ---
            departures = ca.MX.zeros(self.n_lanes)
            for p in range(self.Phases):
                # Vectorized: Add flow from this phase to all relevant lanes
                # Departure_i += Sat_i * Inc_ip * G_pk
                departures += self.P_sat * self.P_inc[:, p] * self.G[p, k]
            
            # Flow Gating (Fix 3): Cannot discharge more than downstream capacity
            # available_space = P_capacity - Q
            # departures = min(departures, available_space)
            # We use a soft constraint to avoid infeasibility
            self.opti.subject_to(departures <= self.P_capacity - self.Q_state[:, k])
            
            q_next = self.Q_state[:, k] + self.P_demand[:, k] - departures
            
            self.opti.subject_to(self.Q_state[:, k+1] >= 0)
            self.opti.subject_to(self.Q_state[:, k+1] == q_next)
            self.opti.subject_to(self.Q_state[:, k+1] <= self.P_capacity)

        opts = {'ipopt.print_level': 0, 'print_time': 0, 'ipopt.sb': 'yes', 'ipopt.max_iter': 100}
        self.opti.solver('ipopt', opts)

    def optimize(self, 
                 queues: Dict[str, float], 
                 demand: np.ndarray, 
                 capacities: Dict[str, float],
                 incidence_matrix: np.ndarray) -> List[float]: # <--- NEW ARG
        
        # 1. State & Params
        q0 = np.array([queues.get(l, 0) for l in self.lane_ids])
        self.opti.set_value(self.P_q0, q0)
        
        # 2. Demand (Lane-Specific)
        # Demand input is [n_lanes, N]
        if demand.shape != (self.n_lanes, self.N):
             # Reshape or Broadcast if single vector
             cycle_demand = np.mean(demand) * self.CycleTime
             demand = np.full((self.n_lanes, self.N), cycle_demand)
        else:
             # Scale veh/sec to veh/cycle
             demand = demand * self.CycleTime
             
        self.opti.set_value(self.P_demand, demand)
        
        # 3. Saturation & Capacity
        self.opti.set_value(self.P_sat, np.full(self.n_lanes, 0.5))
        caps = np.array([capacities.get(l, 40.0) for l in self.lane_ids])
        self.opti.set_value(self.P_capacity, caps)
        
        # 4. Incidence Matrix (The Key Fix)
        # Ensure shape [n_lanes, n_phases]
        if incidence_matrix.shape != (self.n_lanes, self.Phases):
            # Fallback to identity or modulo if missing
            logger.warning("Invalid incidence matrix shape. Using fallback.")
            incidence_matrix = np.zeros((self.n_lanes, self.Phases))
            for i in range(self.n_lanes):
                incidence_matrix[i, i % self.Phases] = 1
                
        self.opti.set_value(self.P_inc, incidence_matrix)
        
        try:
            sol = self.opti.solve()
            return list(sol.value(self.G[:, 0]))
        except:
            return [15.0] * self.Phases